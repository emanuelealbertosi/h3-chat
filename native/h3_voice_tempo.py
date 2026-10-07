"""Pitch-preserving modest speech tempo adjustment using the bundled PyAV."""
def adjust(wav,rate,factor=1):
    if factor==1:return wav
    if not .9<=factor<=1.15:raise ValueError('Ritmo voce: da 0,90 a 1,15.')
    import av,numpy as np
    from fractions import Fraction
    frame=av.AudioFrame.from_ndarray(np.ascontiguousarray(wav[None,:],dtype=np.float32),format='fltp',layout='mono');frame.sample_rate=rate;frame.time_base=Fraction(1,rate);frame.pts=0
    graph=av.filter.Graph();source=graph.add_abuffer(sample_rate=rate,format='fltp',layout='mono',channels=1,time_base=Fraction(1,rate));tempo=graph.add('atempo',str(factor));sink=graph.add('abuffersink');source.link_to(tempo);tempo.link_to(sink);graph.configure();graph.push(frame);graph.push(None)
    parts=[]
    while True:
        try:parts.append(graph.pull().to_ndarray().reshape(-1))
        except (av.error.EOFError,av.error.BlockingIOError):break
    return np.concatenate(parts).astype(np.float32) if parts else wav
