"""No Torch imports, model weights or CUDA execution in these checks."""
import ast
import copy
import json
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MethodType, SimpleNamespace
import textwrap
import unittest
from unittest.mock import patch

from h3chat import video_phase_diagnostics as diagnostic


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT/'runtime/vision/core/comfy/ldm/minimax/model.py'
ENGINE = ROOT/'runtime/veda/60bfae688897dc41bc8685ca9f3130d7ed8f3b0c/veda_comfy/core/engine.py'


def native_function(path, class_name, name, namespace=None):
    if not path.is_file():raise unittest.SkipTest('Optional local video runtime is not installed.')
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == class_name)
    definition = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == name)
    compile_tree = ast.Module(body=[ast.ImportFrom(module='__future__',
        names=[ast.alias(name='annotations')], level=0), copy.deepcopy(definition)], type_ignores=[])
    ast.fix_missing_locations(compile_tree)
    values = {'torch': SimpleNamespace(no_grad=lambda: lambda f: f), **(namespace or {})}
    exec(compile(compile_tree, str(path), 'exec'), values)
    return definition, values[name]


class CUDA:
    def __init__(self): self.synchronizations = 0
    def synchronize(self): self.synchronizations += 1
    def memory_allocated(self): return 10
    def memory_reserved(self): return 20
    def max_memory_allocated(self): return 30
    def max_memory_reserved(self): return 40
    def mem_get_info(self): return 50, 100


class Identity:
    def forward(self, x, *args, **kwargs): return x
    def __call__(self, *args, **kwargs): return self.forward(*args, **kwargs)


class NativeAttention:
    pass


class Block:
    def __init__(self, attention):
        self.attn = attention
        self.norm1 = Identity(); self.norm2 = Identity()
        self.adaln_proj = Identity(); self.mlp = Identity()
        self.executions = 0
    def forward(self, x, *args, **kwargs):
        self.executions += 1
        return self.mlp(self.norm2(x))


class EngineStub:
    attention = native_function(ENGINE, 'VedaEngine', 'attention')[1] if ENGINE.is_file() else lambda *args: None
    def __init__(self): self.chunking = {'heads_per_chunk': 1}; self.timer = lambda _: None
    def _weights(self): return None
    def _chunk_bytes(self): return 128
    def _tile_layout(self): return None


