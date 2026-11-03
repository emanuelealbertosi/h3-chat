import copy,json,tempfile,unittest
from pathlib import Path
from h3chat.infographic_voices import configure
from h3chat.infographics import options

class InfographicVoiceTests(unittest.TestCase):
    def test_scoped_default_references_and_explicit_choices(self):
        settings={'voice_engine':'moss','voice_gender':'male','voice_precision':'8bit','voice_temperature':1.2,
                  'voice_references':{'female':{'path':'other.wav','transcript':''},'male':{'path':'man.wav','transcript':''}}}
        original=copy.deepcopy(settings)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'data/voices';folder.mkdir(parents=True)
            for name in ('limpida','aurora'):(folder/(name+'.wav')).write_bytes(b'fixture')
            (folder/'infographic-profiles.json').write_text(json.dumps({'default':'limpida','profiles':{name:{'path':'data/voices/'+name+'.wav','transcript':name} for name in ('limpida','aurora')}}))
            for name in ('auto','aurora','configured'):
                result,selected=configure(root,settings,options(value={'voice_profile':name}),'lively')
                if name=='configured':self.assertEqual(result['voice_precision'],'8bit');continue
                self.assertEqual(result['voice_precision'],'bf16');self.assertEqual(result['voice_seed'],734)
                self.assertEqual(result['_voice_fields']['delivery'],'custom')
                self.assertEqual(result['_voice_fields']['engine'],'higgs')
                self.assertEqual(result['voice_references']['female']['transcript'],selected)
                self.assertEqual(result['voice_references']['male'],settings['voice_references']['male'])
            result,selected=configure(root,settings,options(value={'voice_gender':'mixed'}),'warm')
            self.assertEqual(selected,'configured');self.assertEqual(result['voice_gender'],'male')
            result,_=configure(root,settings,options(value={'voice_style':'radio'}),'radio')
            self.assertEqual(result['_voice_fields']['delivery'],'radio')
        self.assertEqual(settings,original)

    def test_portable_install_fallback_and_prompt_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,selected=configure(Path(tmp),{},options(),'serious')
            self.assertEqual(selected,'configured')
            with self.assertRaisesRegex(ValueError,'non installato'):
                configure(Path(tmp),{},options(value={'voice_profile':'aurora'}),'serious')
        self.assertEqual(options('Usa voce Aurora',{'voice_profile':'limpida'})['voice_profile'],'aurora')
        with self.assertRaises(ValueError):options(value={'voice_profile':'unknown'})

if __name__=='__main__':unittest.main()
