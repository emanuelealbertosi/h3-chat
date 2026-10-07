"""Local visual-document extraction, indexing metadata and LLM image handoff."""
import hashlib,json,shutil
from pathlib import Path
from .downloads import safe_join,Cancelled
from .residency import Session
from .store import uid
from .vision_options import reference_limit

def extract(knowledge,source,blocks,cancel,stage):
    path=Path(source['path']);st=path.stat()
    digest=hashlib.sha256(f'{st.st_mtime_ns}:{st.st_size}:visual-v2'.encode()).hexdigest()[:24]
    folder=safe_join(knowledge.data,f'project-cache/visual/{source["id"]}/{digest}')
    manifest=folder/'visuals.json'
    if manifest.exists():
        value=json.loads(manifest.read_text(encoding='utf-8'))
        if any(not (folder/x['path']).is_file() for x in value['visuals']):manifest.unlink()
    if not manifest.exists():
        session=Session(('rag-visual',source['id']),'documents',{}, {},{},knowledge.data/'logs'/('project-'+source['id']+'-visual.log'))
        with knowledge.lock:knowledge.readers.add(session)
        try:
            session.start([knowledge.root/'runtime/python/python.exe','-X','utf8',knowledge.root/'native/document-worker.py'],ipc=True,cwd=knowledge.root)
            session.wait('hello',cancel,30,stage);session.send({'op':'visuals','path':str(path),'folder':str(folder),'output':str(manifest)})
            session.wait('result',cancel,1800,stage)
        finally:
            session.stop()
            with knowledge.lock:knowledge.readers.discard(session)
    value=json.loads(manifest.read_text(encoding='utf-8'));rows=[]
    by_page={}
    for b in blocks:
        key=b.get('page') or b['location'];by_page[key]=(by_page.get(key,'')+' '+b['text'])[:1400]
    for image in value['visuals']:
        target=(folder/image['path']).resolve()
        if not target.is_relative_to(folder.resolve()) or not target.is_file():raise ValueError('Figura RAG non disponibile; aggiorna l’indice.')
        text=by_page.get(image.get('page') or image['location'].split(' · ')[0],'').strip()
        rows.append({'location':image['location'],'page':image.get('page'),'text':'Contenuto visivo del documento. '+text,
                     'modality':'image','image_path':target.relative_to(knowledge.data).as_posix()})
    return rows,value.get('warnings',[])

def attach(app,job,history,sources,settings):
    """Copy retrieved visuals into durable chat media; respect Vision and refs."""
    selected=[s for s in sources if s.get('image_path')]
    if not selected:return {}
    model=app.catalog.get(settings['chat_model'],{})
    image_count=sum(m.get('mime','').startswith('image/') for m in history[-1]['media'])
    available=max(0,reference_limit(model,settings)-image_count)
    usable=settings.get('vision_enabled',True) and model.get('vision',{}).get('enabled') and available
    added=[]
    for source in selected:
        original=safe_join(app.data,source['image_path'])
        if not original.is_file():raise ValueError('Immagine RAG non disponibile: aggiorna l’indice.')
        ident=uid();relative=f'outputs/{job["id"]}/rag-visual/{ident}.png';target=safe_join(app.data,relative)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
        media={'id':ident,'name':source['name']+' · '+source['location'],'path':relative,'mime':'image/png'}
        source['image']=media
        if usable and len(added)<available:
            history[-1]['media'].append(media);added.append((source['citation'],image_count+len(added)+1))
    if added:history[-1]['content']+='\nImmagini delle fonti RAG fornite a Vision: '+', '.join(f'Immagine {number} = [{citation}]' for citation,number in added)+'. Usa le immagini insieme ai riferimenti di pagina.'
    missing=len(selected)-len(added)
    result={'rag_visual_count':len(added)}
    if missing:
        result['rag_visual_warning']=f'{missing} '+('immagine RAG recuperata e consultabile nelle fonti, ma non inviata' if missing==1 else 'immagini RAG recuperate e consultabili nelle fonti, ma non inviate')+' al modello. Abilita Vision con un modello compatibile e verifica il limite di riferimenti.'
        history[-1]['content']+='\n'+result['rag_visual_warning']+' Non inventare il contenuto delle immagini non ricevute.'
    return result
