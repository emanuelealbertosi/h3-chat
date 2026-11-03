"""Scoped torchaudio I/O bridge for the pinned MOSS processor on portable Windows.

The model calls only load and functional.resample. Use H3's existing PyAV and
band-limited torch resampler; no incompatible torchaudio native DLL is loaded.
"""
import importlib.machinery,sys,types

def install():
    import torch,av,numpy as np
    def load(path):
        parts=[];samples=0
        with av.open(str(path),options={'protocol_whitelist':'file'}) as source:
            if not source.streams.audio:raise ValueError('Il riferimento non contiene audio.')
            rate=source.streams.audio[0].codec_context.sample_rate
            resampler=av.AudioResampler(format='fltp',layout='stereo',rate=rate)
            for frame in source.decode(audio=0):
                for piece in resampler.resample(frame):
                    samples+=piece.samples
                    if samples>rate*30:raise ValueError('Il riferimento vocale deve durare al massimo 30 secondi.')
                    parts.append(piece.to_ndarray())
            for piece in resampler.resample(None):parts.append(piece.to_ndarray())
        if not parts:raise ValueError('Riferimento vocale vuoto.')
        return torch.from_numpy(np.concatenate(parts,axis=1)),rate
    def resample(waveform,orig_freq,new_freq,**kwargs):
        from h3_voice_resample import resample as sinc
        return sinc(waveform,int(orig_freq),int(new_freq))
    module=types.ModuleType('torchaudio');module.__spec__=importlib.machinery.ModuleSpec('torchaudio',loader=None);module.__version__='0.0.0';module.load=load
    functional=types.ModuleType('torchaudio.functional');functional.resample=resample;functional.__spec__=importlib.machinery.ModuleSpec('torchaudio.functional',loader=None);module.functional=functional
    sys.modules['torchaudio']=module;sys.modules['torchaudio.functional']=functional
