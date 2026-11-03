import copy,json,threading,unittest
from unittest.mock import Mock
from h3chat.infographic_audio import complete_music,music_brief,narration_parts
from h3chat.infographics import options
from h3chat.downloads import Cancelled


class InfographicAudioTests(unittest.TestCase):
    def test_instrumental_without_vocals_keeps_the_requested_narrator(self):
        for prompt in ('Voce narrante italiana. Crea una base strumentale leggera senza voce e tienila bassa.',
                       'Musica senza voce, narrazione italiana presente.', 'Instrumental background music, no voice.'):
            with self.subTest(prompt=prompt):self.assertTrue(options(prompt,{'voice':True})['voice'])
        for prompt in ('Video senza voce.', 'Musica strumentale e video senza narrazione.', 'No voice.'):
            with self.subTest(prompt=prompt):self.assertFalse(options(prompt,{'voice':True})['voice'])

    def plan(self):
        return {'title':'Scuola','visual_direction':'Chiaro e giocoso','music_style':'','jingle_lyrics':'',
                'scenes':[{'narration':'Uno.'},{'narration':'Due.'},{'narration':'Tre.'}]}

    def test_instrumental_music_is_not_conditioned_on_a_jingle(self):
        engine=Mock();plan=self.plan();original=copy.deepcopy(plan)
        engine.completion.return_value=(json.dumps({'music_style':'Gentle acoustic instrumental, no vocals','jingle_lyrics':''}),'stop')
        opts=options(value={'music':'generate'})
        result=complete_music(engine,[{'role':'user','content':'Chitarra dolce senza canto'}],plan,opts,
                              {'max_tokens':40000,'temperature':.6},threading.Event(),lambda _:None)
        self.assertEqual(result['scenes'],original['scenes']);self.assertEqual(plan,original)
        self.assertTrue(result['music_style']);self.assertEqual(result['jingle_lyrics'],'')
        self.assertEqual(engine.completion.call_count,1)
        messages=engine.completion.call_args.args[0]
        self.assertIn('Chitarra dolce senza canto',messages[0]['content'])
        self.assertIn('NON VUOTA',music_brief(opts))

    def test_missing_music_fails_before_synthesis_without_inventing_a_style(self):
        for reply,finish in (({'music_style':'  ','jingle_lyrics':''},'stop'),
                             ({'music_style':'Ambient','jingle_lyrics':''},'length')):
            engine=Mock();engine.completion.return_value=(json.dumps(reply),finish)
            with self.assertRaisesRegex(ValueError,'nessuna sintesi'):
                complete_music(engine,[],self.plan(),options(value={'music':'generate'}),
                    {'max_tokens':40000,'temperature':.6},threading.Event(),lambda _:None)
            self.assertEqual(engine.completion.call_count,1)

    def test_pipeline_rejects_empty_music_before_voice_worker_or_canvas_publication(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from h3chat.infographics import build
        with tempfile.TemporaryDirectory() as tmp:
            app=Mock();app.data=Path(tmp);app.engine.chat_messages.return_value=[]
            app.engine.completion.return_value=(json.dumps({'music_style':'','jingle_lyrics':''}),'stop')
            settings={'_infographic':options(value={'music':'generate','images':'provided','scenes':3}),
                      'max_tokens':40000,'temperature':.6}
            with patch('h3chat.infographics.plan_regia',return_value=self.plan()),patch('h3chat.voice.synthesize') as voice:
                with self.assertRaisesRegex(ValueError,'nessuna sintesi'):
                    build(app,{'id':'fixture','chat_id':'chat'},{'media':[]},[],settings,{},threading.Event(),lambda _:None,Path(tmp)/'log',{})
                voice.assert_not_called();app.engine.generate_music.assert_not_called();app.save_artifact.assert_not_called()

    def test_existing_style_no_music_and_static_require_no_extra_llm(self):
        engine=Mock();plan=self.plan()|{'music_style':'Ambient'}
        for opts,p in ((options(value={'music':'generate'}),plan),
                       (options(value={'music':'none'}),self.plan()),
                       (options(value={'output':'static','music':'generate'}),self.plan())):
            self.assertIs(complete_music(engine,[],p,opts,{},threading.Event(),lambda _:None),p)
        engine.completion.assert_not_called()

    def test_jingle_needs_lyrics_and_stop_is_respected(self):
        engine=Mock();engine.completion.return_value=(json.dumps({'music_style':'Pop','jingle_lyrics':''}),'stop')
        with self.assertRaises(ValueError):
            complete_music(engine,[],self.plan(),options(value={'music':'jingle'}),
                {'max_tokens':40000,'temperature':.6},threading.Event(),lambda _:None)
        cancel=threading.Event();cancel.set()
        with self.assertRaises(Cancelled):complete_music(engine,[],self.plan(),options(value={'music':'generate'}),{},cancel,lambda _:None)

    def test_voice_prompt_overrides_and_scene_alternation_are_stable(self):
        opts=options('Crea un video con voci maschile e femminile',{'voice_gender':'male'})
        self.assertEqual(opts['voice_gender'],'mixed')
        parts=narration_parts(self.plan(),opts['voice_gender'],'male')
        self.assertEqual([p['voice_fields']['gender'] for p in parts],['male','female','male'])
        self.assertEqual([p['scene_id'] for p in parts],[0,1,2])
        self.assertEqual(options('Con voce femminile calda',{'voice_gender':'male','voice_style':'serious'})['voice_style'],'warm')
        self.assertEqual(options('Una donna visita la scuola',{'voice_gender':'male'})['voice_gender'],'male')
        with self.assertRaises(ValueError):options(value={'voice_gender':'invented'})

if __name__=='__main__':unittest.main()
