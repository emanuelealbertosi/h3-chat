"""Multimodal workspace budget uses every image, without shrinking references."""
import ast,json,math,unittest,weakref,gc
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[1]

class VideoConditioningMemoryTests(unittest.TestCase):
    def setUp(self):
        tree=ast.parse((ROOT/'native/video-worker.py').read_text(encoding='utf-8'))
        definitions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='conditioning_memory' or isinstance(n,ast.ClassDef) and n.name=='Worker']
        namespace={'math':math,'json':json,'logging':Mock()}
        exec(compile(ast.Module(body=definitions,type_ignores=[]),'<video memory>', 'exec'),namespace)
        self.estimate=namespace['conditioning_memory'];self.Worker=namespace['Worker']

    def test_all_nine_images_expand_the_workspace_not_just_placeholders(self):
        image={'type':'image','data':SimpleNamespace(shape=(1,768,1344,3))}
        tokens={'qwen3vl_32b':[[(123,1)]*200+[(image,1)]*9]}
        before=list(tokens['qwen3vl_32b'][0])
        # 768/32 * 1344/32 = 1008 merged tokens per image.
        expected=(200+9*24*42)*5120*96+24*42*4*1152*48
        self.assertEqual(self.estimate(tokens),expected)
        self.assertGreater(self.estimate(tokens),4*1024**3)
        self.assertEqual(tokens['qwen3vl_32b'][0],before)
        tokens['qwen3vl_32b'][0]=before[:203]
        self.assertLess(self.estimate(tokens),expected)

    def test_text_only_and_odd_dimensions_have_finite_workspace(self):
        self.assertEqual(self.estimate({'qwen3vl_32b':[[(12,1)]*10]}),10*5120*96)
        image={'type':'image','data':SimpleNamespace(shape=(1,33,65,3))}
        self.assertEqual(self.estimate({'qwen3vl_32b':[[(image,1)]]}),6*5120*96+24*1152*48)

    def test_discard_drops_cast_buffer_references_before_collecting_models(self):
        worker=self.Worker();retained=[]
        class Model:pass
        worker.clip=Model();old=weakref.ref(worker.clip);retained.append(worker.clip)
        management=SimpleNamespace(reset_cast_buffers=retained.clear,cleanup_models=Mock(),soft_empty_cache=Mock())
        worker.comfy=SimpleNamespace(model_management=management)
        worker.discard('clip');gc.collect()
        self.assertIsNone(old());management.cleanup_models.assert_called_once()

    def test_memory_telemetry_reports_only_live_models(self):
        worker=self.Worker();worker.torch=SimpleNamespace(cuda=SimpleNamespace(mem_get_info=lambda:(5*1024**2,16*1024**2),memory_allocated=lambda:4*1024**2,memory_reserved=lambda:7*1024**2))
        worker.comfy=SimpleNamespace(model_management=SimpleNamespace(current_loaded_models=[SimpleNamespace(model=None),SimpleNamespace(model=SimpleNamespace(model=object()))],TOTAL_PINNED_MEMORY=3*1024**2))
        snapshot=worker.memory_snapshot('sampling')
        self.assertEqual(snapshot['allocated_mb'],4);self.assertEqual(snapshot['reserved_mb'],7)
        self.assertEqual(snapshot['pinned_mb'],3);self.assertEqual(snapshot['loaded_models'],['object'])

if __name__=='__main__':unittest.main()
