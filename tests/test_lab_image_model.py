import unittest
from types import SimpleNamespace
from h3chat.lab_image_model import select


class DefaultsTests(unittest.TestCase):
    def test_prefers_ready_standard_qwen_without_changing_chat_or_explicit_choice(self):
        models={key:{'id':key,'architecture':arch,'capabilities':['create'],'external_config':{'profile':profile}} for key,arch,profile in
                [('moss','moss','moss'),('qwen','qwen21','qwen21'),('turbo','qwen21','qwen21-turbo')]}
        engine=SimpleNamespace(catalog=models,require_model=lambda key,capability:models[key]);settings={'create_model':'moss'}
        self.assertEqual(select(engine,settings),'qwen')
        self.assertEqual(select(engine,settings,'moss'),'moss')
        self.assertEqual(settings['create_model'],'moss')
        def absent(key,capability):raise ValueError('Not installed')
        engine.require_model=absent
        self.assertEqual(select(engine,settings),'moss')
