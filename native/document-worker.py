"""Read documents in an isolated, time-limited process. Never execute macros."""
import json
import os
import re
from pathlib import Path
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/tools/documents'
sys.path.insert(0,str(RUNTIME))
dll=os.add_dll_directory(str(RUNTIME)) if os.name=='nt' and RUNTIME.is_dir() else None
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**kw):wire.write(json.dumps({'event':event,**kw},ensure_ascii=False)+'\n');wire.flush()

def chunks(text):
    current=''
    for word in re.findall(r'\S+\s*',text):
        if current and len(current)+len(word)>1800:yield current;current=''
        current+=word
    if current:yield current

def read(path):
    path=Path(path);blocks=[];blank=[];warnings=[]
    if path.suffix.lower()=='.pdf':
        from pypdf import PdfReader
        doc=PdfReader(path)
        if doc.is_encrypted:raise ValueError('Il PDF è protetto: allega una copia senza password.')
        total=len(doc.pages)
        if total>300:raise ValueError('PDF: massimo 300 pagine. Dividi il documento prima di allegarlo.')
        count=0
        for i,page in enumerate(doc.pages):
            emit('stage',message=f'Lettura PDF · pagina {i+1}/{total}')
            # Bound decompressed streams before invoking text extraction.
            contents=page.get_contents()
            if contents and len(contents.get_data())>16*1024**2:raise ValueError('Una pagina PDF è troppo complessa: esportala con una risoluzione inferiore.')
            text=page.extract_text() or ''
            count+=len(text)
            if count>2000000:raise ValueError('Documento troppo lungo: massimo due milioni di caratteri estratti.')
            if not text.strip():blank.append(i+1)
            for chunk in chunks(text):blocks.append({'location':f'pagina {i+1}','page':i+1,'text':chunk})
        if blank:warnings.append(f'{len(blank)} pagine senza testo estraibile: possono richiedere Vision.')
    else:
        validate_docx(path)
        from docx import Document
        from docx.table import Table
        doc=Document(path);total=0;count=0
        for i,item in enumerate(doc.iter_inner_content(),1):
            text='\n'.join(' | '.join(c.text for c in row.cells) for row in item.rows) if isinstance(item,Table) else item.text
            count+=len(text)
            if count>2000000:raise ValueError('Documento Word troppo lungo.')
            for chunk in chunks(text):blocks.append({'location':f'blocco {i}','page':None,'text':chunk})
        warnings.append('Word: testo e tabelle estratti; immagini, intestazioni e layout non vengono analizzati.')
    return {'blocks':blocks,'pages':total,'blank_pages':blank,'warnings':warnings}

def validate_docx(path):
    with zipfile.ZipFile(path) as z:
        items=z.infolist();names={x.filename for x in items}
        if not {'[Content_Types].xml','word/document.xml'}<=names:raise ValueError('Il file non è un documento Word .docx.')
        if len(items)>10000 or sum(x.file_size for x in items)>100*1024**2:raise ValueError('Documento Word decompresso troppo grande.')
        if any(x.flag_bits&1 or (x.file_size>1024*1024 and x.file_size/max(1,x.compress_size)>200) for x in items):raise ValueError('Archivio Word compresso o cifrato non consentito.')
        if any('vbaproject' in x.lower() for x in names):raise ValueError('Usa un .docx senza macro.')

def render(path,pages,output):
    import pypdfium2 as pdfium
    doc=pdfium.PdfDocument(path);result=[]
    try:
        for number in pages[:4]:
            if not 1<=number<=len(doc):raise ValueError('Pagina PDF inesistente.')
            page=doc[number-1]
            try:
                w,h=page.get_size();scale=min(1.7,1600/max(w,h));bitmap=page.render(scale=scale)
                try:
                    target=Path(output)/f'page-{number}.png';target.parent.mkdir(parents=True,exist_ok=True);bitmap.to_pil().save(target);result.append({'page':number,'path':str(target)})
                finally:bitmap.close()
            finally:page.close()
    finally:doc.close()
    return result

emit('hello',engine='documents')
for line in sys.stdin:
    try:
        request=json.loads(line)
        result=read(request['path']) if request['op']=='read' else render(request['path'],request['pages'],request['output'])
        if request['op']=='read':
            target=Path(request['output']);target.parent.mkdir(parents=True,exist_ok=True);part=target.with_suffix('.writing');part.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');part.replace(target);result={'path':str(target)}
        emit('result',result=result)
    except Exception as e:emit('error',message=str(e))
