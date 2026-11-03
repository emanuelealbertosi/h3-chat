"""CPU-only reference page and crop extraction; original files remain untouched."""
import json,sys,math,os,subprocess
from contextlib import closing
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'runtime/tools/documents')]
dll=os.add_dll_directory(str(ROOT/'runtime/tools/documents')) if os.name=='nt' and (ROOT/'runtime/tools/documents').is_dir() else None

def run(request):
    from PIL import Image,ImageOps,ImageDraw,ImageFont
    from h3chat.downloads import safe_join
    data=Path(request['data']).resolve();source=request['source']
    if not source.startswith(('uploads/','outputs/')):raise ValueError('Riferimento non autorizzato.')
    path=safe_join(data,source);out=Path(request['output']).resolve()
    if not out.is_relative_to(data/'outputs'):raise ValueError('Destinazione del riferimento non valida.')
    out.mkdir(parents=True,exist_ok=True)
    if request.get('mode')=='crop':
        regions=request['regions']
        if not isinstance(regions,list) or len(regions)>24:raise ValueError('Troppe regioni immagine.')
        scale=request.get('detail_scale',1)
        if type(scale) is not int or not 1<=scale<=4:raise ValueError('Ingrandimento dettaglio non valido.')
        files=[]
        with Image.open(path) as im:
            if im.width*im.height>64000000:raise ValueError('Riferimento oltre 64 MP.')
            im=ImageOps.exif_transpose(im).convert('RGB');w,h=im.size
            for i,box in enumerate(regions):
                if not isinstance(box,list) or len(box)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in box):raise ValueError('Regione non valida.')
                x,y,bw,bh=box
                if min(x,y)<0 or min(bw,bh)<=0 or x+bw>1.000001 or y+bh>1.000001:raise ValueError('Regione fuori pagina.')
                rect=(round(x*w),round(y*h),min(w,round((x+bw)*w)),min(h,round((y+bh)*h)))
                if rect[2]-rect[0]<8 or rect[3]-rect[1]<8:continue
                target=out/f'photo-{i+1}.png';crop=im.crop(rect)
                if scale>1:
                    crop=crop.resize((crop.width*scale,crop.height*scale),Image.Resampling.LANCZOS);crop.thumbnail((2400,2400))
                crop.save(target)
                files.append({'region_index':i,'path':target.relative_to(data).as_posix(),'width':rect[2]-rect[0],'height':rect[3]-rect[1]})
        return {'files':files}
    text=[];pages=1;page=request.get('page',1)
    if type(page) is not int or not 1<=page<=1000:raise ValueError('Pagina riferimento non valida.')
    if path.stat().st_size>128*1024**2:raise ValueError('Riferimento oltre 128 MB.')
    if path.suffix.lower()=='.pdf':
        import pypdfium2 as pdfium
        with closing(pdfium.PdfDocument(path)) as doc:
            pages=len(doc)
            if page>pages:raise ValueError('Pagina PDF non disponibile.')
            with closing(doc[page-1]) as sheet:
                w,h=sheet.get_size()
                with closing(sheet.get_textpage()) as tp:
                    for i in range(min(tp.count_rects(),400)):
                        l,b,r,t=tp.get_rect(i);s=tp.get_text_bounded(l,b,r,t).strip()
                        if s:text.append({'text':s[:2000],'box':[max(0,l/w),max(0,1-t/h),max(0,(r-l)/w),max(0,(t-b)/h)]})
                scale=min(3,2200/max(w,h))
                with closing(sheet.render(scale=scale)) as bitmap:image=bitmap.to_pil().convert('RGB').copy()
    else:
        if page!=1:raise ValueError('Un’immagine contiene una sola pagina.')
        with Image.open(path) as im:
            if im.width*im.height>64000000:raise ValueError('Riferimento oltre 64 MP.')
            image=ImageOps.exif_transpose(im).convert('RGB');w,h=image.size;image.thumbnail((2400,2400))
    target=out/'reference.png';image.save(target)
    # A labelled coordinate sheet prevents VLMs from estimating a portrait as
    # if it were square. Its border never enters the reusable source crops.
    scale=min(4,1800/max(image.size));large=image.resize((round(image.width*scale),round(image.height*scale)),Image.Resampling.LANCZOS)
    ocr=[];ocr_status='not_available'
    if os.name=='nt' and (ROOT/'native/poster-ocr.ps1').is_file():
        ocr_input=out/'ocr-input.png';large.save(ocr_input)
        powershell=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
        try:
            result=subprocess.run([str(powershell),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(ROOT/'native/poster-ocr.ps1'),'-ImagePath',str(ocr_input)],capture_output=True,timeout=30,creationflags=0x08000000)
            if result.returncode==0:
                reading=json.loads(result.stdout.decode('utf-8-sig'));ocr=reading.get('lines',[])[:200];ocr_status='windows_'+reading.get('language','')
                (out/'ocr.json').write_text(json.dumps(reading,ensure_ascii=False,indent=2),encoding='utf8')
        except (OSError,ValueError,subprocess.TimeoutExpired):pass
    border=64;sheet=Image.new('RGB',(large.width+border*2,large.height+border*2),'white');sheet.paste(large,(border,border))
    draw=ImageDraw.Draw(sheet);font=ImageFont.load_default(size=22)
    for i in range(11):
        x=border+round(large.width*i/10);y=border+round(large.height*i/10)
        draw.line((x,border,x,border+large.height),fill='#a0b5c8',width=1)
        draw.line((border,y,border+large.width,y),fill='#a0b5c8',width=1)
        draw.text((x-16,20),f'{i/10:.1f}',font=font,fill='#113f70')
        draw.text((10,y-12),f'{i/10:.1f}',font=font,fill='#113f70')
    grid=out/'coordinates.png';sheet.save(grid)
    return {'path':target.relative_to(data).as_posix(),'analysis_path':grid.relative_to(data).as_posix(),'width':w,'height':h,'page':page,'pages':pages,'text_regions':text,'ocr_regions':ocr,'ocr_status':ocr_status}

if __name__=='__main__':
    wire=sys.stdout;sys.stdout=sys.stderr
    def emit(event,**kw):wire.write(json.dumps({'event':event,**kw},ensure_ascii=False)+'\n');wire.flush()
    emit('hello')
    try:emit('result',result=run(json.loads(sys.stdin.readline())))
    except Exception as error:emit('error',message=str(error))
