"""Opt-in first-DiT-block measurements; never imported by normal sampling.

Instrumentation is process/instance scoped and leaves pinned vendor files alone.
Only a private diagnostic request enables CUDA synchronization. Every phase is
flushed before its work begins, so an externally stopped probe still identifies
the operation being measured. No tensors or operator arguments enter the log.
"""
from __future__ import annotations

import ast
import __future__
from contextlib import contextmanager
import hashlib
import inspect
import json
from pathlib import Path
import sys
import textwrap
import time
from types import MethodType


ATTENTION_SHA256 = '8eddeb2d5142cd97cb369ed1dba9a30562aac30483c0cf9e825cbc41b9375df2'
ENGINE_SHA256 = '49d4c242adc6f9c60c117a55ffc3316325b3c544edadd3daf3b5a5178a4bb5ac'


class ProbeComplete(BaseException):
    """Deliberate diagnostic boundary, not a render failure or VEDA fallback."""


def _fingerprint(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def _name_target(node):
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return None
    return node.targets[0].id if isinstance(node.targets[0], ast.Name) else None


def _timed(node, name):
    phase = ast.Call(func=ast.Attribute(value=ast.Name(id='_h3_probe', ctx=ast.Load()),
                                      attr='phase', ctx=ast.Load()),
                     args=[ast.Constant(name)], keywords=[])
    wrapped = ast.With(items=[ast.withitem(context_expr=phase)], body=[node])
    return ast.copy_location(wrapped, node)


def _rewrite(function, kind, probe):
    """Reviewed AST; wrap statements without splitting/reordering their operands."""
    function = inspect.unwrap(function)
    if function.__closure__:
        raise ValueError('diagnostic source closure changed')
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError('diagnostic function definition changed')
    definition = tree.body[0]
    expected = ATTENTION_SHA256 if kind == 'attention' else ENGINE_SHA256
    if _fingerprint(definition) != expected:
        raise ValueError(kind+' source not reviewed')
    found = []
    for index, node in enumerate(definition.body):
        label = None
        if kind == 'attention':
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Tuple):
                if [getattr(x, 'id', None) for x in node.targets[0].elts] == ['q', 'k', 'v']:
                    label = 'qkv_projection'
            elif isinstance(node, ast.If) and ast.unparse(node.test) == 'rope_freqs is not None':
                label = 'qk_norm_rope'
            elif _name_target(node) == 'out':
                label = 'optimized_attention'
            elif isinstance(node, ast.Return):
                label = 'attention_output_projection'
        elif kind == 'engine':
            if (_name_target(node) == 'out' and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Attribute)
                    and node.value.func.attr == 'new_empty'):
                label = 'veda.output_allocation'
            elif isinstance(node, ast.For):
                label = 'veda.head_groups'
        else:
            raise ValueError('unknown diagnostic source kind')
        if label:
            found.append(label)
            definition.body[index] = _timed(node, label)
    needed = (['qkv_projection', 'qk_norm_rope', 'optimized_attention',
               'attention_output_projection'] if kind == 'attention'
              else ['veda.output_allocation', 'veda.head_groups'])
    if found != needed:
        raise ValueError(kind+' phase locations changed')
    namespace = dict(function.__globals__)
    namespace['_h3_probe'] = probe
    ast.fix_missing_locations(tree)
    ast.increment_lineno(tree, function.__code__.co_firstlineno - 1)
    flags = function.__code__.co_flags & __future__.annotations.compiler_flag
    exec(compile(tree, function.__code__.co_filename, 'exec', flags=flags, dont_inherit=True), namespace)
    replacement = namespace[function.__name__]
    replacement.__defaults__ = function.__defaults__
    replacement.__kwdefaults__ = function.__kwdefaults__
    return replacement


