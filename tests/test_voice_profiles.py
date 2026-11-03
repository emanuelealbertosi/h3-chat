"""Shared Italian timbres in Voice/Studio; synthetic references, no inference."""
import copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from h3chat.voice import DEFAULTS,configuration,validate_fields
from h3chat.study_audio import voices

class SharedVoiceProfilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        folder=self.root/'data/voices';folder.mkdir(parents=True)
        for name in ('limpida','aurora','male','female'):(folder/(name+'.wav')).write_bytes(b'fixture')
        (folder/'infographic-profiles.json').write_text(json.dumps({'profiles':{name:{'path':'data/voices/'+name+'.wav','transcript':name} for name in ('limpida','aurora')}}))
        self.settings=copy.deepcopy(DEFAULTS)|{'voice_references':{g:{'path':str(folder/(g+'.wav')),'transcript':g} for g in ('male','female')}}
        self.patches=[patch('h3chat.voice.runtime_ready',return_value=True),patch('h3chat.voice.resolve_model',return_value=folder)]
        for p in self.patches:p.start();self.addCleanup(p.stop)
    def test_both_profiles_use_original_recipe_and_leave_preferences_untouched(self):
        before=copy.deepcopy(self.settings)
        for name in ('limpida','aurora'):
            fields=validate_fields({'profile':name,'mode':'read'})
            cfg,choice,acting,voice=configuration(self.root,self.settings|{'_voice_fields':fields},'')
            self.assertEqual((cfg['engine'],cfg['precision'],cfg['seed'],cfg['temperature']),('higgs','bf16',734,.8))
            self.assertEqual(choice['gender'],'female');self.assertEqual(voice['transcript'],name)
            self.assertIn('prosody:expressive_high',acting['tags'])
        self.assertEqual(self.settings,before)
    def test_prompt_direction_overrides_profile_but_verbatim_text_does_not(self):
        settings=self.settings|{'_voice_fields':{'profile':'limpida'}}
        self.assertEqual(configuration(self.root,settings,'Usa voce Aurora. Testo: Buongiorno.')[3]['transcript'],'aurora')
        self.assertEqual(configuration(self.root,settings,'Testo: La voce Aurora è una voce.')[3]['transcript'],'limpida')
    def test_studio_keeps_two_distinct_profiles_and_shared_bf16_config(self):
        result=voices(SimpleNamespace(root=self.root),self.settings|{'_study_audio_voices':{'voice_a':'limpida','voice_b':'aurora'}})
        self.assertNotEqual(result[0][2]['id'],result[1][2]['id'])
        self.assertEqual([v[2]['transcript'] for v in result],['limpida','aurora'])
        self.assertTrue(all(v[0]['precision']=='bf16' and v[0]['seed']==734 for v in result))
    def test_same_speaker_for_both_hosts_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'due voci distinte'):
            voices(SimpleNamespace(root=self.root),self.settings|{'_study_audio_voices':{'voice_a':'limpida','voice_b':'limpida'}})
    def test_infographic_profile_is_not_replaced_by_global_voice_preference(self):
        from h3chat.infographic_voices import configure
        settings,_=configure(self.root,self.settings|{'voice_profile':'aurora'}, {'voice_profile':'limpida','voice_gender':'mixed','voice_style':'auto'},'custom')
        self.assertEqual(configuration(self.root,settings,'')[3]['transcript'],'limpida')
        male=settings|{'_voice_fields':settings['_voice_fields']|{'gender':'male'}}
        self.assertEqual(configuration(self.root,male,'')[3]['transcript'],'male')
    def test_packaged_profiles_work_without_an_owner_registry_and_preserve_auto(self):
        registry=self.root/'data/voices/infographic-profiles.json';original=registry.read_bytes();registry.unlink()
        folder=self.root/'static/voice-profiles';folder.mkdir(parents=True)
        (folder/'limpida.wav').write_bytes(b'generated fixture')
        (folder/'profiles.json').write_text(json.dumps({'default':'configured','profiles':{'limpida':{'path':'static/voice-profiles/limpida.wav','transcript':'Campione italiano'}}}))
        from h3chat.infographic_voices import configure
        opts={'voice_profile':'limpida','voice_gender':'female','voice_style':'auto'}
        selected,name=configure(self.root,self.settings,opts,'custom')
        self.assertEqual(name,'limpida');self.assertTrue(Path(selected['voice_references']['female']['path']).is_file())
        _,name=configure(self.root,self.settings,opts|{'voice_profile':'auto'},'custom');self.assertEqual(name,'configured')
        registry.write_bytes(original)
        selected,_=configure(self.root,self.settings,opts,'custom');self.assertEqual(selected['voice_references']['female']['transcript'],'limpida')
