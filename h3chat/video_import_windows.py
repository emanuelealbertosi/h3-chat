"""Frame-exact import windows that meet MiniMax's one-second minimum."""

def windows(total_frames, segment_seconds=15):
    if type(total_frames) is not int or total_frames < 24:
        raise ValueError('Il video deve contenere almeno un secondo.')
    if type(segment_seconds) is not int or segment_seconds not in (10, 15):
        raise ValueError('Segmenti del video esterno: scegli 10 o 15 secondi.')
    size = segment_seconds * 24
    starts = list(range(0, total_frames, size))
    # Borrow only the missing frames from the preceding window. No footage
    # is discarded, repeated or shifted relative to the soundtrack.
    if len(starts) > 1 and total_frames - starts[-1] < 24:
        starts[-1] = total_frames - 24
    ends = starts[1:] + [total_frames]
    return [(start, end - start) for start, end in zip(starts, ends)]
