"""MiniMax H3 uses the private inference runtime and the shared process pool."""
import json
import time
from .downloads import Cancelled, safe_join
from .video_options import options, validate_plan
from .video_routing import BRIEF, PLAN_SCHEMA, direct_plan
from .vision_runtime import status
from .remote_llm import EmptyCompletion, StructuredCompletionError

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
        opts['duration']=settings.get('_video_duration',opts['duration'])
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

    def generate_video(self,model,settings,plan,refs,job_id,cancel,stage,*,prompt=None,scene=None):
        if model.get('remote_media'):return self.remote_generate(model,settings,prompt if prompt is not None else plan['prompt'],refs,job_id,cancel,stage,plan=plan)
        opts=options(model,settings)
        if scene:opts.update(duration=scene['duration'],frames=scene['frames'])
        plan=validate_plan(plan,refs,opts['duration'])
        if any(a['role']=='lipsync' for a in plan['audios']) and opts['steps']<8:
            opts['steps']=8;stage('Lip-sync · uso almeno 8 passi standard')
        folder=self.data/'outputs'/job_id;folder.mkdir(parents=True,exist_ok=True)
        output=folder/'video.mp4'
        request={'op':'generate','output':str(output),'plan':plan,'options':opts,'format_prompt':prompt if prompt is not None else plan['prompt'],
                 'images':[str(safe_join(self.data,x['path'])) for x in refs if x['mime'].startswith('image/')],
                 'audios':[str(safe_join(self.data,x['path'])) for x in refs if x['mime'].startswith('audio/')]}
        if scene:request.update(sequence=scene['sequence'],scene_index=scene['index'],canvas=scene.get('canvas'))
        (folder/'video-plan.json').write_text(json.dumps({'plan':plan,'parameters':opts},ensure_ascii=False,indent=2),encoding='utf-8')
        startup_started=time.monotonic()
        session=self.start_video(model,settings,folder/'engine.log',cancel,stage)
        startup_seconds=time.monotonic()-startup_started
        stage('Generazione video · '+model['name']);session.send(request)
        try:done=session.wait('done',cancel,14400,stage)
        except RuntimeError as exc:raise RuntimeError(self.failure(session.log_path,str(exc))) from exc
        if cancel.is_set():raise Cancelled()
        with output.open('rb') as stream:
            if stream.read(12)[4:8]!=b'ftyp':raise RuntimeError('Il motore non ha prodotto un MP4 valido.')
        session.uses+=1
        actual=opts|done.get('parameters',{})|{'startup_seconds':startup_seconds}
        (folder/'video-plan.json').write_text(json.dumps({'plan':plan,'parameters':actual},ensure_ascii=False,indent=2),encoding='utf-8')
        return {'id':job_id,'name':'Video MiniMax H3.mp4','mime':'video/mp4','path':output.relative_to(self.data).as_posix(),'generation':actual}

    def scene_scripts(self,plan,scenes,settings,cancel,stage,*,prompt):
        """Bound each structured call; retain continuity across prompt batches."""
        budget=min(settings['context']//2,settings['video_prompt_max_tokens'])
        tuning=settings|{'max_tokens':budget,'think_level':'off'}
        size=max(1,min(3,budget//768));scripts=[]
        brief=BRIEF.replace('Return JSON prompt, images, audios.','Return only JSON {"scenes":[English prompt per requested clip]}.')+'\nDescribe one continuous film, preserving Picture/Audio labels, identities, style and the language of any supplied dialogue. Do not invent unheard lyrics. Return only the requested clips, in order. Use supplied previous prompts and opening as visual continuity, not as repeated action. No opening restart or finale before the last clip. Translate global keyframe times into LOCAL clip times. Each prompt must be concise while retaining the required MiniMax section labels; never return images/audios arrays.'
        def produce(group):
            schema={'type':'object','properties':{'scenes':{'type':'array','minItems':len(group),'maxItems':len(group),'items':{'type':'string'}}},'required':['scenes'],'additionalProperties':False}
            for attempt in range(2 if len(group)==1 else 1):
                if cancel.is_set():raise Cancelled()
                first,last=group[0]['index']+1,group[-1]['index']+1
                stage(f'Assistant · sceneggiatura · scene {first}–{last}/{len(scenes)}'+(' · nuovo tentativo conciso' if attempt else ''))
                context={'request':prompt,'plan':plan,'total_scenes':len(scenes),'film_duration':scenes[-1]['start']+scenes[-1]['duration'],'clips':group,'opening':scripts[0] if scripts else None,'previous':scripts[-2:]}
                instructions=brief+f'\nOutput budget: {budget} tokens for {len(group)} clip(s). Aim for at most {max(40,min(220,budget//(3*len(group))))} words per clip.'
                if attempt:instructions+=' Previous output was empty or incomplete. Return short, complete JSON immediately.'
                try:
                    raw,finish=self.completion([{'role':'system','content':instructions},{'role':'user','content':json.dumps(context,ensure_ascii=False)}],tuning,cancel,on_text=lambda _:None,schema=schema)
                    if finish=='length':raise StructuredCompletionError('Output limit reached')
                    try:value=json.loads(raw)
                    except (ValueError,TypeError) as exc:raise StructuredCompletionError('Incomplete scene JSON') from exc
                    value=value.get('scenes') if isinstance(value,dict) and set(value)=={'scenes'} else None
                    if not isinstance(value,list) or len(value)!=len(group) or any(not isinstance(s,str) or not s.strip() for s in value):raise StructuredCompletionError('Incomplete scene list')
                    scripts.extend(value);return
                except (EmptyCompletion,StructuredCompletionError) as exc:
                    if len(group)>1:
                        stage('Assistant · piano incompleto · divido il gruppo di scene')
                        middle=len(group)//2;produce(group[:middle]);produce(group[middle:]);return
                    if attempt:raise ValueError(f'Assistant video non ha completato la scena {first} dopo due tentativi. Aumenta i token Assistant video o scegli un altro LLM; puoi usare Assistant Off. Nessun video è stato avviato.') from exc
        for start in range(0,len(scenes),size):produce(scenes[start:start+size])
        return scripts

    def generate_long_video(self,model,settings,plan,refs,job_id,cancel,stage,*,prompt):
        from .video_timeline import timeline,scene_plan
        from .soundtrack import compose
        scenes=timeline(settings['_video_duration']);soundtrack=settings['_video_soundtrack']
        if model.get('remote_media') and len(scenes)>1:raise ValueError('Video a più scene con memoria: seleziona il motore MiniMax H3 standalone. Il server esterno deve supportare esplicitamente questa funzione.')
        index=next(i for i,m in enumerate([r for r in refs if r['mime'].startswith('audio/')],1) if m['id']==soundtrack['id'])
        scripts=[plan['prompt']]*len(scenes)
        folder=self.data/'outputs'/job_id;folder.mkdir(parents=True,exist_ok=True)
        if len(scenes)>1 and settings.get('_assistant',True):
            stage(f'Assistant · sceneggiatura continua in {len(scenes)} scene')
            llm=self.require_model(settings['chat_model'],'chat');self.start_llama(llm,settings,folder/'engine.log',cancel,stage=stage)
            scripts=self.scene_scripts(plan,scenes,settings,cancel,stage,prompt=prompt)
        outputs=[];parameters=[];canvas=None
        for position,scene in enumerate(scenes):
            if cancel.is_set():raise Cancelled()
            scoped=scene|{'last':position==len(scenes)-1,'sequence':job_id,'canvas':canvas}
            local=scene_plan(plan,scoped,index,scripts[position])
            def report(label):stage(f'Scena {position+1}/{len(scenes)} · '+label)
            item=self.generate_video(model,settings,local,refs,job_id+f'/scene-{position+1:03d}',cancel,report,prompt=prompt,scene=scoped)
            outputs.append(safe_join(self.data,item['path']));p=item['generation'];parameters.append(p)
            if not canvas and 'canvas_width' in p:canvas={'width':p['canvas_width'],'height':p['canvas_height'],'output_width':p['width'],'output_height':p['height'],'aspect':p['aspect'],'aspect_source':p['aspect_source'],'format_image':p.get('format_image')}
            (folder/'scenes.json').write_text(json.dumps({'timeline':scenes,'prompts':scripts,'completed':position+1,'parameters':parameters},ensure_ascii=False,indent=2),encoding='utf-8')
        result=compose(self,outputs,safe_join(self.data,soundtrack['path']),folder/'video.mp4',cancel,stage,folder/'engine.log')
        return {'id':job_id,'name':'Video MiniMax H3.mp4','mime':'video/mp4','path':(folder/'video.mp4').relative_to(self.data).as_posix(),'generation':parameters[0]|{'duration':result['duration'],'scenes':len(scenes),'scene_parameters':parameters,'audio_preserved':True,'visual_memory':len(scenes)>1}}
