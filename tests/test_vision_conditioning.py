import ast
import math
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]

class ConditioningTests(unittest.TestCase):
    def test_six_qwen_references_keep_order_and_output_area_without_enlarging_inputs(self):
        class Tensor:
            def __init__(self,shape,ident=None):self.shape=shape;self.ident=ident
            def movedim(self,source,target):
                axes=list(self.shape);value=axes.pop(source);axes.insert(target if target>=0 else len(axes)+target+1,value);return Tensor(axes,self.ident)
            def __getitem__(self,key):return self
        tree=ast.parse((ROOT/'native/vision-worker.py').read_text(encoding='utf8'))
        worker=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Worker')
        namespace={'math':math};exec(compile(ast.Module(body=[worker],type_ignores=[]),'<worker-test>','exec'),namespace)
        instance=namespace['Worker']();instance.architecture='qwen21'
        instance.torch=SimpleNamespace(zeros=lambda shape,**kw:Tensor(shape),zeros_like=lambda x:'zero')
        instance.comfy=SimpleNamespace(utils=SimpleNamespace(common_upscale=lambda x,w,h,*a:Tensor([1,3,h,w],x.ident)),model_management=SimpleNamespace(intermediate_device=lambda:None))
        instance.vae=SimpleNamespace(encode=Mock(side_effect=lambda x:x))
        clip=SimpleNamespace(tokenize=Mock(side_effect=lambda text,**kw:text),encode_from_tokens_scheduled=lambda text:[['embedding',{}]])
        images=[Tensor([1,1504,2688,3],i) for i in range(6)]
        request={'width':1888,'height':1088,'prompt':'six people','cfg':1,'preserve_reference_aspect':False}
        positive,negative,latent=instance.encode(clip,request,images)
        self.assertEqual(latent.shape,[1,64,68,118])
        refs=positive[0][1]['reference_latents'];self.assertEqual([x.ident for x in refs],list(range(6)))
        self.assertEqual(len(clip.tokenize.call_args.kwargs['images']),6)
        self.assertTrue(all(x.shape[1]*x.shape[2]<1_100_000 for x in refs))
        self.assertEqual(len(negative[0][1]['reference_latents']),6)
        request['preserve_reference_aspect']=True
        _,_,auto=instance.encode(clip,request,images)
        self.assertGreater(auto.shape[-1]*auto.shape[-2]*256,1_900_000)

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
