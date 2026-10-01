"""MiniMax H3 uses the private inference runtime and the shared process pool."""
import json
from .downloads import Cancelled, safe_join
from .video_options import options, validate_plan
from .video_routing import BRIEF, PLAN_SCHEMA, direct_plan
from .vision_runtime import status

class VideoEngine:
    def start_video(self,model,settings,log_path,cancel,stage=None):
        if not status(self.root)['ready']:raise ValueError('Installa il motore Video / Ming / Qwen dal Setup.')
        session=self._activate('video',model,settings,log_path,cancel,stage=stage)
        if session.ready and session.alive():return session
        with self.process_lock:
            if cancel.is_set():raise Cancelled()
            session.start([self.root/'runtime/python/python.exe','-I','-X','utf8',self.root/'native/video-worker.py'],ipc=True,cwd=self.root)
        session.wait('hello',cancel,60)
        session.send({'op':'load','files':session.files,'offload':options(model,settings,False)['offload'],'threads':settings['threads']})
        session.wait('ready',cancel,1800,stage)
        session.ready=True
        return session

    def refine_video(self,history,prompt,refs,model,settings,cancel,log_path,stage):
        opts=options(model,settings,False)
        if not settings.get('_assistant',True):return direct_plan(prompt,refs,opts['duration']),None
        llm=self.require_model(settings['chat_model'],'chat')
        stage('Assistant · istruzioni, fotogrammi e audio del video')
        self.start_llama(llm,settings,log_path,cancel,stage=stage)
        assets={kind:[{'index':i,'name':x['name']} for i,x in enumerate([r for r in refs if r['mime'].startswith(mime)],1)] for kind,mime in (('images','image/'),('audios','audio/'))}
        content=json.dumps({'request':prompt,'duration':opts['duration'],'attachments':assets,
             'conversation':[{'role':m['role'],'text':m['content'][-2000:]} for m in history[-4:] if m.get('status')=='done']},ensure_ascii=False)
        # Reuse the chat model and its CPU mmproj when enabled. Audio is not sent
        # to a text/vision LLM and must never be presented as a transcription.
        visual=[x for x in refs if x['mime'].startswith('image/')]
        if not settings.get('vision_enabled',True) or not llm.get('vision',{}).get('enabled') or len(visual)>llm.get('max_refs',4):visual=[]
        content+='\nVisible images supplied to Assistant: '+str(bool(visual))+'. Do not invent unseen visual details.'
        messages=self.chat_messages([{'role':'user','content':content,'media':visual,'status':'done','seq':1}],llm,settings)
        messages[0]={'role':'system','content':BRIEF}
        tuning=settings|{'think_level':'off','max_tokens':min(settings['video_prompt_max_tokens'],settings['context']//2)}
        raw,finish=self.completion(messages,tuning,cancel,on_text=lambda _:None,schema=PLAN_SCHEMA)
        if finish=='length':raise ValueError('Assistant video ha esaurito i token. Aumenta contesto/token o semplifica la richiesta.')
        try:plan=validate_plan(json.loads(raw),refs,opts['duration'])
        except (ValueError,TypeError) as exc:raise ValueError('Assistant: piano video non valido. '+str(exc)) from exc
        return plan,{'model':llm['name'],'max_tokens':tuning['max_tokens']}

    def generate_video(self,model,settings,plan,refs,job_id,cancel,stage):
        if model.get('remote_media'):return self.remote_generate(model,settings,'',refs,job_id,cancel,stage,plan=plan)
        opts=options(model,settings)
        plan=validate_plan(plan,refs,opts['duration'])
        if any(a['role']=='lipsync' for a in plan['audios']) and opts['steps']<8:
            opts['steps']=8;stage('Lip-sync · uso almeno 8 passi standard')
        folder=self.data/'outputs'/job_id;folder.mkdir(parents=True,exist_ok=True)
        output=folder/'video.mp4'
        request={'op':'generate','output':str(output),'plan':plan,'options':opts,
                 'images':[str(safe_join(self.data,x['path'])) for x in refs if x['mime'].startswith('image/')],
                 'audios':[str(safe_join(self.data,x['path'])) for x in refs if x['mime'].startswith('audio/')]}
        (folder/'video-plan.json').write_text(json.dumps({'plan':plan,'parameters':opts},ensure_ascii=False,indent=2),encoding='utf-8')
        session=self.start_video(model,settings,folder/'engine.log',cancel,stage)
        stage('Generazione video · '+model['name']);session.send(request)
        try:done=session.wait('done',cancel,14400,stage)
        except RuntimeError as exc:raise RuntimeError(self.failure(session.log_path,str(exc))) from exc
        if cancel.is_set():raise Cancelled()
        with output.open('rb') as stream:
            if stream.read(12)[4:8]!=b'ftyp':raise RuntimeError('Il motore non ha prodotto un MP4 valido.')
        session.uses+=1
        return {'id':job_id,'name':'Video MiniMax H3.mp4','mime':'video/mp4','path':output.relative_to(self.data).as_posix(),'generation':opts|done.get('parameters',{})}
