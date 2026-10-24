"""CPU-only checks: same packed values, shorter lifetimes, reviewed runtime only."""
import ast
import builtins
import copy
import inspect
from pathlib import Path
import unittest
import weakref
from types import MethodType, SimpleNamespace
from unittest.mock import patch

from h3chat import video_activation_memory as adapter


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT/'runtime/vision/core/comfy/ldm/minimax/model.py'


def native_forward():
    if not VENDOR.is_file():raise unittest.SkipTest('Optional local video runtime is not installed.')
    tree = ast.parse(VENDOR.read_text(encoding='utf-8'))
    model = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                 and node.name == 'MiniMaxH3Model')
    definition = next(node for node in model.body if isinstance(node, ast.FunctionDef)
                      and node.name == '_forward')
    namespace = {}
    exec(compile(ast.Module(body=[definition], type_ignores=[]), str(VENDOR), 'exec'), namespace)
    return definition, namespace['_forward']


class Mask:
    def __init__(self, values): self.values = values
    @property
    def shape(self): return (len(self.values),)
    def to(self, device): return self
    def __invert__(self): return Mask([not value for value in self.values])


class Matrix:
    """Small independent buffers; assignments copy like Torch tensor slices."""
    def __init__(self, rows): self.rows = [list(row) for row in rows]
    @property
    def shape(self): return (len(self.rows), len(self.rows[0]))
    def to(self, dtype): return self
    def __getitem__(self, key):
        if isinstance(key, Mask): return Matrix([r for r, keep in zip(self.rows, key.values) if keep])
        return Matrix(self.rows[key])
    def __setitem__(self, key, value):
        positions = ([i for i, keep in enumerate(key.values) if keep] if isinstance(key, Mask)
                     else list(range(len(self.rows)))[key])
        assert len(positions) == len(value.rows)
        for position, row in zip(positions, value.rows): self.rows[position] = list(row)


def probe(definition, with_conditions, refine_text):
    """Execute the real assembly statements without Torch, CUDA or model weights."""
    start = next(i for i, node in enumerate(definition.body)
                 if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                 and node.targets[0].id == 'img_update')
    end = next(i for i, node in enumerate(definition.body)
               if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
               and node.targets[0].id == 't_vals')
    function = ast.parse('def probe(self, video_x, audio_x, context, payload, layout):\n'
                         '    device = "cpu"\n    dtype = "half"\n').body[0]
    function.body.extend(copy.deepcopy(definition.body[start:end]))
    function.body.extend(ast.parse('checkpoint(h)\nreturn h').body)
    tracked = {}
    snapshots = []
    def matrix(name, rows):
        value = Matrix(rows); tracked[name] = weakref.ref(value)
        return value
    allocations = 0
    def empty(rows, columns, **kwargs):
        nonlocal allocations
        allocations += 1
        return matrix('buffer_'+str(allocations), [[0]*columns for _ in range(rows)])
    def projection(name, offset):
        return lambda value: matrix(name, [[sum(row)+offset+i for i in range(3)] for row in value.rows])
    namespace = {
        'torch': SimpleNamespace(float32='float32', empty=empty),
        'patchify_video': lambda *args: matrix('video_rows', [[1, 2], [3, 4]]),
        'pack_audio': lambda *args: matrix('audio_rows', [[10, 20]]),
        'checkpoint': lambda value: snapshots.append({name: ref() is not None for name, ref in tracked.items()}),
    }
    compile_tree = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(compile_tree, '<real-h3-packed-assembly>', 'exec'), namespace)
    model = SimpleNamespace(
        patch_size=(1, 2, 2), hidden_size=3,
        _cond_video_rows=lambda *args: matrix('cond_video_rows', [[100, 200]]) if with_conditions else None,
        _cond_audio_rows=lambda *args: matrix('cond_audio_rows', [[1000, 2000]]) if with_conditions else None,
        video_patch_proj=projection('video_embed', 1), audio_patch_proj=projection('audio_embed', 10),
        condition_proj=projection('condition_projection', 20),
        token_refiner=lambda value, **kwargs: matrix('refined_text', value.rows),
    )
    segments = [(0, 2, 'text')]
    cursor = 2
    if with_conditions:
        segments.extend([(2, 3, 'cond'), (3, 4, 'ref_audio')]); cursor = 4
    segments.extend([(cursor, cursor+1, 'audio'), (cursor+1, cursor+3, 'video')])
    layout = SimpleNamespace(segments=segments, seq_len=cursor+3,
        img_update=Mask(([False] if with_conditions else [])+[True, True]),
        audio_update=Mask(([False] if with_conditions else [])+[True]))
    context = [Matrix([[5, 6], [7, 8]] if refine_text else [[5, 6, 7], [8, 9, 10]])]
    source = SimpleNamespace(to=lambda dtype: object())
    namespace['transformer_options'] = {}
    result = namespace['probe'](model, source, source, context, {}, layout)
    return result.rows, snapshots[0]


