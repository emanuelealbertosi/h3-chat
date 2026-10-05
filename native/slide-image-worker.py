"""Bounded raster decoding in a disposable process, using bundled document tools."""
import base64,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];TOOLS=ROOT/'runtime/tools/documents'
sys.path.insert(0,str(TOOLS))
handle=os.add_dll_directory(str(TOOLS)) if os.name=='nt' else None
from PIL import Image,ImageOps
Image.MAX_IMAGE_PIXELS=20_000_000
request=json.loads(sys.stdin.read())
with Image.open(request['path']) as image:
    if image.width*image.height>20_000_000:raise ValueError('Immagine troppo grande: massimo 20 megapixel.')
    image=ImageOps.exif_transpose(image)
    image.thumbnail((240,160) if request['thumbnail'] else (4096,4096))
    image.convert('RGB').save(request['output'],'JPEG',quality=75 if request['thumbnail'] else 92)
print(json.dumps({'ok':True}))
