import copy,json,tempfile,threading,unittest,wave
from pathlib import Path
from unittest.mock import patch
from h3chat.music_options import DEFAULTS,capture_duration,duration,options,validate,worker_options
from h3chat.music_engine import MusicEngine
from h3chat.store import Store


class DurationTests(unittest.TestCase):
 def test_disabled_preserves_legacy_and_custom_limits(self):
  self.assertIsNone(DEFAULTS['max_duration'])
  for overrides in ({},{'max_duration':None},{'semantic_max_tokens':4500,'num_inference_steps':60}):
   selected=options({'id':'song'},{'music_overrides':{'song':overrides}})
   self.assertNotIn('max_duration',selected)
   self.assertEqual(worker_options(selected),selected)
   self.assertEqual(selected['semantic_max_tokens'],overrides.get('semantic_max_tokens',9000))

 def test_real_generation_budget_and_short_durations(self):
  for seconds,frames in ((.04,1),(4,100),(30,750),(360,9000),(600,15000),(900,22500)):
   selected=validate({'max_duration':seconds,'num_inference_steps':60})
   effective=worker_options(selected)
   self.assertEqual(effective['max_duration'],seconds)
   self.assertEqual(effective['semantic_max_tokens'],frames)
   self.assertLessEqual(effective['semantic_min_tokens'],frames)
   self.assertEqual(effective['num_inference_steps'],60)
   self.assertEqual(selected['semantic_max_tokens'],9000)

 def test_invalid_values_rejected_without_coercion(self):
  for value in (True,False,0,-1,.03,900.01,'60',[],{},float('nan'),float('inf')):
   with self.subTest(value=value),self.assertRaises(ValueError):validate({'max_duration':value})
  self.assertIsNone(duration(None))

 def test_request_overrides_effective_quality_model_without_mutation(self):
  from h3chat.music_quality import capture
  settings={'music_model':'q8','music_quality':'model','music_quality_profiles':{'high':{'model':'bf16','steps':60},'low':{'model':'q8','steps':32}},'music_overrides':{'bf16':{'max_duration':60}}}
  original=copy.deepcopy(settings)
  selected=capture_duration(capture(settings,'high'),90)
  self.assertEqual(selected['music_overrides']['bf16']['max_duration'],90)
  self.assertEqual(selected['music_overrides']['bf16']['num_inference_steps'],60)
  self.assertEqual(settings,original)
  inherited=capture_duration(settings,None)
  self.assertEqual(inherited['music_overrides']['bf16']['max_duration'],60)

 def test_queue_regenerate_and_reuse_keep_optional_choice(self):
  with tempfile.TemporaryDirectory() as temp:
   store=Store(temp);chat=store.create_chat()
   captured=capture_duration({'music_model':'song','music_overrides':{}},45)
   job=store.enqueue(chat['id'],'canzone',[],captured)
   store.save_settings({'music_overrides':{'song':{'max_duration':120}}})
   store.execute("UPDATE jobs SET status='done' WHERE id=?",(job,))
   retry=store.regenerate(chat['id'])
   payload=json.loads(store.one('SELECT payload FROM jobs WHERE id=?',(retry,))['payload'])
   self.assertEqual(payload['settings']['music_overrides']['song']['max_duration'],45)
   self.assertEqual(store.chat(chat['id'])['messages'][0]['meta']['music_max_duration'],45)

 def test_native_request_has_duration_and_budget_never_in_text(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);engine=MusicEngine();engine.data=root
   class Session:
    uses=0;files={};log_path=root/'engine.log'
    def send(self,request):
     self.request=request
     with wave.open(request['output'],'wb') as audio:
      audio.setparams((1,2,48000,0,'NONE','not compressed'));audio.writeframes(b'\0\0'*480)
    def wait(self,*args):return {}
   session=Session();engine.start_music=lambda *a,**k:session
   composition={'title':'Test','style':'Italian pop','lyrics':'[Verse]\nCiao sole','abc':'','instrumental':False}
   original=copy.deepcopy(composition)
   result=engine.generate_music({'id':'song','name':'YuE2'},capture_duration({'music_model':'song'},30),composition,'test',threading.Event(),lambda _:None)
   request=session.request
   self.assertEqual(request['options']['max_duration'],30)
   self.assertEqual(request['options']['semantic_max_tokens'],750)
   self.assertEqual(request['lyrics'],original['lyrics']);self.assertEqual(request['style'],original['style'])
   self.assertEqual(composition,original)
   self.assertEqual(result['generation']['max_duration'],30)
   self.assertEqual(json.loads((root/'outputs/test/composition.json').read_text())['parameters']['max_duration'],30)

 def test_service_captures_duration_with_assistant_off_and_automatic_route(self):
  from test_music import MusicTests
  fixture=MusicTests();fixture.setUp()
  try:
   for explicit in (True,False):
    chat=fixture.app.store.create_chat()
    job=fixture.app.send(chat['id'],{'prompt':'crea una canzone','music':explicit,'assistant':False,'music_max_duration':40})['job_id']
    settings=json.loads(fixture.app.store.one('SELECT payload FROM jobs WHERE id=?',(job,))['payload'])['settings']
    self.assertEqual(settings['music_overrides'][fixture.model['id']]['max_duration'],40)
    self.assertNotIn('max_duration',settings['_music_fields'])
    fixture.app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(job,))
   fixture.app.save_settings({'music_overrides':{fixture.model['id']:{'max_duration':90}}})
  finally:fixture.tearDown()

 def test_remote_request_parameters_keep_duration_out_of_composition(self):
  from h3chat.media_providers import MediaProviders
  import base64,io
  wav=io.BytesIO()
  with wave.open(wav,'wb') as audio:audio.setparams((1,2,48000,0,'NONE','not compressed'));audio.writeframes(b'\0\0'*8)
  with tempfile.TemporaryDirectory() as temp:
   provider=MediaProviders(Store(temp))
   provider.credentials=lambda _:({'name':'Music server','adapter':'h3','model':'song','device':'gpu'},'')
   composition={'style':'pop','lyrics':'ciao'}
   ticket={'id':'a'*32};finished={'status':'done','media':{'data':base64.b64encode(wav.getvalue()).decode(),'mime':'audio/wav'}}
   for value in (None,60):
    with patch.object(provider.client,'exchange',side_effect=[ticket,finished]) as client:
     provider.generate({'id':'remote'},{'music_overrides':{'remote':{'max_duration':value}}},'',[],'test',threading.Event(),lambda _:None,composition=composition)
    body=client.call_args_list[0].kwargs['body']
    if value is None:self.assertNotIn('max_duration',body['parameters'])
    else:self.assertEqual(body['parameters']['max_duration'],value)
    self.assertEqual(body['composition'],composition)

if __name__=='__main__':unittest.main()
