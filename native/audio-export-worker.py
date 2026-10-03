"""Streaming audio conversion with app-private PyAV; no model or GPU loading."""
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/tools/documents'
sys.path.insert(0,str(RUNTIME))
dll=os.add_dll_directory(str(RUNTIME)) if os.name=='nt' and RUNTIME.is_dir() else None


def convert(source,output,format):
    import av
    if format not in ('wav','mp3'):raise ValueError('Formato audio non valido.')
    source=Path(source)
    input_format={'.wav':'wav','.mp3':'mp3','.flac':'flac','.ogg':'ogg'}.get(source.suffix.lower())
    if not input_format:raise ValueError('Formato audio non supportato.')
    samples=0
    with av.open(str(source),format=input_format,options={'protocol_whitelist':'file'}) as inp:
        if not inp.streams.audio:raise ValueError('Il file non contiene una traccia audio.')
        audio=inp.streams.audio[0]
        rate=audio.codec_context.sample_rate or 48000
        if format=='mp3' and rate not in (32000,44100,48000):rate=48000
        if not 8000<=rate<=192000:raise ValueError('Frequenza audio non supportata.')
        layout='mono' if audio.codec_context.channels==1 else 'stereo'
        with av.open(str(output),'w',format=format) as out:
            stream=out.add_stream('libmp3lame' if format=='mp3' else 'pcm_s16le',rate=rate)
            stream.layout=layout
            stream.format='fltp' if format=='mp3' else 's16'
            if format=='mp3':stream.bit_rate=320000
            resampler=av.AudioResampler(format=stream.format,layout=layout,rate=rate)
            for frame in inp.decode(audio):
                frame.pts=None
                samples+=frame.samples
                if samples>3600*audio.codec_context.sample_rate:raise ValueError('Esportazione audio: massimo un’ora per traccia.')
                for part in resampler.resample(frame):
                    for packet in stream.encode(part):out.mux(packet)
            if not samples:raise ValueError('La traccia audio è vuota.')
            for part in resampler.resample(None):
                for packet in stream.encode(part):out.mux(packet)
            for packet in stream.encode(None):out.mux(packet)


if __name__=='__main__':
    try:convert(*sys.argv[1:])
    except Exception:
        # Decoder errors can contain source paths or metadata. Keep them private.
        print('Impossibile convertire la traccia audio. Verifica che il file sia valido.',file=sys.stderr)
        sys.exit(1)
