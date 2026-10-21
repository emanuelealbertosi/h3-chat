import copy
import json
import unittest
from h3chat.moss_layout import requested,compile_layout,explicit


class MossLayoutTests(unittest.TestCase):
    def test_converts_normalized_boxes_to_official_centered_yxyx(self):
        value={'summary':'A red circle beside a blue square.','items':[
            {'label':'object','caption':'Red circle','text':'','bbox':[100,200,400,800]},
            {'label':'text','caption':'Title','text':'Ciao!\nA tutti','bbox':[100,0,900,100]}]}
        before=copy.deepcopy(value);out=json.loads(compile_layout(value,1500,1000))
        self.assertEqual(out['items'][0]['bbox'],[-300,-600,300,-150])
        self.assertEqual(out['items'][1]['text'],'Ciao!\nA tutti')
        self.assertEqual(out['bbox_coord_space'],'abs_centralized');self.assertEqual(out['bbox_format'],'yxyx')
        self.assertEqual(value,before)

    def test_invalid_boxes_never_silently_clip_or_reorder(self):
        for box in ([0,0,1001,1000],[500,0,100,1000],[0,0,0,100],[False,0,100,100],[0,0,float('nan'),100],[0,0,float('inf'),100],[0,0,1]):
            with self.subTest(box=box),self.assertRaises(ValueError):
                compile_layout({'summary':'A scene','items':[{'label':'object','caption':'Red circle','bbox':box}]},1024,1024)

    def test_explicit_layout_is_preserved_without_replanning(self):
        text='{"summary":{"caption":"Title"},"items":[{"label":"text","caption":"Greeting","text":"Ciao!","bbox":[-200,-100,0,300]}],"bbox_format":"yxyx","bbox_coord_space":"abs_centralized"}'
        self.assertEqual(explicit(text),text)
        self.assertIsNone(explicit('An ordinary cat'))
        self.assertIsNone(explicit('{bad json'))

    def test_spatial_intent_does_not_match_hands_or_rain(self):
        for prompt in ('Metti una ragazza a sinistra e un albero a destra','Il titolo in alto','A dog on the left','layout: two subjects'):
            self.assertTrue(requested(prompt))
        for prompt in ('A woman raising her left hand','Un gatto sotto la pioggia','Un paesaggio al tramonto'):
            self.assertFalse(requested(prompt))


if __name__=='__main__':unittest.main()
