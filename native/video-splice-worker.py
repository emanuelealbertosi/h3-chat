"""Replace a frame interval without retiming either side or the new footage."""
import json
import os
from pathlib import Path
import sys
from fractions import Fraction

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/tools/documents'
sys.path.insert(0,str(RUNTIME))
dll=os.add_dll_directory(str(RUNTIME)) if os.name=='nt' and RUNTIME.is_dir() else None
wire=sys.stdout


def emit(event,**kw):
    wire.write(json.dumps({'event':event,**kw},ensure_ascii=False)+'\n');wire.flush()


def splice(original,replacement,output,start_frame,end_frame,total_frames):
    import av
    if any(type(n) is not int for n in (start_frame,end_frame,total_frames)) or not 0<=start_frame<end_frame<=total_frames<=360:
        raise ValueError('Intervallo di sostituzione non valido.')
    destination=Path(output)
    if destination.resolve() in (Path(original).resolve(),Path(replacement).resolve()):
        raise ValueError('Il montaggio deve creare un nuovo file.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    partial=destination.with_suffix('.partial.mp4')
    try:
        with av.open(original,options={'protocol_whitelist':'file'}) as old, av.open(replacement,options={'protocol_whitelist':'file'}) as new:
            if not old.streams.video or not new.streams.video:raise ValueError('Una clip non contiene video.')
            before,after=old.streams.video[0],new.streams.video[0]
            if before.average_rate!=24 or after.average_rate!=24 or (before.width,before.height)!=(after.width,after.height):
                raise ValueError('La sostituzione deve conservare formato e 24 fotogrammi al secondo.')
            written=0;original_count=0
            with av.open(str(partial),'w',format='mp4',options={'movflags':'+faststart'}) as out:
                video=out.add_stream('libx264',rate=24);video.width=before.width;video.height=before.height;video.pix_fmt='yuv420p';video.options={'crf':'18','preset':'fast'}
                def write(frame):
                    nonlocal written
                    frame=frame.reformat(format='yuv420p');frame.pts=written;frame.time_base=Fraction(1,24)
                    for packet in video.encode(frame):out.mux(packet)
                    written+=1
                for index,frame in enumerate(old.decode(before)):
                    original_count+=1
                    if original_count>total_frames:raise ValueError('La clip originale supera la durata salvata.')
                    if index==start_frame:
                        emit('stage',message='Post-produzione · inserimento del tratto rigenerato')
                        generated=0
                        for new_frame in new.decode(after):
                            generated+=1
                            if generated>end_frame-start_frame:raise ValueError('Il tratto rigenerato è più lungo del richiesto.')
                            write(new_frame)
                        if generated!=end_frame-start_frame:raise ValueError('Il tratto rigenerato non copre l’intervallo richiesto.')
                    if index<start_frame or index>=end_frame:write(frame)
                if original_count!=total_frames or written!=total_frames:raise ValueError('La clip non conserva la durata originale.')
                for packet in video.encode(None):out.mux(packet)
        partial.replace(destination)
        return {'path':str(destination),'frames':written,'fps':24,'duration':written/24}
    finally:
        partial.unlink(missing_ok=True)


if __name__=='__main__':
    emit('hello')
    try:
        request=json.loads(sys.stdin.readline())
        result=splice(request['original'],request['replacement'],request['output'],request['start_frame'],request['end_frame'],request['total_frames'])
        emit('result',result=result)
    except Exception as error:emit('error',message=str(error))
