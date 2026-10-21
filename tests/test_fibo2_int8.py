import json,sys,unittest
from pathlib import Path
from h3chat.fibo2_int8 import remap_transformer,install_quantized_modules,encoder_state


class QuantizedLoadingTests(unittest.TestCase):
    def test_tied_qwen_head_reuses_embedding_quantization_without_a_second_checkpoint_copy(self):
        from types import SimpleNamespace
        state={'model.language_model.embed_tokens.'+suffix:object() for suffix in ('weight','weight_scale','comfy_quant')}
        result=encoder_state(state,SimpleNamespace(tie_word_embeddings=True))
        for suffix in ('weight','weight_scale','comfy_quant'):
            self.assertIs(result['lm_head.'+suffix],result['model.language_model.embed_tokens.'+suffix])

    def test_convrot_survives_fused_split_and_padded_feedforward_keeps_all_columns(self):
        class Rows:
            def __init__(self,rows,columns):self.rows=list(rows);self.shape=(len(self.rows),columns)
            def __getitem__(self,s):return Rows(self.rows[s],self.shape[1])
        config=object()
        mapped=remap_transformer({'layers.0.attention.qkv.weight':Rows(range(12),256),
            'layers.0.attention.qkv.weight_scale':Rows(range(12),1),
            'layers.0.attention.qkv.comfy_quant':config,
            'layers.0.feed_forward.w13.weight':Rows(range(20),256),
            'layers.0.feed_forward.w2.weight':Rows(range(4),10)})
        self.assertEqual(mapped['layers.0.attention.to_k.weight'].rows,[4,5,6,7])
        self.assertEqual(mapped['layers.0.attention.to_v.weight_scale'].rows,[8,9,10,11])
        self.assertIs(mapped['layers.0.attention.to_q.comfy_quant'],config)
        self.assertEqual(mapped['layers.0.feed_forward.w3.weight'].shape,(10,256))
        self.assertEqual(mapped['layers.0.feed_forward.w2.weight'].shape,(4,10))

    def test_real_cpu_load_keeps_int8_storage_and_correct_linear_embedding_math(self):
        root=Path(__file__).resolve().parents[1]
        sys.path[:0]=[str(root/'runtime/vision/core'),str(root/'runtime/vision/packages')]
        try:
            import comfy.cli_args
            comfy.cli_args.args.cpu=True
            import torch
        except ImportError:raise unittest.SkipTest('Optional local image runtime is not installed.')
        class Tiny(torch.nn.Module):
            def __init__(self):
                super().__init__();self.linear=torch.nn.Linear(256,8,bias=False,device='meta');self.embedding=torch.nn.Embedding(32,256,device='meta')
        model=Tiny();generator=torch.Generator().manual_seed(7)
        config=torch.tensor(list(json.dumps({'format':'int8_tensorwise','convrot':True,'convrot_groupsize':256}).encode()),dtype=torch.uint8)
        state={}
        for name,rows in (('linear',8),('embedding',32)):
            state[name+'.weight']=torch.randint(-127,128,(rows,256),dtype=torch.int8,generator=generator)
            state[name+'.weight_scale']=torch.full((rows,1),.002,dtype=torch.float32)
            state[name+'.comfy_quant']=config
        self.assertEqual(install_quantized_modules(model,state,torch),2)
        self.assertEqual(model.linear.weight._qdata.dtype,torch.int8)
        self.assertEqual(model.embedding.weight._qdata.dtype,torch.int8)
        model.to('cpu');model.linear._full_precision_mm=True
        with torch.no_grad():
            x=torch.randn(2,256,dtype=torch.bfloat16,generator=generator)
            actual=model.linear(x);expected=torch.nn.functional.linear(x,model.linear.weight.dequantize())
            self.assertTrue(torch.allclose(actual,expected,atol=.01,rtol=.01))
            indices=torch.tensor([1,7,3]);embedding=model.embedding(indices)
            self.assertTrue(torch.allclose(embedding,model.embedding.weight.dequantize()[indices],atol=.01,rtol=.01))
