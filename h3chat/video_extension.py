"""Private native H3 short-context extension. No changes to vendor inference code."""

CONTEXT_FRAMES = 5  # Smallest native temporal VAE block (17k+5).


def window(frames, side):
    if type(frames) is not int or frames not in (120,240,360) or side not in ('before','after'):
        raise ValueError('Estensione video: scegli 5, 10 o 15 secondi e prima/dopo.')
    return {'frames':frames+CONTEXT_FRAMES,'trim_start':CONTEXT_FRAMES if side=='after' else 0,
            'guide_start':0 if side=='after' else frames,'output_frames':frames}


def pad_audio(audio, spec):
    import torch
    rate=audio['sample_rate'];count=round(CONTEXT_FRAMES/24*rate)
    return audio|{'waveform':torch.nn.functional.pad(audio['waveform'],(count,0) if spec['trim_start'] else (0,count))}


def trim_audio(audio, spec):
    rate=audio['sample_rate'];start=round(spec['trim_start']/24*rate);count=round(spec['output_frames']/24*rate)
    return audio|{'waveform':audio['waveform'][...,start:start+count]}
