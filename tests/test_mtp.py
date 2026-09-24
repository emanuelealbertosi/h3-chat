import io
import os
import json
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from h3chat.engine import Engine
from h3chat.hardware import assess_model
from h3chat.models import inspect_model, metadata, mtp_tokens
from h3chat.service import Service
from h3chat.store import DEFAULTS

ROOT=Path(__file__).resolve().parents[1]


def mtp_gguf(path, arch='qwen35', heads=1, blocks=5, names=None, extra=None):
    """Structural fixture, not trained model weights; never used for inference."""
    names=names if names is not None else ['token_embd.weight','blk.0.attn_norm.weight']+[
        f'blk.{i}.nextn.{n}.weight' for i in range(blocks-heads,blocks) for n in ('eh_proj','enorm','hnorm')]
    def string(value):
        raw=value.encode();return struct.pack('<Q',len(raw))+raw
    values={'general.architecture':arch,arch+'.block_count':blocks,arch+'.nextn_predict_layers':heads}|(extra or {})
    data=b'GGUF'+struct.pack('<IQQ',3,len(names),len(values))
    for key,value in values.items():
        data+=string(key)+struct.pack('<I',8 if isinstance(value,str) else 4)
        data+=string(value) if isinstance(value,str) else struct.pack('<I',value)
    for i,name in enumerate(names):
        data+=string(name)+struct.pack('<IQIQ',1,1,0,i*32)
    data+=b'\0'*((-len(data))%32)+b'\0'*(32*len(names))
    path.parent.mkdir(parents=True,exist_ok=True)
    previous=path.stat().st_mtime_ns if path.exists() else 0
    path.write_bytes(data)
    stamp=path.stat()
    # Virtual Windows runners can give rapid same-size rewrites the same timestamp.
    if stamp.st_mtime_ns<=previous:os.utime(path,ns=(stamp.st_atime_ns,previous+1_000_000))
    return path


class MtpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.path=mtp_gguf(self.root/'already downloaded à/model.gguf')
        self.model={'id':'mtp','name':'Structural MTP fixture','external':True,'local':True,
                    'capabilities':['chat'],'files':[]}
        self.sync()
        self.settings=DEFAULTS|{'chat_model':'mtp','profile':'cpu','backend':'cpu','ram_cache_gb':0}

    def tearDown(self): self.tmp.cleanup()

    def sync(self, paths=None):
        self.model['files']=[{'role':'model' if i==0 else 'shard','path':str(p),'size':p.stat().st_size}
                             for i,p in enumerate(paths or [self.path])]
        self.model.update(inspect_model(self.root,self.model))

    def test_detection_requires_declared_heads_and_actual_tensors(self):
        self.assertTrue(self.model['mtp']['supported'])
        mtp_gguf(self.path,names=['token_embd.weight','blk.0.attn_norm.weight'])
        self.sync();self.assertFalse(self.model['mtp']['supported'])
        self.assertIn('assenti',self.model['mtp']['note'])
        mtp_gguf(self.path,heads=0);self.sync()
        self.assertFalse(self.model['mtp']['supported'])
        self.assertIn('non dichiara',self.model['mtp']['note'])

    def test_split_model_uses_all_parts_and_missing_part_disables_mtp(self):
        mtp_gguf(self.path,names=['token_embd.weight','blk.0.attn_norm.weight'],extra={'split.count':2})
        part=mtp_gguf(self.path.with_name('part2.gguf'),names=[f'blk.4.nextn.{n}.weight' for n in ('eh_proj','enorm','hnorm')])
        self.sync([self.path,part]);self.assertTrue(self.model['mtp']['supported'])
        part.unlink();self.sync([self.path]);self.assertFalse(self.model['mtp']['supported'])
        self.assertFalse(self.model['ready'])

    def test_unknown_architecture_multiple_heads_and_draft_only(self):
        mtp_gguf(self.path,arch='unsupported');self.sync();self.assertFalse(self.model['mtp']['supported'])
        mtp_gguf(self.path,heads=2);self.sync();self.assertFalse(self.model['mtp']['supported'])
        mtp_gguf(self.path,arch='step35',heads=2);self.sync();self.assertTrue(self.model['mtp']['supported'])
        self.assertEqual(mtp_tokens(self.model,self.settings|{'mtp_enabled':True,'mtp_draft_tokens':8}),2)
        mtp_gguf(self.path,names=['token_embd.weight']+[f'blk.4.nextn.{n}.weight' for n in ('eh_proj','enorm','hnorm')])
        self.sync();self.assertIn('solo il modulo',self.model['mtp']['note'])

    def test_truncated_directory_and_payload_are_not_reported_as_mtp(self):
        original=self.path.read_bytes()
        for count in (32,80,120):
            self.path.write_bytes(original[:-count]);self.sync()
            self.assertFalse(self.model['mtp']['supported'])
        self.path.write_bytes(b'GGUF'+struct.pack('<IQQ',3,200001,0))
        self.assertFalse(metadata(self.path)['_h3_tensor_scan_ok'])

    def test_effective_mode_and_session_identity(self):
        engine=Engine(self.root,self.root,{'mtp':self.model})
        key=lambda s:engine.session_key('chat',self.model,s)
        base=key(self.settings)
        self.assertEqual(base,key(self.settings|{'max_tokens':512,'think_level':'high','mtp_draft_tokens':6}))
        enabled=self.settings|{'mtp_enabled':True}
        self.assertNotEqual(base,key(enabled))
        self.assertNotEqual(key(enabled),key(enabled|{'mtp_draft_tokens':6}))
        self.model['mtp']['supported']=False
        self.assertEqual(base,key(enabled))

    def test_mtp_memory_overhead_and_unsupported_models(self):
        hw={'ram':{'free_mb':32000,'total_mb':40000},'gpu':[{'name':'GPU','vendor':'NVIDIA','free_mb':16000,'total_mb':18000}]}
        for settings in (self.settings,self.settings|{'profile':'balanced','backend':'cuda','gpu_layers':99}):
            off=assess_model(self.model,settings,hw)
            on=assess_model(self.model,settings|{'mtp_enabled':True},hw)
            key='ram_gb' if settings['profile']=='cpu' else 'vram_gb'
            self.assertGreater(on[key],off[key]);self.assertTrue(any('MTP' in n for n in on['assumptions']))

    def test_runtime_uses_native_mtp_and_checks_activation(self):
        class Response(io.BytesIO): status=200
        class Process:
            pid=123;stdin=None;stdout=None
            def poll(self):return None
            def terminate(self):pass
            def wait(self,timeout):return 0
        for enabled,active in ((False,False),(True,True),(True,False)):
            engine=Engine(self.root,self.root,{'mtp':self.model});commands=[];requests=[]
            def start(session,args):
                commands.append(args);session.process=Process()
            def response(req,**kwargs):
                requests.append(req.full_url)
                return Response(json.dumps([{'speculative':active}] if req.full_url.endswith('/slots') else {'status':'ok'}).encode())
            try:
                with patch('h3chat.engine.runtime_executable',return_value='llama-server.exe'),patch('h3chat.residency.Session.start',start),patch('h3chat.engine.urllib.request.urlopen',side_effect=response):
                    if enabled and not active:
                        with self.assertRaisesRegex(RuntimeError,'non ha attivato MTP'):
                            engine.start_llama(self.model,self.settings|{'mtp_enabled':enabled},self.root/'engine.log',threading.Event())
                    else:
                        engine.start_llama(self.model,self.settings|{'mtp_enabled':enabled},self.root/'engine.log',threading.Event())
                        self.assertEqual(engine.snapshot()['models'][0]['mtp_tokens'],3 if enabled else 0)
                args=commands[0]
                self.assertEqual(args[args.index('--spec-type')+1],'draft-mtp' if enabled else 'none')
                self.assertNotIn('--model-draft',args)
                self.assertEqual(any(p.endswith('/slots') for p in requests),enabled)
            finally:engine.stop()

    def test_max_tokens_reaches_plain_and_canvas_completion(self):
        engine=Engine(self.root,self.root,{})
        engine.active=SimpleNamespace(port=1000,api_key='test');engine.active_model=self.model
        for schema in (None,{'type':'object'}):
            bodies=[]
            def response(req,**kwargs):
                bodies.append(json.loads(req.data));return io.BytesIO(b'data: {"choices":[{"delta":{"content":"42"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n')
            with patch('h3chat.engine.urllib.request.urlopen',side_effect=response):
                engine.completion([],self.settings|{'max_tokens':192,'think_level':'high'},threading.Event(),on_text=lambda _:None,schema=schema)
            self.assertEqual(bodies[0]['max_tokens'],192)

    def test_refresh_keeps_external_model_visible_and_publishes_mtp_traits(self):
        app=Service(ROOT,self.root/'data',start_worker=False)
        entered=threading.Event();release=threading.Event();thread=None;errors=[]
        try:
            linked=app.external_model({'profile':'chat','files':{'model':str(self.path)}})
            settings=app.save_settings({'chat_model':linked['id'],'mtp_enabled':True})
            self.assertTrue(app.catalog[linked['id']]['mtp']['supported'])
            selected=app.engine.require_model(linked['id'],'chat')
            self.assertEqual(app.engine.session_key('chat',selected,settings),app.engine.session_key('chat',app.catalog[linked['id']],settings))
            def paused_scan(root):
                entered.set();release.wait(5);return []
            def refresh():
                try: app.refresh_models()
                except Exception as exc:errors.append(exc)
            with patch('h3chat.service.discover_local',side_effect=paused_scan):
                thread=threading.Thread(target=refresh);thread.start()
                self.assertTrue(entered.wait(5))
                # The worker can still find the model while a UI refresh waits for disk.
                self.assertTrue(app.engine.require_model(linked['id'],'chat')['mtp']['supported'])
                release.set();thread.join(5);self.assertFalse(thread.is_alive())
            self.assertFalse(errors)
        finally:
            release.set()
            if thread:thread.join(5)
            app.close()

    def test_settings_validation_persistence_and_queued_snapshot(self):
        app=Service(ROOT,self.root/'data',start_worker=False)
        try:
            for values in ({'mtp_enabled':'yes'},{'mtp_enabled':1},{'mtp_draft_tokens':0},{'mtp_draft_tokens':9},{'mtp_draft_tokens':True},{'max_tokens':63},{'max_tokens':9000},{'context':1024,'max_tokens':768}):
                with self.assertRaises(ValueError):app.validate_settings(values)
            settings=app.save_settings({'mtp_enabled':True,'mtp_draft_tokens':5,'max_tokens':512})
            chat=app.store.create_chat();jid=app.store.enqueue(chat['id'],'Ciao',[],settings)
            app.save_settings({'mtp_enabled':False,'mtp_draft_tokens':1,'max_tokens':256})
            saved=json.loads(app.store.one('SELECT payload FROM jobs WHERE id=?',(jid,))['payload'])['settings']
            self.assertEqual((saved['mtp_enabled'],saved['mtp_draft_tokens'],saved['max_tokens']),(True,5,512))
            self.assertEqual(app.store.settings()['max_tokens'],256)
        finally:app.close()


if __name__=='__main__':unittest.main()
