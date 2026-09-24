import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]

class ConditioningTests(unittest.TestCase):
    def test_cfg_one_skips_unused_negative_encoder_pass(self):
        source=ast.parse((ROOT/'native/vision-worker.py').read_text(encoding='utf-8'))
        worker=next(node for node in source.body if isinstance(node,ast.ClassDef) and node.name=='Worker')
        namespace={};exec(compile(ast.Module(body=[worker],type_ignores=[]),'<worker-test>','exec'),namespace)
        for cfg,expected in ((1,1),(1.0,1),(2,2)):
            instance=namespace['Worker']();instance.architecture='qwen21'
            instance.torch=SimpleNamespace(zeros=lambda *a,**k:'latent',zeros_like=lambda value:'zeros')
            instance.comfy=SimpleNamespace(model_management=SimpleNamespace(intermediate_device=lambda:'cpu'))
            clip=SimpleNamespace(tokenize=Mock(side_effect=lambda text,**kw:text),encode_from_tokens_scheduled=Mock(side_effect=lambda tokens:[[tokens,{}]]))
            request={'width':512,'height':512,'prompt':'a landscape','negative_prompt':'blur','cfg':cfg}
            positive,negative,latent=instance.encode(clip,request,[])
            self.assertEqual(clip.encode_from_tokens_scheduled.call_count,expected)
            self.assertEqual(positive[0][0],'a landscape')
            if cfg!=1:self.assertEqual(negative[0][0],'blur')
