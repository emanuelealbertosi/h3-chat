import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.voice import DEFAULTS,validate,validate_fields,route,controls,resolve_model,build
from h3chat.voice_controls import split_text,apply_direction

class VoiceTests(unittest.TestCase):
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
