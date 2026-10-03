"""Collect figures only from chat documents and retrieved project sources."""
from pathlib import Path
from .downloads import safe_join, Cancelled
from .store import uid


def extract_assets(app, job, documents, rag_sources, project_id, cancel, stage, log_path):
    entries={str(safe_join(app.data,d['path'])): {'name':d['name'],'pages':[]} for d in documents}
    for ref in rag_sources:
        source=app.store.one('SELECT path,name FROM project_sources WHERE id=? AND project_id=?',(ref['source_id'],project_id))
        if source and Path(source['path']).suffix.lower() in ('.pdf','.docx'):
            entry=entries.setdefault(source['path'],{'name':source['name'],'pages':[]})
            if ref.get('page'):entry['pages'].append(ref['page'])
    assets=[]
    for path,entry in list(entries.items())[:8]:
        if cancel.is_set():raise Cancelled()
        stage('Slide · figure da '+entry['name'])
        folder=app.data/'outputs'/job['id']/'slide-assets'/uid()
        result=app.engine.tool_call('document-worker.py',{'op':'assets','path':path,'pages':entry['pages'],
            'output':str(folder),'limit':min(16,32-len(assets))},cancel,stage,log_path)
        for image in result:
            assets.append({'id':uid(),'name':entry['name']+' · '+image['location'],
                'path':Path(image['path']).relative_to(app.data).as_posix(),'mime':'image/png'})
        if len(assets)>=32:break
    return assets