class VideoActivationMemoryTests(unittest.TestCase):
    def rewritten_tree(self, function):
        captured = []
        def compile_and_capture(tree, *args, **kwargs):
            captured.append(copy.deepcopy(tree))
            return builtins.compile(tree, *args, **kwargs)
        with patch.object(adapter, 'compile', side_effect=compile_and_capture, create=True):
            replacement = adapter._rewrite(function)
        return replacement, captured[0].body[0]

    def test_only_change_is_deleting_dead_temporaries_after_packed_copy(self):
        definition, original = native_forward()
        before = VENDOR.read_bytes()
        replacement, rewritten = self.rewritten_tree(original)
        deletions = [node for node in rewritten.body if isinstance(node, ast.Delete)]
        self.assertEqual(len(deletions), 1)
        self.assertEqual([node.id for node in deletions[0].targets], list(adapter._TEMPORARIES))
        rewritten.body.remove(deletions[0])
        self.assertEqual(ast.dump(definition, include_attributes=False), ast.dump(rewritten, include_attributes=False))
        self.assertIs(replacement.__globals__, original.__globals__)
        self.assertIs(replacement.__defaults__, original.__defaults__)
        self.assertEqual(inspect.signature(replacement), inspect.signature(original))
        self.assertEqual(VENDOR.read_bytes(), before)

    def test_real_assembly_values_are_identical_and_copies_die_before_blocks(self):
        definition, original = native_forward()
        _, rewritten = self.rewritten_tree(original)
        for conditions in (False, True):
            for refine_text in (False, True):
                with self.subTest(conditions=conditions, refine_text=refine_text):
                    expected, old_lifetimes = probe(definition, conditions, refine_text)
                    actual, new_lifetimes = probe(rewritten, conditions, refine_text)
                    self.assertEqual(actual, expected)
                    names = ['video_rows', 'audio_rows', 'video_embed', 'audio_embed']
                    if conditions: names += ['cond_video_rows', 'cond_audio_rows']
                    if refine_text: names += ['refined_text']
                    for name in names:
                        self.assertTrue(old_lifetimes[name], name)
                        self.assertFalse(new_lifetimes[name], name)
                    # h survives and owns the copies; conditional row buffers
                    # must also be gone, while the final buffer remains alive.
                    buffers = [name for name in new_lifetimes if name.startswith('buffer_')]
                    self.assertTrue(new_lifetimes[buffers[-1]])
                    self.assertTrue(all(not new_lifetimes[name] for name in buffers[:-1]))

    def test_instance_scoped_idempotent_installation_and_report(self):
        _, original = native_forward()
        first, second = SimpleNamespace(), SimpleNamespace()
        first._forward = MethodType(original, first)
        second._forward = MethodType(original, second)
        report = adapter.install(first)
        self.assertTrue(report['active'])
        self.assertEqual(report['source_guard'], adapter._SUPPORTED_FORWARD_SHA256)
        self.assertEqual(report['temporaries_released'], list(adapter._TEMPORARIES))
        self.assertIs(second._forward.__func__, original)
        replacement = first._forward
        self.assertEqual(adapter.install(first), report)
        self.assertIs(first._forward, replacement)
        report['active'] = False
        self.assertTrue(adapter.install(first)['active'])

    def test_unreviewed_or_already_wrapped_runtime_keeps_original_method(self):
        class ChangedModel:
            def _forward(self, x): return x
        model = ChangedModel(); original = model._forward
        report = adapter.install(model)
        self.assertFalse(report['active'])
        self.assertEqual(report['source_guard'], 'unsupported')
        self.assertEqual(model._forward, original)
        self.assertEqual(model._forward('unchanged'), 'unchanged')
        self.assertFalse(adapter.install(SimpleNamespace())['active'])
        self.assertFalse(adapter.install(SimpleNamespace(_forward=lambda: None))['active'])

    def test_later_use_guard_rejects_even_if_a_new_digest_were_added_accidentally(self):
        definition, original = native_forward()
        modified = copy.deepcopy(definition)
        modified.body.append(ast.parse('return video_embed').body[0])
        source = ast.unparse(modified)
        with patch.object(adapter.inspect, 'getsource', return_value=source), \
                patch.object(adapter, '_SUPPORTED_FORWARD_SHA256', adapter._fingerprint(modified)):
            with self.assertRaisesRegex(ValueError, 'temporary used after assembly'):
                adapter._rewrite(original)

    def test_worker_keeps_adapter_report_after_releasing_diffuser(self):
        tree = ast.parse((ROOT/'native/video-worker.py').read_text(encoding='utf-8'))
        done = next(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name) and node.func.id == 'emit'
                    and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 'done')
        parameters = next(item.value for item in done.keywords if item.arg == 'parameters')
        expression = next(value for key, value in zip(parameters.keys, parameters.values)
                          if isinstance(key, ast.Constant) and key.value == 'activation_memory')
        code = compile(ast.Expression(body=expression), '<worker-activation-report>', 'eval')
        report = {'active': True, 'temporaries_released': list(adapter._TEMPORARIES), 'source_guard': adapter._SUPPORTED_FORWARD_SHA256}
        worker = SimpleNamespace(model=None, activation_memory_report=report)
        self.assertEqual(eval(code, {'self': worker}), report)
        self.assertFalse(eval(code, {'self': SimpleNamespace(model=None)})['active'])


if __name__ == '__main__': unittest.main()
