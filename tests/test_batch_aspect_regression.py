from types import SimpleNamespace
import unittest
from h3chat.image_batch import validate_plan
from h3chat.store import DEFAULTS


class BatchAspectRegression(unittest.TestCase):
    def test_agent_global_ratio_before_a_sentence_is_kept_for_every_image(self):
        model={'id':'moss','name':'MOSS','architecture':'moss','engine':'vision','capabilities':['create'],'steps':50,'cfg':3,'max_refs':1}
        app=SimpleNamespace(catalog={'moss':model},engine=SimpleNamespace(require_model=lambda ident,cap:model))
        plan={'images':[{'prompt':'A skating scene','model_id':'moss','references':[],'parameters':{'aspect':'1:1'}} for _ in range(4)]}
        for ratio in ('16:9','9:16','4:3','3:4','1:1'):
            with self.subTest(ratio=ratio):
                prompt='Crea 4 immagini. Formato '+ratio+'. Quattro scene di pattinaggio. Nessun testo.'
                tasks=validate_plan(app,plan,[],DEFAULTS,4,(),prompt)
                a,b=map(int,ratio.split(':'))
                self.assertTrue(all(t['parameters']['width']*b==t['parameters']['height']*a for t in tasks))
                self.assertTrue(all(t['parameters']['aspect']==ratio for t in tasks))

    def test_global_header_and_numbered_per_image_overrides_remain_independent(self):
        model={'id':'moss','name':'MOSS','architecture':'moss','engine':'vision','capabilities':['create'],'max_refs':1}
        app=SimpleNamespace(catalog={'moss':model},engine=SimpleNamespace(require_model=lambda ident,cap:model))
        plan={'images':[{'prompt':'An image','model_id':'moss','references':[],'parameters':{}} for _ in range(2)]}
        prompt='Crea 2 immagini. Formato 16:9.\n1. Paesaggio.\n2. Ritratto 9:16.'
        tasks=validate_plan(app,plan,[],DEFAULTS,2,(),prompt)
        self.assertEqual([t['parameters']['aspect'] for t in tasks],['16:9','9:16'])

    def test_numbered_controls_above_twenty_four_remain_available(self):
        from h3chat.image_batch_controls import source_controls
        prompt='Crea 50 immagini. Formato 16:9.\n25. Ritratto 9:16.\n50. Panorama 3:2.'
        self.assertIn('9:16',source_controls(prompt,25))
        self.assertNotIn('9:16',source_controls(prompt,50))
        self.assertIn('3:2',source_controls(prompt,50))


if __name__=='__main__':unittest.main()
