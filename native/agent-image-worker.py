"""CPU-only bounded Vision thumbnail; never changes or registers the source."""
import base64
import io
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime/tools/documents')]
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**kw):wire.write(json.dumps({'event':event,**kw})+'\n');wire.flush()

def preview(request):
    from PIL import Image,ImageOps
    from h3chat.downloads import safe_join
    if not request['source'].startswith(('uploads/','outputs/')):raise ValueError('Immagine non autorizzata.')
    path=safe_join(Path(request['data']).resolve(),request['source'])
    if path.stat().st_size>32*1024**2:raise ValueError('Immagine troppo grande per la lettura Agent (massimo 32 MiB).')
    with Image.open(path) as opened:
        if opened.width*opened.height>64000000:raise ValueError('Immagine troppo grande per la lettura Agent (massimo 64 MP).')
        image=ImageOps.exif_transpose(opened).convert('RGBA');image.thumbnail((768,768))
        white=Image.new('RGB',image.size,'white');white.paste(image,mask=image.getchannel('A'))
    for quality in (80,60,40):
        output=io.BytesIO();white.save(output,format='JPEG',quality=quality)
        if output.tell()<=128*1024:break
    if output.tell()>128*1024:raise ValueError('Anteprima Vision troppo grande.')
    return {'image_url':'data:image/jpeg;base64,'+base64.b64encode(output.getvalue()).decode(),'size':list(white.size)}

if __name__=='__main__':
    emit('hello',engine='agent-image-cpu')
    try:emit('result',result=preview(json.loads(sys.stdin.readline())))
    except Exception as error:emit('error',message=str(error))