class FirstBlockProbe:
    """Measure one genuine first block, then stop before block 1 or decoding.

    Call ``install(diffusion, veda_patch)`` only after LoRA/VEDA preparation,
    immediately before sampling. Catch ProbeComplete outside the sampler and
    call ``close('done')``. In all other exits call close('error'). The worker
    must be dedicated to diagnostics: no MP4 is produced by this mode.
    """
    def __init__(self, torch, folder, *, head_chunks, emit=None, clock=time.monotonic):
        self.torch = torch
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.events = self.folder/'phase-probe.jsonl'
        self.result = self.folder/'phase-probe-result.json'
        self.clock = clock
        self.started = clock()
        self.head_chunks = head_chunks
        self.emit = emit
        self.active = False
        self.stack = []
        self.restores = []
        self.phase_totals = {}
        self.phase_counts = {}
        self.engines = []
        self.int8_calls = []
        self.completed_blocks = 0
        self.source_guards = {}
        self.closed = False

    def snapshot(self):
        cuda = self.torch.cuda
        values = {}
        for name in ('memory_allocated', 'memory_reserved', 'max_memory_allocated', 'max_memory_reserved'):
            try:
                values[name+'_bytes'] = int(getattr(cuda, name)())
            except (AttributeError, RuntimeError, TypeError):
                pass
        try:
            free, total = cuda.mem_get_info()
            values.update(driver_free_bytes=int(free), driver_total_bytes=int(total))
        except (AttributeError, RuntimeError, TypeError):
            pass
        return values

    def record(self, event, **values):
        data = {'event': event, 'elapsed_seconds': self.clock()-self.started,
                'path': list(self.stack), 'memory': self.snapshot(), **values}
        with self.events.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(data, ensure_ascii=False)+'\n')

    @contextmanager
    def phase(self, name):
        if not self.active:
            yield
            return
        self.stack.append(name)
        self.record('phase_start', phase=name)
        started = self.clock()
        try:
            self.torch.cuda.synchronize()
            synchronized = self.clock()
            yield
            self.torch.cuda.synchronize()
        except BaseException as error:
            self.record('phase_error', phase=name, error=type(error).__name__,
                        seconds=self.clock()-started)
            raise
        else:
            seconds = self.clock()-started
            self.phase_totals[name] = self.phase_totals.get(name, 0)+seconds
            self.phase_counts[name] = self.phase_counts.get(name, 0)+1
            self.record('phase_end', phase=name, seconds=seconds,
                        entry_sync_seconds=synchronized-started)
        finally:
            self.stack.pop()

    def replace(self, obj, name, replacement):
        # Restore instance inheritance as inheritance, rather than keeping a
        # bound method alive after diagnostics are removed.
        own = name in getattr(obj, '__dict__', {})
        original = getattr(obj, name)
        setattr(obj, name, replacement)
        self.restores.append((obj, name, original, own))

    def wrap(self, obj, name, phase, *, result=None):
        original = getattr(obj, name)
        def wrapped(*args, **kwargs):
            with self.phase(phase):
                value = original(*args, **kwargs)
                if result is not None and self.active:
                    result(value)
                return value
        self.replace(obj, name, wrapped)

    def _engine(self, engine):
        if engine is None or any(item is engine for item in self.engines):
            return engine
        replacement = _rewrite(type(engine).attention, 'engine', self)
        self.replace(engine, 'attention', MethodType(replacement, engine))
        self.replace(engine, 'timer', lambda name: self.phase('veda.'+{'score': 'predictor', 'attend': 'kernel'}.get(name, name)))
        for method in ('_weights', '_chunk_bytes', '_tile_layout'):
            self.wrap(engine, method, 'veda.'+method.lstrip('_'))
        self.source_guards['veda_engine'] = ENGINE_SHA256
        self.engines.append(engine)
        return engine

    def _kitchen(self):
        kitchen = sys.modules.get('comfy_kitchen.backends.cuda')
        kernels = getattr(kitchen, '_C', None)
        for name in ('cutlass_int8_dequant', 'cutlass_int8_dequant_residual', 'cublas_gemm_int8'):
            if not callable(getattr(kernels, name, None)):
                continue
            def outcome(value, name=name):
                result = bool(value) if name.startswith('cutlass') else None
                data = {'kernel': name, 'used': result, 'path': list(self.stack)}
                self.int8_calls.append(data)
                self.record('int8_kernel', **data)
            try:
                self.wrap(kernels, name, 'int8.'+name, result=outcome)
            except (AttributeError, TypeError):
                self.record('instrumentation_unavailable', target=name)

    def install(self, diffusion, patch):
        if self.restores:
            raise ValueError('probe already installed')
        if patch is None:
            raise ValueError('first-block probe requires VEDA')
        block = diffusion.blocks[0]
        attention = block.attn
        original_attention = attention.forward
        replacement = _rewrite(original_attention.__func__, 'attention', self)
        try:
            self.replace(attention, 'forward', MethodType(replacement, attention))
            self.source_guards['attention'] = ATTENTION_SHA256
            for method in ('norm1', 'norm2', 'adaln_proj', 'mlp'):
                self.wrap(getattr(block, method), 'forward', 'block.'+method)
            original_engine = patch._engine
            self.replace(patch, '_engine', lambda device: self._engine(original_engine(device)))
            for engine in patch._engines.values():
                self._engine(engine)
            original_block = block.forward
            def run_first_block(*args, **kwargs):
                self.active = True
                try:
                    reset=getattr(self.torch.cuda,'reset_peak_memory_stats',None)
                    if callable(reset):reset()
                    first = args[0] if args else kwargs.get('x')
                    self.record('first_block_input', shape=list(first.shape), dtype=str(first.dtype),
                                head_chunks=self.head_chunks)
                    with self.phase('first_dit_block'):
                        original_block(*args, **kwargs)
                    self.completed_blocks += 1
                    self.record('first_block_complete')
                finally:
                    self.active = False
                # BaseException avoids VEDA's catch-Exception dense fallback.
                raise ProbeComplete()
            self.replace(block, 'forward', run_first_block)
            self._kitchen()
            self.record('installed', head_chunks=self.head_chunks, source_guards=self.source_guards)
        except BaseException:
            self.close('installation_error')
            raise
        return self

    def close(self, status):
        if self.closed:
            return
        self.closed = True
        self.active = False
        chunks = [dict(item.chunking) for item in self.engines]
        for obj, name, original, own in reversed(self.restores):
            if own:
                setattr(obj, name, original)
            else:
                delattr(obj, name)
        self.restores.clear()
        summary = {'status': status, 'completed_blocks': self.completed_blocks,
                   'head_chunks': self.head_chunks, 'elapsed_seconds': self.clock()-self.started,
                   'phase_seconds': self.phase_totals, 'phase_counts': self.phase_counts,
                   'chunking': chunks, 'int8_calls': self.int8_calls,
                   'source_guards': self.source_guards, 'memory': self.snapshot(),
                   'note': 'Diagnostic synchronization is enabled; nested phase durations overlap. CUDA peak counters are reset at first-block entry and remain cumulative across its phases. No video is rendered.'}
        self.result.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        self.record('closed', status=status)
