import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime/tools/documents')]
handle=os.add_dll_directory(str(ROOT/'runtime/tools/documents')) if os.name=='nt' else None
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**kw):wire.write(json.dumps({'event':event,**kw})+'\n');wire.flush()
if __name__=='__main__':
    emit('hello')
    try:
        from h3chat.infographic_video import probe,asset
        from h3chat.downloads import safe_join
        request=json.loads(sys.stdin.readline());poster=safe_join(request['data'],request['poster']);poster.parent.mkdir(parents=True,exist_ok=True)
        emit('result',result=probe(asset(request['data'],request['media'],request['id'],'video/mp4'),poster))
    except Exception as exc:emit('error',message=str(exc))
