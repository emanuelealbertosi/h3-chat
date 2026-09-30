"""Document, speech and web context for the existing chat LLM."""
import hashlib
import json
import re
import secrets
from pathlib import Path
from .context_tools import budget,excerpts
from .downloads import Cancelled,safe_join
from .residency import Session
from .tools_runtime import model_path,status,pure_transcription
from .web_search import requested,search

class ToolsEngine:
    def tool_call(self,worker,request,cancel,stage,log_path,timeout=90):
        if cancel.is_set():raise Cancelled()
        session=Session(('tool',(),()),'tool',{'id':worker,'name':worker},{},{},log_path)
        with self.process_lock:self.tool_session=session
        try:
            session.start([self.root/'runtime/python/python.exe','-X','utf8',self.root/'native'/worker],ipc=True,cwd=self.root)
            session.wait('hello',cancel,30,stage);session.send(request)
            return session.wait('result',cancel,timeout,stage)['result']
        finally:
            session.stop()
            with self.process_lock:
                if self.tool_session is session:self.tool_session=None

    def read_document(self,item,cancel,stage,log_path):
        if not status(self.root)['documents']['ready']:raise ValueError('Installa i componenti documenti eseguendo install.bat oppure dal Setup → Strumenti.')
        target=safe_join(self.data,'document-cache/'+item['id']+'.json')
        if not target.exists():
            stage('Lettura documento · '+item['name'])
            self.tool_call('document-worker.py',{'op':'read','path':str(safe_join(self.data,item['path'])),'output':str(target)},cancel,stage,log_path)
        return json.loads(target.read_text(encoding='utf-8'))

    def transcribe(self,item,settings,cancel,stage,log_path):
        if not status(self.root)['asr']['ready']:raise ValueError('Installa il motore trascrizione dal Setup → Strumenti.')
        folder=model_path(self.root,settings['asr_model']);weight=folder/'model.bin';st=weight.stat()
        key=hashlib.sha256(json.dumps([item['id'],str(folder),st.st_size,st.st_mtime_ns,settings['asr_language'],settings['asr_beam']]).encode()).hexdigest()
        target=safe_join(self.data,'transcriptions/'+key+'.json')
        if not target.exists():
            if settings.get('memory_policy')!='resident':
                stage('Rilascio modelli · trascrizione sulla CPU');self.stop()
            self.tool_call('transcription-worker.py',{'model':str(folder),'path':str(safe_join(self.data,item['path'])),'settings':settings,'output':str(target)},cancel,stage,log_path,timeout=3600)
        result=json.loads(target.read_text(encoding='utf-8'))
        if not result['text'].strip():result['warning']='Nessun parlato riconosciuto; non è un’analisi di musica o rumori.'
        return result

    def transcript_files(self,results,job_id):
        media=[]
        def stamp(value):
            milliseconds=round(value*1000);seconds,milliseconds=divmod(milliseconds,1000);minutes,seconds=divmod(seconds,60);hours,minutes=divmod(minutes,60)
            return f'{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}'
        for i,(item,result) in enumerate(results,1):
            srt='\n\n'.join(f"{n}\n{stamp(s['start'])} --> {stamp(s['end'])}\n{s['text']}" for n,s in enumerate(result['segments'],1))+'\n'
            for ext,text,mime in (('txt',result['text'],'text/plain'),('srt',srt,'application/x-subrip')):
                relative=f'outputs/{job_id}/transcript-{i}.{ext}';target=safe_join(self.data,relative);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text,encoding='utf-8')
                media.append({'id':secrets.token_hex(16),'name':Path(item['name']).stem+'.'+ext,'path':relative,'mime':mime})
        return media

    def prepare_tools(self,history,payload,settings,cancel,stage,log_path,*,use_audio=True):
        documents=[x for x in payload['media'] if x['mime'] in ('application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document')]
        audios=[x for x in payload['media'] if x['mime'].startswith('audio/')] if use_audio else []
        # Retain document access for later questions, without resending entire files.
        if not documents:
            documents=next(([x for x in m['media'] if x['mime'] in ('application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document')] for m in reversed(history) if any(x['mime'] in ('application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document') for x in m['media'])),[])
        history=[m|{'media':[x for x in m['media'] if x['mime'].startswith('image/')]} for m in history]
        context=[];meta={};transcripts=[];remaining=budget(settings,history)
        sources=[]
        if requested(payload['prompt'],settings):
            sources=search(payload['prompt'],settings,cancel,stage);meta['web_sources']=[{k:s[k] for k in ('title','url','read','snippet')} for s in sources]
            for i,s in enumerate(sources,1):
                allocation=max(150,min(remaining//max(1,len(sources)-i+1+len(documents)+len(audios)),3500));selected,_=excerpts([{'location':'web','text':s['text'][j:j+1200]} for j in range(0,len(s['text']),1200)],payload['prompt'],allocation)
                text='\n'.join(x['text'] for x in selected);context.append(f"Fonte web [{i}] {s['title']}\nURL: {s['url']}\n{'Testo pagina' if s['read'] else 'Solo estratto ricerca'}:\n{text}");remaining-=len(text)+180
        meta['documents']=[]
        for index,item in enumerate(documents):
            doc=self.read_document(item,cancel,stage,log_path);allocation=max(150,remaining//max(1,len(documents)-index+len(audios)))
            selected,partial=excerpts(doc['blocks'],payload['prompt'],allocation)
            text='\n\n'.join(f"[{b['location']}]\n{b['text']}" for b in selected);remaining-=len(text)+180
            note='Sono estratti selezionati, non tutto il documento.' if partial else 'Testo estraibile completo.'
            meta['documents'].append({'name':item['name'],'pages':doc['pages'],'partial':partial,'locations':list(dict.fromkeys(b['location'] for b in selected)),'warnings':doc['warnings']})
            context.append(f"Documento {item['name']}\n{note}\n{text}\n"+'\n'.join(doc['warnings']))
            if item['mime']=='application/pdf':
                explicit={int(x) for x in re.findall(r'\b(?:pagina|page)\s+(\d+)\b',payload['prompt'],re.I)}
                pages=sorted(explicit) if explicit and re.search(r'grafico|diagramma|immagin|figura|leggi|analizz|descrivi',payload['prompt'],re.I) else doc['blank_pages']
                llm=self.catalog.get(settings['chat_model'],{});available=max(0,llm.get('max_refs',4)-len(history[-1]['media']))
                if pages and settings.get('vision_enabled',True) and llm.get('vision',{}).get('enabled') and available:
                    picked=pages[:min(4,available)]
                    output=safe_join(self.data,'document-cache/'+item['id'])
                    rendered=self.tool_call('document-worker.py',{'op':'render','path':str(safe_join(self.data,item['path'])),'pages':picked,'output':str(output)},cancel,stage,log_path)
                    first=len(history[-1]['media'])+1
                    history[-1]['media'] += [{'id':item['id'],'name':item['name']+f" · pagina {x['page']}",'path':Path(x['path']).relative_to(self.data).as_posix(),'mime':'image/png'} for x in rendered]
                    context.append('Pagine PDF fornite a Vision: '+', '.join(f"Immagine {first+i} = {item['name']} pagina {x['page']}" for i,x in enumerate(rendered))+'. Altre pagine senza testo non sono state lette.')
                    meta['documents'][-1]['visual_pages']=picked
                elif pages:
                    context.append('Pagine senza testo/figure non analizzate: abilita Vision con un modello compatibile. Non inventarne il contenuto.')
        for index,item in enumerate(audios):
            if not settings['transcribe_auto'] and not settings.get('_transcribe') and not pure_transcription(payload['prompt'],audios):raise ValueError('La trascrizione automatica audio è disattivata nelle preferenze. Usa Trascrivi per richiederla esplicitamente.')
            result=self.transcribe(item,settings,cancel,stage,log_path);transcripts.append((item,result))
            blocks=[{'location':f"{s['start']:.1f}–{s['end']:.1f} s",'text':s['text']} for s in result['segments']]
            selected,partial=excerpts(blocks,payload['prompt'],max(150,remaining//max(1,len(audios)-index)));text='\n'.join(f"[{b['location']}] {b['text']}" for b in selected);remaining-=len(text)+180
            context.append(f"Trascrizione automatica di {item['name']} · lingua {result['language']}\nPuò contenere errori; non è analisi di musica, rumori o identità del parlante.\n"+('Estratti selezionati; trascrizione completa nel TXT/SRT.\n' if partial else '')+text+result.get('warning',''))
        if transcripts:meta['transcriptions']=[{'name':item['name'],**{k:r[k] for k in ('duration','language','device','compute_type')},'warning':r.get('warning','')} for item,r in transcripts]
        if context:
            history[-1]['content'] += '\n\n<contenuti_allegati_e_web>\n'+'\n\n'.join(context)+'\n</contenuti_allegati_e_web>'
        return history,meta,transcripts,sources
