import ast
import math
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from h3chat.video_options import validate

ROOT = Path(__file__).resolve().parents[1]


class VideoAttentionTests(unittest.TestCase):
    def test_preferences_and_existing_presets_use_auto(self):
        self.assertEqual(validate({'steps':12})['attention'], 'auto')
        for preference in ('auto','sage','pytorch'):
            self.assertEqual(validate({'attention':preference})['attention'], preference)
        for invalid in ('flash',None,True,[]):
            with self.assertRaises(ValueError):validate({'attention':invalid})
        for invalid in (-1,57,True,1.5,'8'):
            with self.assertRaises(ValueError):validate({'attention_chunks':invalid})

    def test_auto_fallback_explicit_sage_and_switch_back_to_pytorch(self):
        tree = ast.parse((ROOT/'native/video-worker.py').read_text(encoding='utf-8'))
        definition = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Worker')
        events = Mock()
        namespace = {'emit':events, 'logging':Mock(), 'chunked_attention':lambda torch,attention,chunks:attention.attention_sage}
        exec(compile(ast.Module(body=[definition], type_ignores=[]), '<video-worker>', 'exec'), namespace)
        worker = namespace['Worker']();worker.model = Mock()
        worker.torch=SimpleNamespace(cuda=SimpleNamespace(get_device_properties=lambda _:SimpleNamespace(total_memory=16*1024**3)))
        module = ModuleType('comfy.ldm.modules')
        module.attention = Mock(SAGE_ATTENTION_IS_AVAILABLE=False)
        with patch.dict('sys.modules', {'comfy.ldm.modules':module}):
            self.assertEqual(worker.configure_attention('auto'), 'pytorch')
            worker.model.set_model_optimized_attention.assert_called_with(module.attention.attention_pytorch)
            with self.assertRaisesRegex(ValueError, 'SageAttention non installato'):
                worker.configure_attention('sage')
            module.attention.SAGE_ATTENTION_IS_AVAILABLE = True
            for preference in ('auto','sage'):
                self.assertEqual(worker.configure_attention(preference), 'sage')
                worker.model.set_model_optimized_attention.assert_called_with(module.attention.attention_sage)
            self.assertEqual(worker.configure_attention('pytorch'), 'pytorch')
            worker.model.set_model_optimized_attention.assert_called_with(module.attention.attention_pytorch)
        events.assert_called_with('stage', message='Video · attenzione PyTorch')


if __name__ == '__main__':unittest.main()
