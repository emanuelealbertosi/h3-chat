import base64,io,json,threading,unittest,wave
from unittest.mock import patch
from h3chat.soundtrack import select
import test_video as fixture

TRACK={'id':'a','name':'GOW_test_30sec.mp3','mime':'audio/mpeg','path':'uploads/song.mp3'}
PROMPT='''DURATION: Exactly 30 seconds, divided into two consecutive 15-second clips.
AUDIO: Use the supplied 30-second song excerpt exactly as provided.
Preserve all music and vocals without modification. No additional dialogue,
voices, sound effects or music.
REFERENCE ROUTING:
- Picture 3: Mimir — silent supporting character
### CLIP 1 — 00:00–00:15
Freya sings. Mimir watches silently.
### CLIP 2 — 00:15–00:30
Kratos sings. Keep Mimir completely silent, with no additional dialogue.
'''


class SoundtrackTests(unittest.TestCase):
 def test_silent_character_keeps_explicit_and_attached_soundtrack(self):
  for prompt in (PROMPT,'Mimir is silent. Use original audio.',
                 'Personaggio muto, conserva musica e canto.',
                 'Crea un video con musica, senza audio aggiuntivo.',
                 'Use the track with no audio changes.',
                 'Use audio; without audio modifications.',
                 'Usa le immagini solo come riferimento e conserva la traccia.',
                 'Silent supporting character, musical backing.'):
   with self.subTest(prompt=prompt):self.assertEqual(select(prompt,[TRACK]),TRACK)
  self.assertEqual(select(PROMPT,[],[{'media':[TRACK]}]),TRACK)

 def test_explicit_output_silence_and_audio_reference_still_respected(self):
  for prompt in ('Crea senza audio','Render without audio','No audio',
                 'Silent','Muto','Make a silent video','Make a mute movie',
                 'The video must be completely silent','Video completamente muto',
                 'Il filmato deve essere muto','Audio solo come riferimento',
                 'Use audio as reference only','solo come riferimento'):
   with self.subTest(prompt=prompt):self.assertIsNone(select(prompt,[TRACK]))

 def test_track_choice_and_ambiguity_remain_explicit(self):
  other=TRACK|{'id':'b','name':'other.wav'}
  self.assertEqual(select('Audio 2. The supporting character is silent.',[TRACK,other]),other)
  self.assertEqual(select('Use GOW_test_30sec.mp3. Mimir is silent.',[TRACK,other]),TRACK)
  with self.assertRaisesRegex(ValueError,'più tracce'):select('A silent character sings with music',[TRACK,other])
  self.assertIsNone(select('A silent supporting character',[]))


class StoryboardAudioServiceTests(unittest.TestCase):
 setUp=fixture.VideoTests.setUp
 tearDown=fixture.VideoTests.tearDown

 def test_silent_supporting_character_does_not_reject_attached_music_before_planner(self):
  wav=io.BytesIO()
  with wave.open(wav,'wb') as f:f.setparams((1,2,8000,0,'NONE','NONE'));f.writeframes(b'\0\0'*8000)
  audio=self.app.upload({'name':'song.wav','data':base64.b64encode(wav.getvalue()).decode()})
  chat=self.app.store.create_chat()
  with patch.object(self.app.engine,'require_model'):
   job_id=self.app.send(chat['id'],{'prompt':PROMPT,'media':[audio],'video':True,'assistant':True,'video_editing':'storyboard'})['job_id']
  job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(job_id,))
  plan={'prompt':'Music video','images':[],'audios':[{'index':1,'role':'lipsync','start':0}]}
  result={'id':'test','name':'video.mp4','mime':'video/mp4','path':'outputs/test/video.mp4','generation':{'duration':30}}
  with patch.object(self.app.engine,'require_model',return_value=self.model),patch('h3chat.soundtrack.probe',return_value={'duration':30}),patch.object(self.app.engine,'refine_video',return_value=(plan,{})) as planner,patch.object(self.app.engine,'generate_long_video',return_value=result) as generate:
   self.app.execute_job(job,threading.Event())
  answer=self.app.store.chat(chat['id'])['messages'][-1]
  self.assertEqual(answer['status'],'done',answer['meta'])
  planner.assert_called_once();generate.assert_called_once()
  settings=generate.call_args.args[1]
  self.assertEqual(settings['_video_soundtrack']['id'],audio['id'])
  self.assertEqual(settings['_video_duration'],30)
  self.assertEqual(settings['_video_editing'],'storyboard')

if __name__=='__main__':unittest.main()
