import json,struct,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from h3chat.external_models import validate_config,build_model,suggest
from h3chat.fibo2 import pipeline_root,prompt,negative,NEGATIVE_EDIT
from h3chat.image_options import options
from h3chat.store import DEFAULTS
from h3chat.visual_routing import image_brief


def weight(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    header=json.dumps({'w':{'dtype':'BF16','shape':[1],'data_offsets':[0,2]}}).encode()
    path.write_bytes(struct.pack('<Q',len(header))+header+b'\0\0')


class FiboTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.files={k:str(self.root/p) for k,p in {'diffusion':'transformer/diffusion_pytorch_model-00001-of-00002.safetensors','llm':'text_encoder/model.safetensors','vae':'vae/diffusion_pytorch_model.safetensors'}.items()}
        for p in self.files.values():weight(Path(p))
        weight(self.root/'transformer/diffusion_pytorch_model-00002-of-00002.safetensors')
        for name in ('model_index.json','transformer/config.json','transformer/diffusion_pytorch_model.safetensors.index.json','text_encoder/config.json','processor/processor_config.json','processor/tokenizer.json','processor/tokenizer_config.json','processor/chat_template.jinja','vae/config.json','scheduler/scheduler_config.json','fonts/Aileron-Regular.otf','fonts/DejaVuSans.ttf'):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps({'_class_name':'BriaFibo2Pipeline'}) if name=='model_index.json' else '{}')
        self.config={'profile':'fibo2','name':'FIBO prova','files':self.files}

    def test_registration_checks_both_shards_processor_and_companions_without_copying(self):
        saved=validate_config(self.config);model=build_model(saved)
        self.assertEqual((model['architecture'],model['engine'],model['max_refs']),('fibo2','fibo2',4))
        self.assertEqual(model['capabilities'],['create','edit']);self.assertGreater(len(model['files']),10)
        from h3chat.models import model_path
        for entry in model['files']:self.assertTrue(model_path(self.root,model,entry['path']).is_absolute())
        with self.assertRaises(ValueError):model_path(self.root,model,str(self.root/'unregistered.json'))
        self.assertEqual(model['steps'],50);self.assertEqual(model['cfg'],5)
        suggested=suggest({'profile':'fibo2','path':self.files['diffusion']})
        self.assertEqual(suggested['files']['llm'],self.files['llm'])
        (self.root/'transformer/diffusion_pytorch_model-00002-of-00002.safetensors').unlink()
        with self.assertRaises(ValueError):validate_config(self.config)

    def test_foreign_encoder_and_wrong_pipeline_rejected(self):
        with self.assertRaisesRegex(ValueError,'stessa cartella'):pipeline_root(self.files|{'llm':str(self.root/'elsewhere.safetensors')})
        (self.root/'model_index.json').write_text('{"_class_name":"UnrelatedPipeline"}')
        with self.assertRaisesRegex(ValueError,'Manifest'):validate_config(self.config)

    def test_int8_registration_keeps_both_quantized_components_and_small_assets(self):
        main=self.root/'diffusion_models/fibo2_dev_int8_convrot.safetensors'
        encoder=self.root/'text_encoders/qwen3vl_4b_int8_convrot.safetensors'
        weight(main);weight(encoder)
        config=self.config|{'profile':'fibo2-int8','files':{'diffusion':str(main),'llm':str(encoder),'vae':self.files['vae']}}
        model=build_model(validate_config(config))
        self.assertEqual(model['quantization'],'int8_convrot')
        self.assertEqual(model['engine'],'fibo2')
        self.assertFalse(any('00002-of' in f['path'] for f in model['files']))
        with self.assertRaisesRegex(ValueError,'profilo'):validate_config(config|{'profile':'fibo2'})

    def test_official_size_grid_seed_and_prompt_controls_win(self):
        model=build_model(validate_config(self.config));p=options(model,DEFAULTS,'1424x800 seed 42 passi 30 CFG 4')
        self.assertEqual([p[k] for k in ('width','height','seed','steps','cfg')],[1424,800,42,30,4])
        self.assertFalse(p['preserve_reference_aspect'])
        p=options(model,DEFAULTS,'9:16 1 MP');self.assertEqual(p['width']%16,0);self.assertEqual(p['height']%16,0);self.assertLess(p['width'],p['height'])
        with self.assertRaisesRegex(ValueError,'scheduler'):options(model,DEFAULTS,'scheduler karras')
        with self.assertRaisesRegex(ValueError,'multipli di 16'):options(model,DEFAULTS,'1500x1500')

    def test_normal_prompt_and_explicit_structured_edit_need_no_external_assistant(self):
        self.assertEqual(prompt('Una bicicletta rossa'),'Una bicicletta rossa')
        caption='{"short_description":"Una bicicletta","objects":[]}'
        self.assertEqual(json.loads(prompt(caption))['short_description'],'Una bicicletta')
        with self.assertRaisesRegex(ValueError,'edit_instruction'):prompt(caption,editing=True)
        self.assertIn('edit_instruction',prompt('{"edit_instruction":"red jacket"}',True))
        self.assertEqual(negative('',True),NEGATIVE_EDIT)
        self.assertEqual(json.loads(negative('blurry'))['short_description'],'blurry')
        instructions,schema=image_brief({'architecture':'fibo2'})
        self.assertIn('edit_instruction',instructions);self.assertIn('location',instructions)
        self.assertEqual(schema['required'],['prompt'])

    def test_engine_dispatches_private_worker_instead_of_shared_vision_runtime(self):
        from h3chat.engine import Engine
        engine=Engine(Path(__file__).resolve().parents[1],self.tmp.name,{})
        session=Mock();session.ready=False
        with patch.object(engine,'_activate',return_value=session),patch('h3chat.fibo2_engine.start',return_value=session) as launch,patch.object(engine,'start_vision') as vision:
            result=engine.start_image({'engine':'fibo2'},DEFAULTS,self.root/'test.log',threading.Event(),stage=Mock())
        self.assertIs(result,session);launch.assert_called_once();vision.assert_not_called()

    def test_fibo_releases_idle_vision_worker_before_loading_large_cpu_weights(self):
        from h3chat.engine import Engine
        model=build_model(validate_config(self.config))
        engine=Engine(Path(__file__).resolve().parents[1],self.tmp.name,{model['id']:model})
        warm=Mock();engine.warm_image=warm
        old=Mock();old.model={'name':'Other model'};engine.sessions={'old':old}
        with patch.object(engine,'configure'),patch.object(engine,'_drop',side_effect=lambda key,**kw:engine.sessions.pop(key)) as drop:
            engine._activate('image',model,DEFAULTS,self.root/'test.log',threading.Event())
        drop.assert_called_once_with('old',keep_warm=False)
        warm.stop.assert_called_once();self.assertIsNone(engine.warm_image)

    def test_offload_is_per_model_and_changing_it_requires_a_new_session(self):
        from h3chat.engine import Engine
        model=build_model(validate_config(self.config));engine=Engine(self.root,self.tmp.name,{})
        base=engine.session_key('image',model,DEFAULTS)
        grouped=DEFAULTS|{'image_overrides':{model['id']:{'fibo_offload':'group'}}}
        self.assertEqual(options(model,grouped)['fibo_offload'],'group')
        self.assertNotEqual(base,engine.session_key('image',model,grouped))
        from h3chat.image_options import validate_overrides
        full={model['id']:{'fibo_offload':'full'}}
        validate_overrides(full,{model['id']:model})
        self.assertEqual(options(model,DEFAULTS|{'image_overrides':full})['fibo_offload'],'full')
        self.assertNotEqual(base,engine.session_key('image',model,DEFAULTS|{'image_overrides':full}))
        with self.assertRaises(ValueError):validate_overrides({'other':{'fibo_offload':'full'}},{'other':{'architecture':'moss'}})


if __name__=='__main__':unittest.main()
