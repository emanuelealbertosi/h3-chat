import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.voice import DEFAULTS,validate,validate_fields,route,controls,resolve_model,build,synthesize
from h3chat.voice_controls import split_text,apply_direction

class VoiceTests(unittest.TestCase):
    def test_radio_profile_preserves_words_and_varies_phrase_delivery(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);app=Mock(root=root,data=root)
            app.engine.tool_call.return_value={'duration':12}
            config={'engine':'higgs','model_path':tmp,'device':'cuda','temperature':.7,'seed':734,'speed_factor':1.08,'pause_ms':150}
            text='Dai vita alle tue idee! Immagini, parole e musica. Scegli il tuo stile. Comincia da te!'
            meta={}
            with patch('h3chat.voice.configuration',return_value=(config,{'delivery':'radio'}, {'prefix':'','tags':[]}, {'id':'fixture','reference':tmp})):
                synthesize(app,root/'voice',[{'text':text}],DEFAULTS|{'memory_policy':'on_demand'},'',threading.Event(),lambda _:None,root/'log',meta)
            request=app.engine.tool_call.call_args.args[1]
            self.assertEqual(''.join(s['text'] for s in request['segments']),text)
            self.assertEqual([s['speed_factor'] for s in request['segments']],[1.08,1.12,1.08,1.12])
            self.assertTrue(all(s['seed']==734 for s in request['segments']))
            self.assertIn('<|emotion:pride|>',request['segments'][2]['spoken'])
            self.assertEqual(meta['voice_parameters']['segment_speed_factors'],[1.08,1.12,1.08,1.12])

    def test_enthusiasm_also_requests_expressive_delivery(self):
        for settings,prompt in ((DEFAULTS|{'_voice_fields':{'emotion':'enthusiasm'}},'Spiega il Sole'),
                                (DEFAULTS,'Spiega il Sole con voce entusiasta')):
            choice,acting=controls(settings,prompt)
            self.assertEqual(choice['emotion'],'enthusiasm')
            self.assertEqual(choice['expressiveness'],'high')
            self.assertIn('emotion:enthusiasm',acting['tags'])
            self.assertIn('prosody:expressive_high',acting['tags'])
            speech='Prima frase. Seconda frase!'
            spoken=apply_direction(speech,acting['prefix'])
            self.assertEqual(spoken.count('<|prosody:expressive_high|>'),2)
            from h3chat.voice_controls import TAG_RE
            self.assertEqual(TAG_RE.sub('',spoken),speech)

    def test_explicit_sober_and_negated_expression_are_preserved(self):
        choice,acting=controls(DEFAULTS|{'_voice_fields':{'emotion':'enthusiasm','expressiveness':'low'}},'Spiega il Sole')
        self.assertEqual(choice['expressiveness'],'low')
        self.assertIn('prosody:expressive_low',acting['tags'])
        self.assertNotIn('prosody:expressive_high',acting['tags'])
        _,acting=controls(DEFAULTS|{'voice_emotion':'enthusiasm'},'Non espressiva')
        self.assertNotIn('prosody:expressive_high',acting['tags'])
        _,acting=controls(DEFAULTS,'Spiega il Sole')
        self.assertEqual(acting['tags'],[])
        choice,acting=controls(DEFAULTS|{'voice_emotion':'enthusiasm'},'Non entusiasta')
        self.assertEqual(choice['emotion'],'neutral')
        self.assertEqual(acting['tags'],[])

    def test_words_to_read_cannot_flatten_selected_interpretation(self):
        choice,acting=controls(DEFAULTS|{'_voice_fields':{'emotion':'enthusiasm'}},
                              'Leggi. Testo: Questo è un grafico piatto. Una voce triste e lenta.')
        self.assertEqual(choice['emotion'],'enthusiasm')
        self.assertEqual(choice['speed'],'normal')
        self.assertEqual(set(acting['tags']),{'emotion:enthusiasm','prosody:expressive_high'})

    def test_narrated_scene_segments_all_receive_effective_controls(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);ref=folder/'reference.wav';ref.write_bytes(b'fixture')
            app=Mock(root=folder,data=folder)
            settings=DEFAULTS|{'memory_policy':'on_demand','_voice_fields':{'emotion':'enthusiasm'},
                'voice_references':{'female':{'path':str(ref),'transcript':'Campione.'}}}
            parts=[{'scene_id':0,'text':'Primo concetto. Secondo concetto!','sentence_cues':True},
                   {'scene_id':1,'text':'Ultima scena.','sentence_cues':True}]
            app.engine.tool_call.return_value={'duration':9}
            meta={}
            with patch('h3chat.voice.runtime_ready',return_value=True),patch('h3chat.voice.resolve_model',return_value=tmp):
                synthesize(app,folder/'audio',parts,settings,'Crea Manim con voce',threading.Event(),lambda _:None,folder/'log',meta)
            worker,request,*_=app.engine.tool_call.call_args.args
            self.assertEqual(worker,'voice-worker.py')
            self.assertEqual([s['scene_id'] for s in request['segments']],[0,0,1])
            self.assertEqual(''.join(s['text'] for s in request['segments']),''.join(p['text'] for p in parts))
            for segment in request['segments']:
                self.assertTrue(segment['spoken'].startswith('<|emotion:enthusiasm|><|prosody:expressive_high|>'))
            self.assertEqual(meta['voice_controls']['expressiveness'],'high')
            self.assertEqual(request['config']['temperature'],DEFAULTS['voice_temperature'])

    def test_routing_controls_and_verbatim_segments(self):
        for text in ('crea una lezione audio sul Sole','leggi ad alta voce: Ciao','genera un riassunto vocale'):
            self.assertEqual(route([{'content':text}],DEFAULTS)['intent'],'voice')
        for text in ('non creare una voce','come genero un riassunto vocale?','crea una canzone','spiega che cosa è la voce'):
            self.assertIsNone(route([{'content':text}],DEFAULTS))
        self.assertIsNone(route([{'content':'leggi questo'}],DEFAULTS|{'_video':True}))
        value,tags=controls(DEFAULTS,'voce maschile, profonda e lenta')
        self.assertEqual(value['gender'],'male');self.assertIn('prosody:pitch_low',tags['tags'])
        text=('Prima frase. Seconda frase con accenti: è così! '*40)
        self.assertEqual(''.join(split_text(text,120)),text)
        validate(copy.deepcopy(DEFAULTS))
        with self.assertRaises(ValueError):validate_fields({'gender':'invented'})

    def test_checkpoint_selection_and_invalid_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'config.json').write_text(json.dumps({'model_type':'higgs_multimodal_qwen3'}))
            with self.assertRaises(ValueError):resolve_model(tmp)
            for name in ('tokenizer.json','modeling_higgs_multimodal_qwen3.py','configuration_higgs_multimodal_qwen3.py','model.safetensors'):(p/name).write_text('fixture')
            self.assertEqual(resolve_model(tmp),str(p.resolve()))

    def test_voice_off_uses_no_llm_and_canvas_wav_text_subtitles(self):
        from h3chat.service import Service
        from h3chat.store import DEFAULTS as ALL
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            app=Service(root,tmp,start_worker=False)
            try:
                ref=Path(tmp)/'ref.wav';ref.write_bytes(b'fixture')
                settings=ALL|{'voice_references':{'female':{'path':str(ref),'transcript':''},'male':{'path':'','transcript':''}},'_assistant':False,'_voice':True,'_voice_fields':{'mode':'read'}}
                job={'id':'synthetic','chat_id':'chat'};meta={}
                def render(worker,request,*args,**kw):
                    self.assertEqual(worker,'voice-worker.py');self.assertEqual(''.join(s['text'] for s in request['segments']),'Testo esatto.')
                    for name in ('voce.wav','voce.srt'):(Path(request['output'])/name).write_bytes(b'fixture')
                    return {'duration':2}
                with patch('h3chat.voice.runtime_ready',return_value=True),patch('h3chat.voice.resolve_model',return_value=tmp),patch.object(app.engine,'tool_call',side_effect=render),patch.object(app.engine,'start_llama',side_effect=AssertionError('Must not load LLM')):
                    media=build(app,job,{'prompt':'Testo esatto.'},[],settings,{},threading.Event(),lambda _:None,Path(tmp)/'log',meta)
                self.assertEqual([m['mime'] for m in media],['audio/wav','text/plain','application/x-subrip'])
                self.assertEqual(meta['voice_duration'],2)
            finally:app.close()