class ProbeTests(unittest.TestCase):
    def probe(self, folder):
        self.cuda = CUDA()
        return diagnostic.FirstBlockProbe(SimpleNamespace(cuda=self.cuda), folder, head_chunks=56)

    def test_rewrites_only_phase_contexts_on_exact_reviewed_vendor(self):
        with TemporaryDirectory() as folder:
            probe = self.probe(folder)
            for path, cls, name, kind in ((MODEL, 'Attention', 'forward', 'attention'),
                                         (ENGINE, 'VedaEngine', 'attention', 'engine')):
                definition, original = native_function(path, cls, name)
                captured = []
                real_compile = compile
                def capture(tree, *args, **kwargs):
                    captured.append(copy.deepcopy(tree)); return real_compile(tree, *args, **kwargs)
                before = path.read_bytes()
                with patch.object(diagnostic, 'compile', side_effect=capture, create=True):
                    rewritten = diagnostic._rewrite(original, kind, probe)
                transformed = captured[-1].body[0]
                class Undo(ast.NodeTransformer):
                    def visit_With(self, node):
                        if (isinstance(node.items[0].context_expr, ast.Call)
                                and ast.unparse(node.items[0].context_expr.func) == '_h3_probe.phase'):
                            return node.body[0]
                        return self.generic_visit(node)
                restored = Undo().visit(transformed)
                expected = ast.parse(textwrap.dedent(inspect.getsource(original))).body[0]
                self.assertEqual(ast.dump(restored), ast.dump(expected))
                self.assertEqual(path.read_bytes(), before)
                self.assertIs(rewritten.__defaults__, original.__defaults__)

    def test_unreviewed_forward_is_rejected_without_running_it(self):
        class Other:
            def forward(self, x): raise AssertionError('must not run')
        with TemporaryDirectory() as folder:
            probe = self.probe(folder)
            with self.assertRaisesRegex(ValueError, 'not reviewed'):
                diagnostic._rewrite(Other.forward, 'attention', probe)

    def test_opt_in_synchronizes_and_flushes_start_before_execution(self):
        with TemporaryDirectory() as folder:
            probe = self.probe(folder)
            with probe.phase('inactive'):
                pass
            self.assertEqual(self.cuda.synchronizations, 0)
            self.assertFalse(probe.events.exists())
            probe.active = True
            with probe.phase('qkv_projection'):
                events = [json.loads(x) for x in probe.events.read_text().splitlines()]
                self.assertEqual(events[-1]['event'], 'phase_start')
                self.assertEqual(events[-1]['memory']['driver_free_bytes'], 50)
                self.assertEqual(self.cuda.synchronizations, 1)
            self.assertEqual(self.cuda.synchronizations, 2)
            events = [json.loads(x) for x in probe.events.read_text().splitlines()]
            self.assertEqual(events[-1]['event'], 'phase_end')
            self.assertEqual(probe.phase_counts, {'qkv_projection': 1})

    def test_probe_stops_after_exactly_one_block_and_restores_everything(self):
        _, forward = native_function(MODEL, 'Attention', 'forward')
        attention = NativeAttention(); attention.forward = MethodType(forward, attention)
        block = Block(attention)
        engine = EngineStub()
        engine_for = lambda device: engine
        veda = SimpleNamespace(_engine=engine_for, _engines={'cuda:0': engine})
        original = attention.forward
        with TemporaryDirectory() as folder:
            probe = self.probe(folder)
            probe.install(SimpleNamespace(blocks=[block]), veda)
            self.assertIs(veda._engine('cuda:0'), engine)
            with self.assertRaises(diagnostic.ProbeComplete):
                block.forward(SimpleNamespace(shape=(165873, 5376), dtype='bf16'))
            self.assertEqual(block.executions, 1)
            self.assertEqual(probe.completed_blocks, 1)
            self.assertFalse(probe.active)
            self.assertFalse(isinstance(diagnostic.ProbeComplete(), Exception))
            probe.close('done'); probe.close('error')
            result = json.loads(probe.result.read_text())
            self.assertEqual(result['status'], 'done')
            self.assertEqual(result['completed_blocks'], 1)
            self.assertEqual(result['head_chunks'], 56)
            self.assertEqual(result['chunking'], [{'heads_per_chunk': 1}])
            self.assertEqual(attention.forward, original)
            self.assertIs(veda._engine, engine_for)
            self.assertNotIn('forward', block.__dict__)
            self.assertNotIn('forward', block.mlp.__dict__)
            self.assertNotIn('attention', engine.__dict__)

    def test_kitchen_records_success_and_actual_cublas_fallback_without_arguments(self):
        kernels = SimpleNamespace(cutlass_int8_dequant=lambda *args: False,
                                  cublas_gemm_int8=lambda *args: None)
        original = kernels.cutlass_int8_dequant
        module = SimpleNamespace(_C=kernels)
        with TemporaryDirectory() as folder, patch.dict('sys.modules', {'comfy_kitchen.backends.cuda': module}):
            probe = self.probe(folder)
            probe._kitchen(); probe.active = True
            private_tensor = object()
            self.assertFalse(kernels.cutlass_int8_dequant(private_tensor))
            kernels.cublas_gemm_int8(private_tensor)
            self.assertEqual([x['kernel'] for x in probe.int8_calls],
                             ['cutlass_int8_dequant', 'cublas_gemm_int8'])
            self.assertFalse(probe.int8_calls[0]['used'])
            self.assertNotIn('args', probe.events.read_text())
            probe.close('done')
            self.assertIs(kernels.cutlass_int8_dequant, original)

    def test_operation_error_is_logged_and_keeps_original_exception(self):
        with TemporaryDirectory() as folder:
            probe = self.probe(folder); probe.active = True
            with self.assertRaisesRegex(RuntimeError, 'sentinel'):
                with probe.phase('veda.kernel'):
                    raise RuntimeError('sentinel')
            self.assertEqual(probe.stack, [])
            events = [json.loads(x) for x in probe.events.read_text().splitlines()]
            self.assertEqual(events[-1]['event'], 'phase_error')
            self.assertEqual(events[-1]['error'], 'RuntimeError')


if __name__ == '__main__': unittest.main()
