import json
import threading
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock
from h3chat.slide_vision import describe
from h3chat.store import DEFAULTS
from h3chat.downloads import Cancelled


class SlideVisionTests(unittest.TestCase):
    def test_caption_budget_and_progress_are_separate_from_final_answer(self):
        app=Mock();app.engine.chat_messages.side_effect=lambda history,model,settings,**kw:history
        assets=[{'id':str(n),'path':f'image{n}.png'} for n in range(5)];stages=[];meta={}
        def complete(messages,settings,cancel,**kw):
            batch=messages[0]['media'];self.assertLessEqual(settings['max_tokens'],1792);self.assertEqual(settings['think_level'],'off')
            self.assertEqual(kw['schema']['properties']['descriptions']['maxItems'],len(batch))
            kw['on_text']('Un testo parziale ricevuto')
            return json.dumps({'descriptions':['Figura '+m['id'] for m in batch]}),'stop'
        app.engine.completion.side_effect=complete
        settings=DEFAULTS|{'max_tokens':25000,'vision_device':'gpu'}
        result=describe(app,assets,{'max_refs':4},settings,threading.Event(),stages.append,meta)
        self.assertEqual(set(result),{str(n) for n in range(5)});self.assertEqual(settings['max_tokens'],25000)
        self.assertTrue(any('Vision GPU' in s and 'scrittura descrizioni' in s for s in stages));self.assertEqual(meta['slide_vision']['new_images'],5)

    def test_incomplete_caption_does_not_invent_evidence_or_block_slides(self):
        app=Mock();app.engine.chat_messages.return_value=[];app.engine.completion.return_value=('{"descriptions":["unfinished','length');meta={}
        self.assertEqual(describe(app,[{'id':'figure'}],{},DEFAULTS,threading.Event(),lambda _:None,meta),{})
        self.assertIn('non analizzate',meta['slide_warning'])

    def test_cancellation_is_not_swallowed(self):
        app=Mock();app.engine.completion.side_effect=Cancelled()
        with self.assertRaises(Cancelled):describe(app,[{'id':'figure'}],{},DEFAULTS,threading.Event(),lambda _:None,{})

    def cached_app(self,folder):
        app=Mock();app.data=Path(folder);app.root=Path(folder)
        app.engine.chat_messages.side_effect=lambda history,model,settings,**kw:history
        def complete(messages,settings,cancel,**kw):
            return json.dumps({'descriptions':['Contenuto verificato '+a['id'] for a in messages[0]['media']]}),'stop'
        app.engine.completion.side_effect=complete
        return app

    def test_cached_captions_are_reused_across_output_paths_and_aliases(self):
        with tempfile.TemporaryDirectory() as folder:
            app=self.cached_app(folder)
            for name in ('first.png','copy.png'):(app.data/name).write_bytes(b'identical pixels')
            model={'id':'same-model','max_refs':4};assets=[{'id':'first','path':'first.png'},{'id':'copy','path':'copy.png'}]
            first=describe(app,assets,model,DEFAULTS,threading.Event(),lambda _:None,{})
            self.assertEqual(app.engine.completion.call_count,1);self.assertEqual(first['first'],first['copy'])
            second=describe(app,[{'id':'new-id','path':'copy.png'}],model,DEFAULTS,threading.Event(),lambda _:None,{})
            self.assertEqual(second['new-id'],first['first']);self.assertEqual(app.engine.completion.call_count,1)
            describe(app,assets,model|{'id':'other-model'},DEFAULTS,threading.Event(),lambda _:None,{})
            self.assertEqual(app.engine.completion.call_count,2)

    def test_rapid_mode_limits_only_new_images_and_keeps_all_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            app=self.cached_app(folder);assets=[]
            for n in range(12):
                (app.data/f'{n}.png').write_bytes(str(n).encode());assets.append({'id':str(n),'path':f'{n}.png'})
            meta={};result=describe(app,assets,{'id':'model'},DEFAULTS,threading.Event(),lambda _:None,meta,limit=8)
            self.assertEqual(len(result),8);self.assertEqual(meta['slide_vision']['unanalysed'],4);self.assertEqual(len(assets),12)
            meta={};result=describe(app,assets,{'id':'model'},DEFAULTS,threading.Event(),lambda _:None,meta,limit=8)
            self.assertEqual(len(result),12);self.assertEqual(meta['slide_vision']['cached'],8);self.assertEqual(meta['slide_vision']['new_images'],4)

    def test_changed_image_content_invalidates_cached_caption(self):
        with tempfile.TemporaryDirectory() as folder:
            app=self.cached_app(folder);file=app.data/'image.png';file.write_bytes(b'first')
            asset={'id':'image','path':'image.png'}
            describe(app,[asset],{'id':'model'},DEFAULTS,threading.Event(),lambda _:None,{})
            file.write_bytes(b'changed');describe(app,[asset],{'id':'model'},DEFAULTS,threading.Event(),lambda _:None,{})
            self.assertEqual(app.engine.completion.call_count,2)

    def test_changed_projector_invalidates_cached_caption(self):
        with tempfile.TemporaryDirectory() as folder:
            app=self.cached_app(folder);(app.data/'image.png').write_bytes(b'image')
            projector=app.root/'mmproj.gguf';projector.write_bytes(b'original')
            model={'id':'model','vision':{'projector':'mmproj.gguf'}};assets=[{'id':'image','path':'image.png'}]
            describe(app,assets,model,DEFAULTS,threading.Event(),lambda _:None,{})
            describe(app,assets,model,DEFAULTS,threading.Event(),lambda _:None,{})
            self.assertEqual(app.engine.completion.call_count,1)
            projector.write_bytes(b'updated projector');describe(app,assets,model,DEFAULTS,threading.Event(),lambda _:None,{})
            self.assertEqual(app.engine.completion.call_count,2)
