"""Private accelerator lifecycle regression tests: no GPU or native inference."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from h3chat import llm_acceleration as accel
from h3chat.llm_acceleration import check_hardware as real_check_hardware
from h3chat.engine import Engine, runtime_executable
from h3chat.models import inspect_model
from h3chat.residency import Session
from h3chat.store import DEFAULTS, Store
from h3chat.llm_options import merge, validate
from test_mtp import mtp_gguf


class Process:
    pid = 123
    stdin = stdout = None
    def __init__(self): self.ended = False
    def poll(self): return 0 if self.ended else None
    def terminate(self): self.ended = True
    def wait(self, timeout): return 0


class Response(io.BytesIO): status = 200


class AccelerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = mtp_gguf(self.root/accel.FILENAME, blocks=65, extra={
            'qwen35.embedding_length':5120, 'qwen35.attention.head_count':24,
            'qwen35.attention.head_count_kv':4})
        self.model = {'id':'llm','name':'IQ3_S fixture','external':True,'local':True,
                      'capabilities':['chat'], 'files':[{'role':'model',
                      'path':str(self.path),'size':accel.MODEL_BYTES}]}
        self.model.update(inspect_model(self.root,self.model))
        # The fixture contains structure only, never the real model's 12 GB payload.
        self.model['files'][0]['size'] = accel.MODEL_BYTES
        self.catalog = {'llm':self.model}
        for name,cap in [('image','create'),('music','music'),('video','video')]:
            p = self.root/(name+'.bin');p.write_bytes(b'fixture')
            self.catalog[name] = {'id':name,'name':name,'capabilities':[cap],
                'architecture':'sd','files':[{'role':'model','path':str(p),'size':7}]}
        self.engine = Engine(self.root,self.root/'data',self.catalog)
        self.settings = DEFAULTS|{'chat_model':'llm','create_model':'image',
            'edit_model':'image','music_model':'music','video_model':'video',
            'profile':'balanced','backend':'cuda','gpu_layers':999,
            'context':131072,'mtp_enabled':True,'mtp_draft_tokens':2,
            'llm_acceleration':'qwen27','memory_policy':'on_demand','ram_cache_gb':0}
        self.cancel = threading.Event();self.commands = [];self.requests = []
        self.exe = str(self.root/accel.FOLDER/'llama-server.exe')
        def start(session,args):
            self.commands.append((session,list(args)));session.process = Process()
        def response(req,**kwargs):
            self.requests.append(req)
            return Response(json.dumps([{'speculative':True}] if req.full_url.endswith('/slots') else {'status':'ok'}).encode())
        for mock in (patch.object(accel,'_model_size',return_value=accel.MODEL_BYTES),
                     patch.object(accel,'_verified',return_value=self.exe),
                     patch.object(accel,'check_hardware'),
                     patch('h3chat.residency.Session.start',start),
                     patch('h3chat.engine.urllib.request.urlopen',side_effect=response),
                     patch('h3chat.engine.runtime_executable',return_value='standard/llama-server.exe')):
            mock.start();self.addCleanup(mock.stop)

    def tearDown(self):
        self.engine.stop();self.tmp.cleanup()

    def load(self, settings=None):
        self.engine.start_llama(self.model,settings or self.settings,self.root/'llm.log',self.cancel)
        return self.engine.active

    def use_orca(self):
        self.path = self.path.rename(self.root/accel.ORCA_FILENAME)
        self.model['name'] = 'Orca fixture'
        self.model['files'][0].update(path=str(self.path),size=accel.ORCA_BYTES)
        self.settings['mtp_draft_tokens'] = 4
        mock=patch.object(accel,'_model_size',return_value=accel.ORCA_BYTES)
        mock.start();self.addCleanup(mock.stop)

    def test_orca_uses_same_owned_runtime_128k_mtp4_and_u512(self):
        self.use_orca()
        self.assertEqual(accel.model_profile(self.model),'orca-iq3xxs')
        session=self.load();args=self.commands[-1][1]
        for option,value in {'--ctx-size':131072,'--spec-draft-n-max':4,
                             '--ubatch-size':512,'--cache-type-k':'q4_0'}.items():
            self.assertEqual(args[args.index(option)+1],value)
        self.assertIn('Orca',session.acceleration);self.assertIn('MTP4',session.acceleration)
        self.assertEqual(session.child_env['QWEN27_MTP_WINDOW'],'8192')
        self.assertEqual(accel.traits(self.root,self.model)['draft_tokens'],4)
        self.assertIs(self.load(),session)
        self.engine.abort_active();self.assertFalse(session.alive())

    def test_orca_vision_u512_and_incompatible_options_rejected(self):
        self.use_orca()
        with patch.object(self.engine,'model_files',return_value={'model':str(self.path),'mmproj':'fixture.gguf'}):
            session=self.load();args=self.commands[-1][1]
            self.assertEqual(args[args.index('--ubatch-size')+1],512)
            self.assertIn('--no-mmproj-offload',args)
            for changes in ({'mtp_draft_tokens':2},{'mtp_draft_tokens':8},{'vision_device':'gpu'},
                            {'backend':'vulkan'},{'context':262144},{'gpu_layers':20}):
                with self.subTest(changes=changes),self.assertRaises(ValueError):
                    self.load(self.settings|changes)
                self.assertTrue(session.alive())

    def test_orca_chain_closes_before_image_music_video_and_can_return(self):
        self.use_orca()
        self.test_chain_closes_llm_before_image_music_video_start_and_return()

    def test_orca_memory_estimate_is_distinct_and_does_not_reduce_context(self):
        self.use_orca()
        hw={'ram':{'free_mb':32000},'gpu':[{'vendor':'NVIDIA','name':'RTX 5070 Ti','free_mb':15000}]}
        self.assertEqual(accel.estimate(self.model,self.settings,hw)['status'],'ok')
        with patch('h3chat.hardware.detect_hardware',return_value=hw), patch.object(accel,'check_hardware',side_effect=real_check_hardware):
            accel.check_hardware(131072,'orca-iq3xxs')
            with self.assertRaisesRegex(ValueError,'VRAM'):accel.check_hardware(131072,'ista-iq3s')
            hw['gpu'][0]['free_mb']=14000
            with self.assertRaisesRegex(ValueError,'VRAM'):accel.check_hardware(131072,'orca-iq3xxs')
        estimate=accel.estimate(self.model,self.settings,hw)
        self.assertEqual(estimate['status'],'oom');self.assertEqual(estimate['recommended_patch'],{})

    def test_orca_presets_are_per_model_and_unverified_payload_is_rejected(self):
        selected=merge(self.settings,{'chat_model':'orca','llm_acceleration':'qwen27','context':131072,'mtp_draft_tokens':4})
        back=merge(selected,{'chat_model':'llm'})
        self.assertEqual(back['mtp_draft_tokens'],2)
        again=merge(back,{'chat_model':'orca'})
        self.assertEqual(again['mtp_draft_tokens'],4)
        self.use_orca()
        self.model['files'][0]['size']-=1
        self.assertFalse(accel.eligible(self.model))
        with self.assertRaisesRegex(ValueError,'verificato'):self.load()
        self.assertEqual(self.commands,[])

    def test_private_runtime_full_target_context_and_scoped_environment(self):
        with patch.dict(os.environ,{'QWEN27_MTP_Q4_VEC':'1','QWEN27_MTP_WINDOW':'1'}):
            session = self.load()
            args = self.commands[-1][1]
            self.assertEqual(args[0],self.exe)
            for option,value in {'--ctx-size':131072,'--batch-size':2048,
                                 '--ubatch-size':256,'--spec-draft-n-max':2,
                                 '--cache-type-k':'q4_0','--cache-type-v':'q4_0',
                                 '--host':'127.0.0.1','--spec-type':'draft-mtp'}.items():
                self.assertEqual(args[args.index(option)+1],value)
            self.assertEqual(session.child_env['QWEN27_MTP_WINDOW'],'8192')
            self.assertNotIn('QWEN27_MTP_Q4_VEC',session.child_env)
            self.assertEqual(os.environ['QWEN27_MTP_WINDOW'],'1')
            self.assertEqual(os.environ['QWEN27_MTP_Q4_VEC'],'1')
            self.assertEqual(args[args.index('--api-key')+1],session.api_key)
            self.assertTrue(all(req.get_header('Authorization')=='Bearer '+session.api_key for req in self.requests))
            self.assertIn('bozza 8K',session.snapshot()['acceleration'])

    def test_chain_closes_llm_before_image_music_video_start_and_return(self):
        for kind in ('image','music','video'):
            with self.subTest(kind=kind):
                llm = self.load();old = llm.process
                following = self.engine._activate(kind,self.catalog[kind],self.settings,self.root/(kind+'.log'),self.cancel)
                # This check is before launching/loading the next model, not after.
                self.assertTrue(old.ended);self.assertFalse(llm.alive())
                self.assertIsNone(following.child_env)
                self.assertEqual(len(self.engine.sessions),1)
                following.process = Process();following.ready = True
                next_process = following.process
                returned = self.load()
                self.assertTrue(next_process.ended)
                self.assertIsNot(returned,llm);self.assertTrue(returned.alive())
                self.engine.stop()
                self.assertTrue(returned.process is None or returned.process.ended)
                self.assertEqual(self.engine.snapshot()['models'],[])

    def test_reuse_sampling_then_standard_reloads_and_abort_releases(self):
        llm = self.load()
        self.assertIs(self.load(self.settings|{'max_tokens':512,'think_level':'high','temperature':1.2}),llm)
        self.assertEqual(len(self.commands),1)
        standard = self.load(self.settings|{'llm_acceleration':'standard'})
        self.assertFalse(llm.alive());self.assertIsNot(llm,standard)
        self.assertEqual(self.commands[-1][1][0],'standard/llama-server.exe')
        self.assertNotIn('QWEN27_MTP_WINDOW',standard.child_env)
        self.engine.abort_active();self.assertFalse(standard.alive())
        self.assertEqual(self.engine.snapshot()['models'],[])

    def test_context_or_runtime_fingerprint_changes_reload(self):
        first = self.load()
        second = self.load(self.settings|{'context':65536})
        self.assertFalse(first.alive());self.assertIsNot(first,second)
        folder = self.root/accel.FOLDER;folder.mkdir(parents=True)
        (folder/'manifest.json').write_text('{}')
        third = self.load(self.settings|{'context':65536})
        self.assertFalse(second.alive());self.assertIsNot(second,third)

    def test_invalid_options_do_not_drop_existing_chain_model(self):
        following = self.engine._activate('image',self.catalog['image'],self.settings,self.root/'image.log',self.cancel)
        following.process = Process();following.ready = True
        for changes in ({'mtp_draft_tokens':1},{'mtp_enabled':False},{'gpu_layers':20},
                        {'profile':'cpu'},{'backend':'vulkan'},{'context':262144}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                self.load(self.settings|changes)
            self.assertTrue(following.alive());self.assertEqual(self.commands,[])
        with patch.object(accel,'check_hardware',side_effect=ValueError('VRAM insufficiente')):
            with self.assertRaisesRegex(ValueError,'VRAM'):self.load()
        self.assertEqual(self.commands,[])

    def test_vision_uses_cpu_and_smaller_ubatch(self):
        files = {'model':str(self.path),'mmproj':'fixture-projector.gguf'}
        with patch.object(self.engine,'model_files',return_value=files):
            self.load()
            args = self.commands[-1][1]
            self.assertEqual(args[args.index('--ubatch-size')+1],128)
            self.assertIn('--no-mmproj-offload',args)
            with self.assertRaisesRegex(ValueError,'Vision CPU'):
                self.load(self.settings|{'vision_device':'gpu'})

    def test_sampling_omits_only_redundant_off_budget_and_preserves_low_budget(self):
        self.load()
        self.engine.active_model=self.model|{'thinking':{'supported':True,'mode':'native'}}
        for level in ('off','low'):
            captured=[]
            def response(req,**kwargs):
                captured.append(json.loads(req.data))
                return io.BytesIO(b'data: {"choices":[{"delta":{"content":"42"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n')
            with patch('h3chat.engine.urllib.request.urlopen',side_effect=response):
                self.engine.completion([],self.settings|{'think_level':level,'max_tokens':512},self.cancel,on_text=lambda _:None)
            if level=='off':self.assertNotIn('reasoning_budget_tokens',captured[0])
            else:
                self.assertEqual(captured[0]['reasoning_budget_tokens'],64)
                self.assertEqual(captured[0]['reasoning_effort'],'low')
        self.engine.active.acceleration=None
        with patch('h3chat.engine.urllib.request.urlopen',side_effect=response):
            self.engine.completion([],self.settings|{'think_level':'off','max_tokens':512},self.cancel,on_text=lambda _:None)
        self.assertEqual(captured[-1]['reasoning_budget_tokens'],0)

    def test_resident_policy_is_unchanged(self):
        settings = self.settings|{'memory_policy':'resident'}
        llm = self.load(settings)
        following = self.engine._activate('image',self.catalog['image'],settings,self.root/'image.log',self.cancel)
        following.process = Process();following.ready = True
        self.assertTrue(llm.alive());self.assertEqual(len(self.engine.sessions),2)
        self.engine.stop();self.assertFalse(llm.alive());self.assertFalse(following.alive())

    def test_per_model_opt_in_preserves_previous_settings_and_queue_snapshot(self):
        saved = DEFAULTS|{'chat_model':'llm','context':50000,'mtp_enabled':True,'mtp_draft_tokens':1}
        selected = merge(saved,{'llm_acceleration':'qwen27','context':131072,'mtp_draft_tokens':2})
        other = merge(selected,{'chat_model':'other'})
        self.assertEqual(other['llm_acceleration'],'standard')
        back = merge(other,{'chat_model':'llm'})
        self.assertEqual(back['llm_acceleration'],'qwen27');self.assertEqual(back['mtp_draft_tokens'],2)
        self.assertEqual(saved['context'],50000);self.assertEqual(saved['mtp_draft_tokens'],1)
        self.assertEqual(saved['llm_acceleration'],'standard')
        store = Store(self.root/'queue-fixture')
        store.save_settings(saved)
        chat = store.create_chat()
        jid = store.enqueue(chat['id'],'fixture',[],selected)
        store.save_settings(saved)
        queued = json.loads(store.one('SELECT payload FROM jobs WHERE id=?',(jid,))['payload'])['settings']
        self.assertEqual(queued['llm_acceleration'],'qwen27')
        self.assertEqual((queued['context'],queued['mtp_draft_tokens']),(131072,2))
        self.assertEqual(store.settings()['llm_acceleration'],'standard')
        with self.assertRaises(ValueError):validate({'llm_acceleration':'unknown'})

    def test_changed_model_size_is_rejected_before_start(self):
        with patch.object(accel,'_model_size',return_value=self.path.stat().st_size):
            with self.assertRaisesRegex(ValueError,'incompleto'):self.load()
        self.assertEqual(self.commands,[])

    def test_hybrid_estimate_and_memory_guards(self):
        hw = {'ram':{'free_mb':32000},'gpu':[{'vendor':'NVIDIA','name':'RTX 5080','free_mb':16000}]}
        estimate = accel.estimate(self.model,self.settings,hw)
        self.assertEqual(estimate['status'],'ok')
        self.assertLess(estimate['vram_gb'],16)
        hw['gpu'][0]['free_mb'] = 15000
        estimate = accel.estimate(self.model,self.settings,hw)
        self.assertEqual(estimate['status'],'oom');self.assertEqual(estimate['recommended_patch'],{})

    def test_owned_warm_image_is_released_before_real_accelerator_memory_guard(self):
        from unittest.mock import Mock
        self.settings.update(context=80000,ram_cache_gb=16)
        self.catalog['image']['engine']='vision'
        image=self.engine._activate('image',self.catalog['image'],self.settings,self.root/'image.log',self.cancel)
        image.process=Process();image.ready=True;image.worker_backend='cuda';image.send=Mock();image.wait=Mock()
        before={'ram':{'free_mb':11000},'gpu':[{'vendor':'NVIDIA','name':'RTX 5070 Ti','free_mb':14600}]}
        after={'ram':{'free_mb':32000},'gpu':[{'vendor':'NVIDIA','name':'RTX 5070 Ti','free_mb':15600}]}
        with patch('h3chat.hardware.detect_hardware',side_effect=[before,after]),patch.object(accel,'check_hardware',side_effect=real_check_hardware):
            session=self.load()
        self.assertFalse(image.alive());self.assertIsNone(self.engine.warm_image)
        self.assertTrue(session.ready);self.assertEqual(len(self.commands),1)
        args=self.commands[0][1];self.assertEqual(args[args.index('--ctx-size')+1],80000)
        self.assertEqual(self.settings['ram_cache_gb'],16)


class RuntimeVerificationTests(unittest.TestCase):
    def test_small_desktop_fluctuation_warns_but_larger_shortage_remains_blocked(self):
        from unittest.mock import Mock
        hw={'ram':{'free_mb':32000},'gpu':[{'vendor':'NVIDIA','name':'RTX 5070 Ti','free_mb':14623}]};stage=Mock()
        with patch('h3chat.hardware.detect_hardware',return_value=hw):
            accel.check_hardware(80000,stage=stage)
            stage.assert_called_once();self.assertIn('80000 invariato',stage.call_args.args[0])
            required=accel.required_free_mib(80000)
            hw['gpu'][0]['free_mb']=required-accel.PREFLIGHT_TOLERANCE_MIB
            accel.check_hardware(80000)
            hw['gpu'][0]['free_mb']-=1
            with self.assertRaisesRegex(ValueError,'differenza 129 MiB'):accel.check_hardware(80000)
    def test_context_guard_subtracts_only_exact_q4_target_cache_saving(self):
        self.assertEqual(accel.required_free_mib(131072),15550)
        self.assertEqual(accel.required_free_mib(65536),14398)
        self.assertEqual(accel.required_free_mib(16384),13534)
        for context in (0,1024,262144,True):
            with self.assertRaises(ValueError):accel.required_free_mib(context)
    def test_standard_search_cannot_pick_private_accelerator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            standard = root/'runtime/cuda/llama/llama-server.exe'
            private = root/accel.FOLDER/'llama-server.exe'
            for exe in (standard,private):
                exe.parent.mkdir(parents=True,exist_ok=True);exe.write_bytes(b'fixture')
            self.assertEqual(runtime_executable(root,'cuda','llama'),standard)

    def test_cold_start_checks_gpu_architecture_vram_and_ram_without_loading(self):
        hw = {'ram':{'free_mb':32000},'gpu':[{'vendor':'NVIDIA','name':'RTX 5080','free_mb':16000}]}
        with patch('h3chat.hardware.detect_hardware',return_value=hw):
            accel.check_hardware()
            hw['gpu'][0]['free_mb'] = 15000
            with self.assertRaisesRegex(ValueError,'VRAM'):accel.check_hardware()
            accel.check_hardware(65536)
            hw['gpu'][0]['free_mb'] = 16000;hw['ram']['free_mb'] = 15000
            with self.assertRaisesRegex(ValueError,'RAM'):accel.check_hardware()
            hw['ram']['free_mb'] = 32000;hw['gpu'][0]['name'] = 'RTX 4090'
            with self.assertRaisesRegex(ValueError,'RTX 50'):accel.check_hardware()

    def test_attestation_rejects_changed_or_missing_private_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);folder = root/accel.FOLDER;folder.mkdir(parents=True)
            hashes = {}
            for name in accel.RUNTIME_FILES:
                data = name.encode();(folder/name).write_bytes(data)
                hashes[name] = hashlib.sha256(data).hexdigest()
            (folder/'manifest.json').write_text(json.dumps({'profile':'qwen27-iq3s-mtp2-window8k','sha256':hashes}))
            self.assertEqual(accel._verified(str(folder),accel.stamp(root)),str(folder/'llama-server.exe'))
            (folder/'llama-common.dll').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'modificata'):accel._verified(str(folder),accel.stamp(root))
            (folder/'ggml-cuda.dll').unlink()
            with self.assertRaises(ValueError):accel._verified(str(folder),accel.stamp(root))

    def test_environment_is_not_global_or_inherited_by_standard(self):
        with patch.dict(os.environ,{'QWEN27_MTP_WINDOW':'64','QWEN27_MTP_Q4_VEC':'1'}):
            env = accel.child_environment({'exe':'private/llama-server.exe','window':8192})
            self.assertEqual(env['QWEN27_MTP_WINDOW'],'8192')
            self.assertNotIn('QWEN27_MTP_WINDOW',accel.child_environment())
            self.assertEqual(os.environ['QWEN27_MTP_WINDOW'],'64')

    def test_unknown_and_unverified_orca_models_never_auto_enable(self):
        for model in ({},{'identity':None,'parameters':None,'files':[]},
                      {'files':[{'role':'model','path':'Orca-IQ3_XXS.gguf','size':10442846464}]}):
            self.assertFalse(accel.eligible(model))

    def test_session_passes_child_environment_to_owned_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Session((), 'chat', {'id':'llm','name':'llm'}, {}, {}, Path(tmp)/'session.log')
            s.child_env = {'PATH':'private-runtime','QWEN27_MTP_WINDOW':'8192'}
            with patch('h3chat.residency.subprocess.Popen',return_value=Process()) as spawn:
                s.start(['private/llama-server.exe'])
                self.assertEqual(spawn.call_args.kwargs['env'],s.child_env)
                owned = s.process;s.stop();self.assertTrue(owned.ended)


if __name__ == '__main__': unittest.main()
