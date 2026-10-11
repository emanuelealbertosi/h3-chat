"""Allocator compatibility and initialization order without GPU inference."""
import ast,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class VideoAllocatorTests(unittest.TestCase):
    def setUp(self):
        self.tree=ast.parse((ROOT/'native/video-worker.py').read_text(encoding='utf-8'))
        node=next(n for n in self.tree.body if isinstance(n,ast.FunctionDef) and n.name=='configure_cuda_allocator')
        namespace={};exec(compile(ast.Module(body=[node],type_ignores=[]),'<allocator>', 'exec'),namespace)
        self.configure=namespace['configure_cuda_allocator']

    def test_bundled_cuda_uses_async_but_unsupported_builds_keep_default(self):
        for version in ('2.13.0+cu130','2.6.0+cu124','2.0.0+cu118'):
            env={};self.assertTrue(self.configure(env,version))
            self.assertEqual(env,{'PYTORCH_CUDA_ALLOC_CONF':'backend:cudaMallocAsync'})
        for version in ('','2.13.0','2.13.0+rocm6.2','1.13.0+cu117','2.0.0+cu113'):
            env={};self.assertFalse(self.configure(env,version));self.assertEqual(env,{})

    def test_explicit_configuration_and_new_variable_precedence(self):
        for env,async_expected in (
            ({'PYTORCH_CUDA_ALLOC_CONF':'backend:native,max_split_size_mb:128'},False),
            ({'PYTORCH_CUDA_ALLOC_CONF':'backend:cudaMallocAsync'},True),
            ({'PYTORCH_ALLOC_CONF':'backend:native','PYTORCH_CUDA_ALLOC_CONF':'backend:cudaMallocAsync'},False),
            ({'PYTORCH_ALLOC_CONF':'backend:cudaMallocAsync','PYTORCH_CUDA_ALLOC_CONF':'backend:native'},True),
            ({'PYTORCH_ALLOC_CONF':'garbage_collection_threshold:0.8'},False),
        ):
            before=env.copy();self.assertEqual(self.configure(env,'2.13.0+cu130'),async_expected)
            self.assertEqual(env,before)

    def test_allocator_is_selected_before_torch_import_in_fresh_worker(self):
        worker=next(n for n in self.tree.body if isinstance(n,ast.ClassDef) and n.name=='Worker')
        load=next(n for n in worker.body if isinstance(n,ast.FunctionDef) and n.name=='load')
        selection=next(n.lineno for n in ast.walk(load) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='configure_cuda_allocator')
        imports=[n.lineno for n in ast.walk(load) if isinstance(n,ast.Import) and any(a.name=='torch' for a in n.names)]
        self.assertLess(selection,min(imports))

if __name__=='__main__':unittest.main()
