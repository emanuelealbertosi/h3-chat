import json
import threading
import unittest
from unittest.mock import Mock
from h3chat.slide_vision import describe
from h3chat.store import DEFAULTS
from h3chat.downloads import Cancelled


class SlideVisionTests(unittest.TestCase):
    def test_caption_budget_and_progress_are_separate_from_final_answer(self):
        app=Mock();app.engine.chat_messages.side_effect=lambda history,model,settings:history
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
        self.assertTrue(any('Vision GPU' in s and 'scrittura descrizioni' in s for s in stages));self.assertEqual(meta,{})

    def test_incomplete_caption_does_not_invent_evidence_or_block_slides(self):
        app=Mock();app.engine.chat_messages.return_value=[];app.engine.completion.return_value=('{"descriptions":["unfinished','length');meta={}
        self.assertEqual(describe(app,[{'id':'figure'}],{},DEFAULTS,threading.Event(),lambda _:None,meta),{})
        self.assertIn('non analizzate',meta['slide_warning'])

    def test_cancellation_is_not_swallowed(self):
        app=Mock();app.engine.completion.side_effect=Cancelled()
        with self.assertRaises(Cancelled):describe(app,[{'id':'figure'}],{},DEFAULTS,threading.Event(),lambda _:None,{})
