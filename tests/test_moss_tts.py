import copy,json,tempfile,threading,unittest,wave,importlib.util
from pathlib import Path
from unittest.mock import Mock,patch
from h3chat import voice_engines
from h3chat.voice import DEFAULTS,configuration,synthesize,validate_fields
from h3chat.moss_tts import validate_params,resolve,instruction,spoken

class MossTests(unittest.TestCase):
    def test_voice_design_is_request_local_and_pause_is_native_markup(self):
        custom='A mature Italian female voice, incredulous then relieved with a nervous laugh.'
        from h3chat.moss_tts import CODEC_QUALITIES
        self.assertEqual(CODEC_QUALITIES['full'],('fp32','fp32'))
        self.assertEqual(CODEC_QUALITIES['official'],('fp32','bf16'))
        validate_params({'codec_quality':'full','target_seconds':22.})
        validate_params({'instruction':custom,'reference_mode':'none'})
        self.assertEqual(instruction({'emotion':'neutral'},custom),custom)
        self.assertEqual(spoken('Dimmi che scherzi. [pausa] Ahahah!'),'Dimmi che scherzi. [pause 0.8s] Ahahah!')
        self.assertEqual(spoken('Una [pause 1.2s] pausa.'),'Una [pause 1.2s] pausa.')
        settings=copy.deepcopy(DEFAULTS);settings['_voice_fields']={'engine':'moss','params':{'moss':{'instruction':custom,'reference_mode':'none','seed':345}}}
        settings['voice_references']['female']={'path':'missing-reference.wav','transcript':'Originale'}
        with patch('h3chat.moss_tts.resolve',side_effect=lambda p,*a:p):
            from h3chat.moss_tts import configuration as config
            cfg,identity=config('.',settings,{'gender':'female'})
        self.assertEqual(identity['reference'],'');self.assertIn('345',identity['id']);self.assertEqual(cfg['instruction'],custom)
        self.assertEqual(settings['voice_references']['female']['path'],'missing-reference.wav')
        for bad in ({'instruction':'x'*2001},{'reference_mode':'auto'}):
            with self.assertRaises(ValueError):validate_params(bad)
    def test_alternative_is_opt_in_and_retires_only_old_engines(self):
        self.assertEqual(voice_engines.selected(DEFAULTS),'higgs')
        self.assertEqual(voice_engines.selected(DEFAULTS|{'_voice_fields':{'engine':'moss'}}),'moss')
        self.assertEqual(voice_engines.normalize({'voice_engine':'moss'})['voice_engine'],'moss')
        self.assertEqual(voice_engines.normalize({'voice_engine':'qwen'})['voice_engine'],'higgs')
        value={'engine':'moss','params':{'moss':{'temperature':1.7,'language':'Italian','seed':123}}}
        self.assertEqual(validate_fields(value),value)
        for wrong in ({'temperature':True},{'top_k':2.5},{'top_p':2},{'language':'invented'},{'precision':'4bit'},{'url':'https://invalid.invalid'}):
            with self.subTest(wrong=wrong),self.assertRaises(ValueError):validate_params(wrong)

    def test_config_keeps_higgs_paths_and_sampling_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ref=root/'ref.wav';ref.write_bytes(b'fixture')
            settings=copy.deepcopy(DEFAULTS);settings.update(voice_moss_model_path='moss-model',voice_moss_codec_path='moss-codec',voice_references={'female':{'path':str(ref),'transcript':'Testo'},'male':{'path':'','transcript':''}},_voice_fields={'engine':'moss','delivery':'warm','params':{'moss':{'temperature':1.9,'seed':123,'language':'French'}}})
            before=copy.deepcopy(settings)
            with patch('h3chat.voice.runtime_ready',return_value=True),patch('h3chat.moss_tts.resolve',side_effect=lambda p,*a:p):
                cfg,choice,acting,identity=configuration(root,settings,'')
            self.assertEqual(cfg['model_path'],'moss-model');self.assertEqual(cfg['temperature'],1.9);self.assertEqual(cfg['language'],'French');self.assertEqual(cfg['seed'],123)
            self.assertEqual(acting['tags'],[]);self.assertIn('Warm',acting['instruction']);self.assertEqual(settings,before)
            app=Mock(root=root,data=root);app.engine.tool_call.return_value={'duration':3};meta={}
            with patch('h3chat.voice.configuration',return_value=(cfg,choice,acting,identity)):
                synthesize(app,root/'out',[{'text':'Una frase.'}],settings,'',threading.Event(),lambda _:None,root/'log',meta)
            request=app.engine.tool_call.call_args.args[1];self.assertEqual(request['segments'][0]['spoken'],'Una frase.');self.assertNotIn('<|',request['segments'][0]['spoken']);self.assertEqual(meta['voice_parameters']['n_vq'],12)

    def test_reject_wrong_generation_and_incomplete_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);(folder/'config.json').write_text(json.dumps({'model_type':'moss_tts_local','sampling_rate':48000,'n_vq':12}))
            with self.assertRaises(ValueError):resolve(tmp)
            (folder/'model.safetensors').write_bytes(b'fixture');self.assertEqual(resolve(tmp),tmp)
            (folder/'config.json').write_text(json.dumps({'model_type':'moss_tts_local','sampling_rate':24000,'n_vq':8}))
            with self.assertRaises(ValueError):resolve(tmp)
