import json
import os
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from h3chat.engine import Engine
from h3chat.hardware import assess_model
from h3chat.image_options import configured, options, validate_overrides
from h3chat.loras import LoraLibrary, for_model, public, validate_directories
from h3chat.service import Service
from h3chat.store import DEFAULTS
from test_external_models import safetensors

ROOT=Path(__file__).resolve().parents[1]

def lora(path,family='anima'):
    header={'__metadata__':{'ss_base_model_version':family},
            'layer.lora_down.weight':{'dtype':'F16','shape':[1,1],'data_offsets':[0,2]},
            'layer.lora_up.weight':{'dtype':'F16','shape':[1,1],'data_offsets':[2,4]}}
    raw=json.dumps(header).encode();path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(struct.pack('<Q',len(raw))+raw+b'\0'*4);return path

class LoraTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.a=lora(self.root/'first/sub/同名.safetensors')
        self.b=lora(self.root/'second/同名.safetensors','flux.2')
        self.dirs=[str(self.root/'first'),str(self.root/'second')]
        self.lib=LoraLibrary()
        self.models={name:{'id':name,'name':name,'architecture':arch,'capabilities':caps} for name,arch,caps in
                     [('anima','anima',['create']),('flux','flux2',['create','edit']),('llm','qwen3',['chat'])]}

    def tearDown(self):self.tmp.cleanup()

    def selection(self,family='anima',**patches):
        item=next(i for i in self.lib.scan(self.dirs)['items'] if i['family']==family)
        return {'id':item['id'],'weight':1,'model_id':'anima'}|patches

    def test_multiple_recursive_directories_exclude_non_loras_and_keep_originals(self):
        before={p:p.read_bytes() for p in (self.a,self.b)}
        safetensors(self.root/'first/not-a-lora.safetensors')
        (self.root/'second/invalid.safetensors').write_bytes(b'broken')
        result=self.lib.scan(self.dirs+[self.dirs[0]],True)
        self.assertEqual(len(result['items']),2)
        self.assertEqual(len({i['id'] for i in result['items']}),2)
        self.assertEqual({i['family'] for i in result['items']},{'anima','flux2'})
        self.assertEqual({Path(i['path']) for i in result['items']},{self.a,self.b})
        self.assertTrue(all(p.read_bytes()==data for p,data in before.items()))

    def test_unknown_family_is_explicit_and_incompatible_family_is_rejected(self):
        unknown=lora(self.root/'first/unknown.safetensors','')
        item=next(i for i in self.lib.scan(self.dirs,True)['items'] if i['path']==str(unknown))
        self.assertIn('non dichiarata',item['note'])
        self.assertEqual(len(self.lib.capture([{'id':item['id'],'model_id':'anima'}],self.dirs,self.models)),1)
        with self.assertRaisesRegex(ValueError,'incompatibile'):
            self.lib.capture([self.selection('flux2')],self.dirs,self.models)

    def test_only_indexed_ids_image_targets_and_valid_weights_are_accepted(self):
        valid=self.selection()
        for choices in ([valid|{'path':str(self.a)}],[valid|{'id':'missing'}],[valid|{'model_id':'llm'}],
                        [valid|{'weight':True}],
                        [valid|{'weight':float('nan')}],[valid|{'weight':2.1}],[valid,valid],[valid]*9):
            with self.subTest(choices=choices),self.assertRaises(ValueError):self.lib.capture(choices,self.dirs,self.models)
        self.assertEqual(self.lib.capture([valid|{'weight':-1.5}],self.dirs,self.models)[0]['weight'],-1.5)

    def test_per_model_routing_zero_weight_and_queued_file_change(self):
        selections=[self.selection(),self.selection('flux2',model_id='flux',weight=.6)]
        captured=self.lib.capture(selections,self.dirs,self.models)
        self.assertEqual([i['weight'] for i in for_model(captured,self.models['flux'])],[.6])
        self.assertEqual(for_model([captured[0]|{'weight':0}],self.models['anima']),[])
        self.assertNotIn('path',public(captured)[0])
        self.a.write_bytes(self.a.read_bytes()+b'\0')
        with self.assertRaisesRegex(ValueError,'cambiato'):for_model(captured,self.models['anima'])
        with self.assertRaisesRegex(ValueError,'cambiato'):self.lib.capture(selections,self.dirs,self.models)

    def test_missing_and_disconnected_files_are_reported_without_blocking_preferences(self):
        selection=self.selection();self.a.unlink()
        with self.assertRaisesRegex(ValueError,'assente'):self.lib.capture([selection],self.dirs,self.models)
        missing=str(self.root/'offline')
        self.assertEqual(validate_directories([missing,missing]),[missing])
        self.assertIn('non disponibile',self.lib.scan([missing],True)['warnings'][0])
        with self.assertRaises(ValueError):validate_directories([str(self.b)])

    def test_bounds_and_malformed_headers(self):
        (self.root/'first/huge.safetensors').write_bytes(struct.pack('<Q',2**50)+b'{}')
        folders=self.dirs+[str(self.root/'missing')]*20
        with self.assertRaises(ValueError):validate_directories(folders)
        self.assertEqual(len(self.lib.scan(self.dirs,True)['items']),2)

class ImageOptionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name).resolve()
        self.app=Service(ROOT,self.base/'data',start_worker=False)
        files={role:str(safetensors(self.base/(role+'.safetensors'))) for role in ('diffusion','llm','vae')}
        self.model=self.app.external_model({'profile':'anima-turbo','name':'Anima test','files':files})

    def tearDown(self):self.app.close();self.tmp.cleanup()

    def test_anima_requires_all_components_and_has_correct_capability_and_defaults(self):
        self.assertEqual(self.model['capabilities'],['create']);self.assertEqual(self.model['max_refs'],0)
        self.assertEqual((configured(self.model,DEFAULTS)['steps'],configured(self.model,DEFAULTS)['cfg']),(8,1))
        cfg={k:v for k,v in self.model['external_config'].items() if k not in ('steps','cfg')}|{'profile':'anima'}
        base=self.app.external_model(cfg)
        self.assertEqual((base['steps'],base['cfg']),(30,4))
        with self.assertRaises(ValueError):self.app.external_model({'profile':'anima','files':{'diffusion':cfg['files']['diffusion']}})

    def test_per_model_overrides_seed_and_hidden_advanced_keep_actual_values(self):
        mid=self.model['id'];override={'width':768,'steps':12,'cfg':1.5,'sampler':'heun','scheduler':'simple','seed':456,'negative_prompt':'blur'}
        settings=DEFAULTS|{'steps':22,'image_overrides':{mid:override},'image_advanced':False,'chat_advanced':False}
        resolved=options(self.model,settings)
        for k,v in override.items():self.assertEqual(resolved[k],v)
        self.assertEqual(options(self.model,settings|{'image_advanced':True,'chat_advanced':True}),resolved)
        auto=options(self.model,DEFAULTS)
        self.assertEqual(auto['sampler'],'euler');self.assertGreaterEqual(auto['seed'],0)
        self.assertNotEqual(options(self.model,DEFAULTS)['seed'],auto['seed'])
        self.app.save_settings({'image_overrides':{mid:override}})
        self.assertEqual(self.app.store.settings()['image_overrides'][mid],override)

    def test_invalid_overrides_and_flags_fail_before_inference(self):
        for invalid in ({'width':257},{'steps':True},{'cfg':float('nan')},{'sampler':'invalid'},
                        {'scheduler':'invalid'},{'seed':-2},{'negative_prompt':[]},{'path':'any'}):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):validate_overrides({'model':invalid})
        for invalid in ({'image_advanced':'yes'},{'chat_advanced':1},{'image_cfg':float('nan')}):
            with self.assertRaises(ValueError):self.app.validate_settings(invalid)

    def test_loras_and_parameters_reach_native_request_and_empty_list_clears_them(self):
        engine=self.app.engine
        settings=DEFAULTS|{'seed':99,'negative_prompt':'blur','image_sampler':'heun','image_scheduler':'simple',
                         '_loras':[{'path':str(self.base/'original.safetensors'),'weight':.75}]}
        req=engine.image_request(self.model,settings,'cat',[],self.base/'out.png')
        self.assertNotIn('flow_shift',req)
        self.assertNotIn('flow_shift',options(self.model|{'architecture':'flux2'},DEFAULTS))
        self.assertEqual(options(self.model|{'architecture':'qwen-edit'},DEFAULTS)['flow_shift'],3)
        self.assertEqual(req['loras'],[{'path':str(self.base/'original.safetensors'),'weight':.75}])
        self.assertEqual((req['seed'],req['sampler'],req['scheduler'],req['negative_prompt']),(99,'heun','simple','blur'))
        self.assertEqual(engine.image_request(self.model,DEFAULTS,'cat',[],self.base/'out.png')['loras'],[])
        self.assertEqual(engine.session_key('image',self.model,settings),engine.session_key('image',self.model,DEFAULTS))

    def test_routed_job_keeps_snapshot_and_records_only_applied_adapters(self):
        path=lora(self.base/'loras/style.safetensors');dirs=[str(path.parent)]
        item=self.app.loras.scan(dirs)['items'][0]
        selection={'id':item['id'],'weight':.8,'model_id':self.model['id']}
        captured=self.app.loras.capture([selection],dirs,self.app.catalog)
        chat=self.app.store.create_chat();settings=DEFAULTS|{'create_model':self.model['id'],'seed':42,'_assistant':False}
        jid=self.app.store.enqueue(chat['id'],'Crea una immagine di un gatto',[],settings,loras=captured)
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(jid,))
        self.assertEqual(json.loads(job['payload'])['loras'][0]['path'],str(path))
        media={'id':jid,'path':'test.png','mime':'image/png','name':'test.png','generation':{'sampler':'euler','scheduler':'discrete','seed':42}}
        with patch.object(self.app.engine,'require_model',return_value=self.model),patch.object(self.app.engine,'generate',return_value=media) as generate:
            self.app.execute_job(job,threading.Event())
        self.assertEqual(generate.call_args.args[1]['_loras'][0]['weight'],.8)
        messages=self.app.store.messages(chat['id'])
        self.assertNotIn('path',messages[0]['meta']['loras'][0])
        self.assertEqual(messages[-1]['meta']['image_parameters']['scheduler'],'discrete')
        self.assertEqual(messages[-1]['meta']['loras'][0]['weight'],.8)

    def test_memory_estimate_includes_loras_and_per_model_resolution(self):
        hardware={'ram':{'free_mb':32000,'total_mb':40000},'gpu':[]}
        settings=DEFAULTS|{'profile':'cpu','backend':'cpu'}
        normal=assess_model(self.model,settings,hardware)
        larger=assess_model(self.model|{'active_lora_bytes':1024**3},settings|{'image_overrides':{self.model['id']:{'width':1024,'height':1024}}},hardware)
        self.assertGreater(larger['ram_gb'],normal['ram_gb']+2)

if __name__=='__main__':unittest.main()
