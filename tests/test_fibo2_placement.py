import sys,types,unittest
from unittest.mock import Mock,patch
from h3chat.fibo2_placement import resident

GIB=1024**3

class Tensor:
    def __init__(self,size):self.size=size;self.data=self
    def numel(self):return self.size//2
    def element_size(self):return 2
    def to(self,device):return self

class Module:
    def __init__(self,size):self.size=size;self._parameters={};self.moves=[]
    def parameters(self,recurse=True):return [Tensor(self.size)] if self.size else []
    def buffers(self,recurse=True):return []
    def to(self,device):self.moves.append(device)

class PlacementTests(unittest.TestCase):
    def test_resident_weights_stay_on_gpu_and_only_remaining_blocks_stream(self):
        shared=Module(2*GIB);blocks=[Module(GIB) for _ in range(12)];transformer=Module(0)
        transformer.layers=blocks;transformer.named_children=lambda:[('shared',shared),('layers',blocks)]
        pipe=types.SimpleNamespace(transformer=transformer,text_encoder=Module(GIB),vae=Module(GIB//3))
        offload=Mock();hook=Mock();torch=types.SimpleNamespace(device=lambda s:s,cuda=types.SimpleNamespace(mem_get_info=lambda:(14*GIB,16*GIB)))
        with patch.dict(sys.modules,{'accelerate':types.SimpleNamespace(cpu_offload=offload),
                'accelerate.hooks':types.SimpleNamespace(AlignDevicesHook=Mock(),add_hook_to_module=hook)}):
            result=resident(pipe,torch)
        self.assertEqual((result['resident_blocks'],result['offloaded_blocks']),(8,4))
        self.assertEqual(result['resident_weights_gib'],10)
        self.assertTrue(all(b.moves==['cuda'] for b in blocks[:8]));self.assertTrue(all(not b.moves for b in blocks[8:]))
        self.assertEqual([c.args[0] for c in offload.call_args_list],[*blocks[8:],pipe.text_encoder])
        self.assertEqual(shared.moves,['cuda']);self.assertEqual(pipe.vae.moves,['cuda']);hook.assert_called_once()

    def test_low_memory_fails_before_moving_weights(self):
        pipe=Mock();torch=types.SimpleNamespace(device=lambda s:s,cuda=types.SimpleNamespace(mem_get_info=lambda:(5*GIB,16*GIB)))
        with patch.dict(sys.modules,{'accelerate':types.SimpleNamespace(cpu_offload=Mock()),
                'accelerate.hooks':types.SimpleNamespace(AlignDevicesHook=Mock(),add_hook_to_module=Mock())}):
            with self.assertRaisesRegex(ValueError,'6 GiB'):resident(pipe,torch)
        pipe.transformer.to.assert_not_called()
