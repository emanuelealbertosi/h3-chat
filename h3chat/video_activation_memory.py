"""Release H3's copied input activations before its transformer blocks.

The native forward assembles a separate packed ``h`` tensor, but normally
retains the projection outputs and temporary packed rows for the whole call.
Only their Python references are released here: tensor values, guides, model
weights, attention, and sampler operations are unchanged.  No Torch import or
CUDA/cache operation is needed, and the pinned inference library stays intact.
"""
import ast
import hashlib
import inspect
import textwrap
from types import MethodType


# AST fingerprint, independent of comments, indentation and line endings.
# An updated runtime must be reviewed explicitly before applying this adapter.
_SUPPORTED_FORWARD_SHA256 = '574fa101e3c644ff192b7094aacc6cf1eb1e9850e9db14fe9dbd093d04f16bad'
_TEMPORARIES = (
    'video_embed', 'audio_embed', 'all_video_rows', 'all_audio_rows',
    'video_rows', 'audio_rows', 'cond_video_rows', 'cond_audio_rows',
    'text_states', 'img_update', 'audio_update',
)
_MARKER = '_h3_activation_memory_report'


def _fingerprint(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def _rewrite(function):
    if function.__closure__:
        raise ValueError('forward closure changed')
    source = textwrap.dedent(inspect.getsource(function))
    tree = ast.parse(source)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError('forward definition changed')
    definition = tree.body[0]
    if definition.name != '_forward' or _fingerprint(definition) != _SUPPORTED_FORWARD_SHA256:
        raise ValueError('forward source not reviewed')

    # Insert immediately after the final copy into h, before timestep/rotary
    # preparation and all transformer blocks. Check every subsequent nested
    # expression too; a future use must never become an unbound local.
    assembly = [i for i, node in enumerate(definition.body)
                if isinstance(node, ast.For)
                and isinstance(node.iter, ast.Attribute)
                and isinstance(node.iter.value, ast.Name)
                and node.iter.value.id == 'layout' and node.iter.attr == 'segments'
                and any(isinstance(part, ast.Name) and isinstance(part.ctx, ast.Load)
                        and part.id == 'video_embed' for part in ast.walk(node))]
    if len(assembly) != 1:
        raise ValueError('packed activation assembly changed')
    position = assembly[0] + 1
    later = ast.Module(body=definition.body[position:], type_ignores=[])
    if any(isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
           and node.id in _TEMPORARIES for node in ast.walk(later)):
        raise ValueError('temporary used after assembly')
    assigned = {node.id for node in ast.walk(ast.Module(body=definition.body[:position], type_ignores=[]))
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
    if not set(_TEMPORARIES).issubset(assigned):
        raise ValueError('temporary assignment changed')
    deletion = ast.Delete(targets=[ast.Name(id=name, ctx=ast.Del()) for name in _TEMPORARIES])
    ast.copy_location(deletion, definition.body[position])
    definition.body.insert(position, deletion)
    ast.fix_missing_locations(tree)
    ast.increment_lineno(tree, function.__code__.co_firstlineno - 1)
    namespace = {}
    exec(compile(tree, function.__code__.co_filename, 'exec'), function.__globals__, namespace)
    replacement = namespace['_forward']
    replacement.__defaults__ = function.__defaults__
    replacement.__kwdefaults__ = function.__kwdefaults__
    replacement.__qualname__ = function.__qualname__
    replacement.__module__ = function.__module__
    replacement.__doc__ = function.__doc__
    return replacement


def install(diffusion):
    """Adapt this model instance, or retain its original compatible fallback.

    The report records installation, not measured VRAM savings. It is emitted
    with each generated clip so comparisons can verify the code path used.
    """
    previous = getattr(diffusion, _MARKER, None)
    if previous is not None:
        return dict(previous)
    report = {'active': False, 'temporaries_released': [], 'source_guard': 'unsupported'}
    original = getattr(diffusion, '_forward', None)
    if not inspect.ismethod(original) or original.__self__ is not diffusion:
        report['reason'] = 'forward method unavailable'
        return report
    try:
        replacement = _rewrite(original.__func__)
    except (OSError, TypeError, ValueError, SyntaxError) as exc:
        report['reason'] = str(exc)
        return report
    report.update(active=True, temporaries_released=list(_TEMPORARIES),
                  source_guard=_SUPPORTED_FORWARD_SHA256)
    diffusion._forward = MethodType(replacement, diffusion)
    setattr(diffusion, _MARKER, dict(report))
    return report
