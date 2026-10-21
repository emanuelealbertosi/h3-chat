import copy
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

from h3chat.store import DEFAULTS
from h3chat.video_engine import VideoEngine
from h3chat.video_request import spoken_lines
from h3chat.video_storyboard import build,validate


CUES='''## 3. ACTUAL VOCAL SEQUENCE
Follow the vocal arrangement in the supplied recording.
MALE — JACK:
"The lights went out across the sea"
### Female vocals
Rose sings:
"But you were the one thing by my side"
These are lyric alignment cues. Never regenerate the lyrics or vocals.
## 4. TWO INTERCUT CINEMATIC WORLDS
Silent ocean scenes accompany the original song.
'''
DIALOGUE='\n## 5. NEW DIALOGUE\nJack says: "We need another boat!"'


class LyricCueTests(unittest.TestCase):
    def setUp(self):
        self.refs=[{'id':'audio','mime':'audio/wav','path':'song.wav','name':'song.wav'}]
        self.plan={'prompt':'Silent ocean montage with the original <Audio 1>.','images':[],
                   'audios':[{'index':1,'role':'reuse','start':0}]}
        self.value={'style':'Moonlit ocean, cinematic lighting.','shots':[{
            'end':15,'prompt':'Jack balances on a floating wooden panel under the moon.',
            'time_basis':'local','continuity':'cut','lip_sync':False,'images':[]}]}
        self.settings=DEFAULTS|{'chat_model':'fixture','context':80000,'video_prompt_max_tokens':3000,
                               '_video_duration':15,'_video_soundtrack':self.refs[0]}
        self.engine=VideoEngine()
        self.engine.require_model=Mock(return_value={'id':'chat','name':'Chat','vision':{'enabled':False}})
        self.engine.start_llama=Mock()
        self.engine.chat_messages=Mock(return_value=[{'role':'system','content':''},{'role':'user','content':'request'}])

    def test_original_lyric_cues_are_exempt_only_when_audio_is_preserved(self):
        self.assertIn('The lights went out across the sea',spoken_lines(CUES))
        self.assertEqual(spoken_lines(CUES,preserved_audio=True),[])
        self.assertEqual(spoken_lines(CUES+DIALOGUE,preserved_audio=True),['We need another boat!'])

    def test_vocal_heading_without_reference_cue_marker_is_still_required(self):
        prompt='## VOCAL SEQUENCE\nJack sings: "Please do not leave me."'
        self.assertEqual(spoken_lines(prompt,preserved_audio=True),['Please do not leave me.'])

    def test_italian_cues_and_next_heading_boundary(self):
        prompt='## Versi della canzone\nCanto: "Il mare ci separa"\nQuesti versi sono un riferimento per la sincronizzazione.\n## Dialogo\nRose dice: "Torna qui!"'
        self.assertEqual(spoken_lines(prompt,preserved_audio=True),['Torna qui!'])

    def test_storyboard_accepts_original_lyrics_but_rejects_omitted_new_dialogue(self):
        result=validate(self.value,15,self.refs,CUES,preserved_audio=True)
        self.assertEqual(len(result['shots']),1)
        for prompt,preserved in ((CUES,False),(CUES+DIALOGUE,True)):
            with self.subTest(prompt=prompt,preserved=preserved),self.assertRaisesRegex(ValueError,'parole esatte'):
                validate(self.value,15,self.refs,prompt,preserved_audio=preserved)
        value=copy.deepcopy(self.value);value['shots'][0]['prompt']+=' Jack says: "We need another boat!"'
        validate(value,15,self.refs,CUES+DIALOGUE,preserved_audio=True)

    def test_storyboard_build_passes_preservation_and_required_dialogue_to_llm(self):
        self.engine.completion=Mock(return_value=(json.dumps(self.value),'stop'))
        build(self.engine,self.plan,self.refs,self.settings,CUES,threading.Event(),Mock(),Path('fixture.log'))
        self.assertEqual(self.engine.completion.call_count,1)
        context=json.loads(self.engine.completion.call_args.args[0][1]['content'])
        self.assertTrue(context['preserved_audio']);self.assertEqual(context['required_spoken_lines'],[])
        self.assertEqual(context['clip_windows'][0]['local_time_range'],[0,15])

    def test_initial_refinement_does_not_retry_for_preserved_lyric_cues(self):
        self.engine.completion=Mock(return_value=(json.dumps(self.plan),'stop'))
        plan,_=self.engine.refine_video([],CUES,self.refs,{'id':'video'},self.settings,
                                       threading.Event(),Path('fixture.log'),Mock())
        self.assertEqual(plan,self.plan);self.assertEqual(self.engine.completion.call_count,1)

    def test_initial_refinement_still_repairs_missing_new_dialogue(self):
        repaired=self.plan|{'prompt':self.plan['prompt']+' Jack says: "We need another boat!"'}
        self.engine.completion=Mock(side_effect=[(json.dumps(self.plan),'stop'),(json.dumps(repaired),'stop')])
        plan,_=self.engine.refine_video([],CUES+DIALOGUE,self.refs,{'id':'video'},self.settings,
                                       threading.Event(),Path('fixture.log'),Mock())
        self.assertEqual(plan,repaired);self.assertEqual(self.engine.completion.call_count,2)


if __name__=='__main__':unittest.main()
