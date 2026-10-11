"""Compatibility for sub-grid annotations; model files remain unmodified."""
import importlib


def generate_score(notation, *args, **kwargs):
    """Retry annotations occupying zero cells of the model's ABC grid.

    Raw notes, MIDI and annotations stay intact. This runs in the dedicated
    transcription child; the temporary override cannot affect another job.
    """
    try:
        return notation.generate_abc_from_data(*args, **kwargs)
    except ValueError as error:
        if not str(error).endswith('is shorter than the ABC subbeat grid'):
            raise
    original_fill = notation._fill_intervals
    skipped = []

    def fill(rows, grid, *, default, dtype):
        kept = []
        for start, end, value in rows:
            first = max(0, min(notation._quantize_time(start, grid), len(grid)-1))
            last = max(0, min(notation._quantize_time(end, grid), len(grid)-1))
            if last <= first:
                skipped.append(f'notation only: annotation {start:.6f}-{end:.6f} ({value}) occupies no ABC grid cell; raw annotation retained')
            else:
                kept.append((start, end, value))
        return original_fill(kept, grid, default=default, dtype=dtype)

    notation._fill_intervals = fill
    try:
        text, score = notation.generate_abc_from_data(*args, **kwargs)
    finally:
        notation._fill_intervals = original_fill
    score.diagnostics.extend(skipped)
    return text, score


def install_export_compatibility(model):
    exports = importlib.import_module(model.__class__.__module__.rsplit('.', 1)[0]+'.exports_sheetsage2')
    if getattr(exports.generate_abc_from_data, '_h3_notation_compatibility', False):
        return
    notation = importlib.import_module(exports.generate_abc_from_data.__module__)

    def compatible(*args, **kwargs):
        return generate_score(notation, *args, **kwargs)

    compatible._h3_notation_compatibility = True
    exports.generate_abc_from_data = compatible
