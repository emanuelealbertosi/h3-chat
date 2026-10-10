"""MiniMax H3 uses the private inference runtime and the shared process pool."""
import json
import time
from .downloads import Cancelled, safe_join
from .video_options import options, validate_plan, resolve_canvas
from .video_routing import BRIEF, SCENE_DIRECTION, PLAN_SCHEMA, direct_plan, attachment_instructions
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
             'audio_source_start':settings.get('_video_audio_start',0),
             'conversation':[{'role':m['role'],'text':m['content'][-2000:]} for m in history[-4:] if m.get('status')=='done']},ensure_ascii=False)
        # Reuse the chat model and its CPU mmproj when enabled. Audio is not sent
        # to a text/vision LLM and must never be presented as a transcription.
        visual=[x for x in refs if x['mime'].startswith('image/')]
        if not settings.get('vision_enabled',True) or not llm.get('vision',{}).get('enabled') or len(visual)>llm.get('max_refs',4):visual=[]
        content+='\nVisible images supplied to Assistant: '+str(bool(visual))+'. Do not invent unseen visual details.'
        messages=self.chat_messages([{'role':'user','content':content,'media':visual,'status':'done','seq':1}],llm,settings)
        messages[0]={'role':'system','content':BRIEF+attachment_instructions(assets['images'],assets['audios'])}
        tuning=settings|{'think_level':'off','max_tokens':min(settings['video_prompt_max_tokens'],settings['context']//2)}
        from .video_request import spoken_lines
        speech=spoken_lines(prompt)
        for attempt in range(2):
            raw,finish=self.completion(messages,tuning,cancel,on_text=lambda _:None,schema=PLAN_SCHEMA)
            if finish=='length':raise ValueError('Assistant video ha esaurito i token. Aumenta contesto/token o semplifica la richiesta.')
            try:plan=validate_plan(json.loads(raw),refs,opts['duration'])
            except (ValueError,TypeError) as exc:raise ValueError('Assistant: piano video non valido. '+str(exc)) from exc
            missing=[line for line in speech if line not in plan['prompt']]
            if not missing:break
            if attempt:raise ValueError('Assistant video ha omesso le parole del canto/dialogo anche dopo la correzione. Nessun video è stato avviato.')
            stage('Assistant · recupero le parole esatte del canto/dialogo')
            messages=messages+[{'role':'assistant','content':raw},{'role':'user','content':'Preserve these exact user-supplied spoken/sung words in the video prompt, in their original language: '+json.dumps(missing,ensure_ascii=False)+'. Keep all original timing and actions. Return the complete corrected JSON plan.'}]
        return plan,{'model':llm['name'],'max_tokens':tuning['max_tokens']}

    def generate_video(self,model,settings,plan,refs,job_id,cancel,stage,*,prompt=None,scene=None):
        if model.get('remote_media'):return self.remote_generate(model,settings,prompt if prompt is not None else plan['prompt'],refs,job_id,cancel,stage,plan=plan)
        opts=options(model,settings)
        from .veda import preflight
        preflight(self.root,opts)
        if scene:opts.update(duration=scene['duration'],frames=scene['frames'])
        plan=validate_plan(plan,refs,opts['duration'])
        if any(a['role']=='lipsync' for a in plan['audios']) and opts['steps']<8:
            opts['steps']=8;stage('Lip-sync · uso almeno 8 passi standard')
        folder=self.data/'outputs'/job_id;folder.mkdir(parents=True,exist_ok=True)
        output=folder/'video.mp4'
        request={'op':'generate','output':str(output),'plan':plan,'options':opts,'format_prompt':prompt if prompt is not None else plan['prompt'],
                 'images':[str(safe_join(self.data,x['path'])) for x in refs if x['mime'].startswith('image/')],
                 'audios':[str(safe_join(self.data,x['path'])) for x in refs if x['mime'].startswith('audio/')]}
        image_sizes=[]
        if request['images']:
            # Pillow belongs to the bundled video runtime, not the HTTP host.
            # Read headers in a small cancellable worker without loading Torch.
            image_sizes=self.tool_call('image-size-worker.py',{'paths':request['images']},
                cancel,stage,folder/'image-size.log',timeout=30)['sizes']
        opts=resolve_canvas(opts,plan,image_sizes,request['format_prompt'])
        if scene and scene.get('canvas'):opts.update(scene['canvas'])
        request['options']=opts
        if scene:
            request.update(sequence=scene['sequence'],scene_index=scene['index'],canvas=scene.get('canvas'),audio_tail_padding=bool(scene.get('last')))
            if 'continuity' in scene:request['continuity']=scene['continuity']
            if scene.get('resume_memory'):request['resume_memory']=scene['resume_memory']
        (folder/'video-plan.json').write_text(json.dumps({'plan':plan,'parameters':opts},ensure_ascii=False,indent=2),encoding='utf-8')
        stage(f"Video · formato {opts['aspect']} · {opts['output_width']}×{opts['output_height']}")
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
        actual=opts|done.get('parameters',{})|{'startup_seconds':startup_seconds,'quality':settings.get('_video_quality','high')}
        (folder/'video-plan.json').write_text(json.dumps({'plan':plan,'parameters':actual},ensure_ascii=False,indent=2),encoding='utf-8')
        return {'id':job_id,'name':'Video MiniMax H3.mp4','mime':'video/mp4','path':output.relative_to(self.data).as_posix(),'generation':actual}

    def scene_scripts(self,plan,scenes,settings,cancel,stage,*,prompt):
        """Bound each structured call; retain continuity across prompt batches."""
        budget=min(settings['context']//2,settings['video_prompt_max_tokens'])
        tuning=settings|{'max_tokens':budget,'think_level':'off'}
        size=max(1,min(3,budget//768));scripts=[]
        brief=BRIEF.replace('Return JSON prompt, images, audios.','Return only JSON {"scenes":[{"prompt":English prompt per requested clip,"time_basis":"local"}]}.')+'\nDescribe one continuous film, preserving Picture/Audio labels, identities, style and the language of any supplied dialogue. Do not invent unheard lyrics. Return only the requested clips, in order. Use supplied previous prompts and opening as visual continuity, not as repeated action. No opening restart or finale before the last clip. Translate global keyframe times into LOCAL clip times. Each prompt must be concise while retaining the required MiniMax section labels; never return images/audios arrays.\n'+SCENE_DIRECTION+attachment_instructions(plan['images'],plan['audios'])
        refs=[{'mime':'image/png'} for _ in plan['images']]+[{'mime':'audio/wav'} for _ in plan['audios']]
        def produce(group):
            schema={'type':'object','properties':{'scenes':{'type':'array','minItems':len(group),'maxItems':len(group),'items':{'type':'object','properties':{'prompt':{'type':'string'},'time_basis':{'type':'string','enum':['local','video','source']}},'required':['prompt','time_basis'],'additionalProperties':False}}},'required':['scenes'],'additionalProperties':False}
            correction=None;rejected=None
            for attempt in range(2):
                if cancel.is_set():raise Cancelled()
                first,last=group[0]['index']+1,group[-1]['index']+1
                stage(f'Assistant · sceneggiatura · scene {first}–{last}/{len(scenes)}'+(' · nuovo tentativo conciso' if attempt else ''))
                context={'request':prompt,'plan':plan,'total_scenes':len(scenes),'film_duration':scenes[-1]['start']+scenes[-1]['duration'],'audio_source_start':settings.get('_video_audio_start',0),'clips':group,'opening':scripts[0] if scripts else None,'previous':scripts[-2:]}
                if rejected:context['rejected_scenes']=rejected
                instructions=brief+f'\nOutput budget: {budget} tokens for {len(group)} clip(s). Aim for at most {max(40,min(220,budget//(3*len(group))))} words per clip.'
                instructions+='\nEach scenes item is {"prompt":English MiniMax prompt,"time_basis":"local"}. All action/cut/vocal timestamps must run from 00:00 to this clip duration. Subtract clips.start from global FILM times; subtract audio_source_start + clips.start from SOURCE audio times. Preserve the exact order, timing intervals and words of the original request. Do not move actions to different times. time_basis="video" or "source" is allowed only when clocks deliberately use that coordinate system; never mix bases within a prompt. Previous prompts use their own clip-local clocks, not the clocks for this clip.'
                if attempt and not correction:instructions+=' Previous output was empty or incomplete. Return short, complete JSON immediately.'
                if correction:instructions+='\nPrevious output failed scene validation: '+correction+'. Rewrite this batch following the original request, correcting the invalid parts. Use only allowed labels and preserve the original soundtrack; do not request or invent an image. Do not replay an earlier action unless the user explicitly asked for that repetition.'
                try:
                    raw,finish=self.completion([{'role':'system','content':instructions},{'role':'user','content':json.dumps(context,ensure_ascii=False)}],tuning,cancel,on_text=lambda _:None,schema=schema)
                    if finish=='length':raise StructuredCompletionError('Output limit reached')
                    try:value=json.loads(raw)
                    except (ValueError,TypeError) as exc:raise StructuredCompletionError('Incomplete scene JSON') from exc
                    value=value.get('scenes') if isinstance(value,dict) and set(value)=={'scenes'} else None
                    if not isinstance(value,list) or len(value)!=len(group):raise StructuredCompletionError('Incomplete scene list')
                    try:
                        from .video_timing import localize
                        normalized=[]
                        for item,clip in zip(value,group):
                            if isinstance(item,str):text=item;basis='auto'
                            elif isinstance(item,dict) and set(item)=={'prompt','time_basis'}:text=item['prompt'];basis=item['time_basis']
                            else:raise StructuredCompletionError('Incomplete scene prompt')
                            if not isinstance(text,str) or not text.strip():raise StructuredCompletionError('Empty scene prompt')
                            normalized.append(localize(text,clip,basis=basis,audio_start=settings.get('_video_audio_start',0)))
                        value=normalized
                        from .video_timeline import scene_plan
                        for text,clip in zip(value,group):
                            # Validate the local prompt before any clip spends GPU time.
                            local=scene_plan(plan,clip|{'last':clip['index']==scenes[-1]['index']},0,text)
                            validate_plan(local,refs,clip['duration'])
                    except ValueError as exc:
                        if not attempt:
                            correction=str(exc);stage('Assistant · correggo i riferimenti della sceneggiatura');continue
                        raise ValueError(f'Assistant video: la scena {clip["index"]+1} non è valida anche dopo la correzione. {exc} Nessun video è stato avviato.') from exc
                    from .video_request import repeated_scene
                    duplicate=repeated_scene(scripts,value,prompt)
                    if duplicate:
                        if not attempt:
                            correction=f'Clip {duplicate} copies an earlier scene instead of advancing the action';rejected=value
                            stage('Assistant · correggo le scene ripetute');continue
                        raise ValueError(f'Assistant video: la scena {duplicate} ripete una scena precedente anche dopo la correzione. Nessun video è stato avviato.')
                    scripts.extend(value);return
                except (EmptyCompletion,StructuredCompletionError) as exc:
                    if len(group)>1:
                        stage('Assistant · piano incompleto · divido il gruppo di scene')
                        middle=len(group)//2;produce(group[:middle]);produce(group[middle:]);return
                    if attempt:raise ValueError(f'Assistant video non ha completato la scena {first} dopo due tentativi. Aumenta i token Assistant video o scegli un altro LLM; puoi usare Assistant Off. Nessun video è stato avviato.') from exc
        for start in range(0,len(scenes),size):produce(scenes[start:start+size])
        return scripts

    def generate_long_video(self,model,settings,plan,refs,job_id,cancel,stage,*,prompt):
        from .video_timeline import timeline,scene_plan,validate_audio_interval
        from .video_resume import checkpoint,save as save_checkpoint
        from .soundtrack import compose,probe
        scenes=timeline(settings['_video_duration']);soundtrack=settings['_video_soundtrack'];audio_start=settings.get('_video_audio_start',0)
        if model.get('remote_media') and len(scenes)>1:raise ValueError('Video a più scene con memoria: seleziona il motore MiniMax H3 standalone. Il server esterno deve supportare esplicitamente questa funzione.')
        index=next(i for i,m in enumerate([r for r in refs if r['mime'].startswith('audio/')],1) if m['id']==soundtrack['id'])
        scripts=[plan['prompt']]*len(scenes)
        folder=self.data/'outputs'/job_id;folder.mkdir(parents=True,exist_ok=True)
        resumed=checkpoint(self.data,settings['_video_resume']) if settings.get('_video_resume') else None
        storyboard=None
        if settings.get('_video_editing')=='storyboard':
            from .video_storyboard import build
            if resumed:
                storyboard=resumed.get('storyboard')
                if not storyboard:raise ValueError('Il video salvato non contiene uno storyboard da recuperare.')
                if abs(resumed['timeline'][-1]['start']+resumed['timeline'][-1]['duration']-settings['_video_duration'])>1/24:
                    raise ValueError('La durata dello storyboard salvato è cambiata.')
            else:storyboard=build(self,plan,refs,settings,prompt,cancel,stage,folder/'engine.log')
            scenes=storyboard['shots'];scripts=[s['prompt'] for s in scenes]
        if resumed and (resumed['timeline']!=scenes or resumed.get('model',model.get('id',''))!=model.get('id','')):raise ValueError('Il modello o la durata audio sono cambiati: il video salvato non può essere ripreso.')
        if resumed and resumed.get('audio_start',0)!=audio_start:raise ValueError('Il segmento audio è cambiato: le scene salvate non possono essere riprese.')
        # Validate every exact source interval BEFORE spending GPU time. The
        # selected track's decoded length was already measured by the service.
        durations={index:settings.get('_video_audio_source_duration',audio_start+settings['_video_duration'])}
        audios=[r for r in refs if r['mime'].startswith('audio/')]
        for position,scene in enumerate(scenes):
            local=scene_plan(plan,scene|{'last':position==len(scenes)-1},index,audio_start=audio_start,normalize=False)
            for entry in local['audios']:
                if entry['role'] not in ('reuse','lipsync'):continue
                ordinal=entry['index']
                if ordinal not in durations:durations[ordinal]=probe(self,self.data,audios[ordinal-1],cancel,stage,folder/'engine.log')['duration']
                validate_audio_interval(durations[ordinal],entry['start'],scene['duration'],tail=position==len(scenes)-1)
        if resumed:scripts=resumed['prompts'];plan=resumed['plan']
        elif not storyboard and len(scenes)>1 and settings.get('_assistant',True):
            stage(f'Assistant · sceneggiatura continua in {len(scenes)} scene')
            llm=self.require_model(settings['chat_model'],'chat');self.start_llama(llm,settings,folder/'engine.log',cancel,stage=stage)
            scripts=self.scene_scripts(plan,scenes,settings,cancel,stage,prompt=prompt)
        if settings.get('_assistant',True):
            from .video_request import repeated_scene
            duplicate=repeated_scene([],scripts,prompt)
            if duplicate and (not resumed or duplicate>resumed['completed']):
                raise ValueError(f'Piano video: la scena {duplicate} ripete una scena precedente. Nessuna nuova scena è stata avviata. Invia una nuova richiesta per correggere il piano salvato.')
        # Check remaining scripts too when resuming an older checkpoint or
        # using Assistant Off, before loading the video model for any clip.
        for position,scene in enumerate(scenes):
            if resumed and position<resumed['completed']:continue
            try:
                if storyboard:
                    from .video_storyboard import local_plan
                    local,local_refs=local_plan(storyboard,scene,plan,refs,index,audio_start)
                else:local=scene_plan(plan,scene|{'last':position==len(scenes)-1},index,scripts[position],audio_start=audio_start,shared=not settings.get('_assistant',True));local_refs=refs
                validate_plan(local,local_refs,scene['duration'])
            except ValueError as exc:raise ValueError(f'Piano video: la scena {position+1} non è valida. {exc} Nessuna nuova scena è stata avviata.') from exc
        outputs=[safe_join(self.data,path) for path in resumed['outputs']] if resumed else []
        parameters=list(resumed['parameters']) if resumed else [];canvas=None
        def saved_canvas(p):return {'width':p['canvas_width'],'height':p['canvas_height'],'output_width':p['width'],'output_height':p['height'],'aspect':p['aspect'],'aspect_source':p['aspect_source'],'format_image':p.get('format_image')}
        if parameters and 'canvas_width' in parameters[0]:canvas=saved_canvas(parameters[0])
        def relative_output(path):return path.resolve().relative_to(self.data.resolve()).as_posix()
        record={'timeline':scenes,'prompts':scripts,'plan':plan,'model':model.get('id',''),'audio_start':audio_start,'completed':len(outputs),'parameters':parameters,'outputs':[relative_output(p) for p in outputs]}
        if storyboard:record['storyboard']=storyboard
        save_checkpoint(folder,record)
        completed=len(outputs)
        for position,scene in enumerate(scenes):
            if position<completed:continue
            if cancel.is_set():raise Cancelled()
            scoped=scene|{'last':position==len(scenes)-1,'sequence':job_id,'canvas':canvas}
            if resumed and completed and position==completed and scene.get('continuity')!='cut':
                anchor=max((i for i in range(position) if scenes[i].get('continuity')=='cut'),default=0) if storyboard else 0
                scoped['resume_memory']={'opening':str(outputs[anchor]),'recent':[str(p) for p in outputs[anchor:][-2:]]}
            if storyboard:local,local_refs=local_plan(storyboard,scene,plan,refs,index,audio_start)
            else:local=scene_plan(plan,scoped,index,scripts[position],audio_start=audio_start,shared=not settings.get('_assistant',True));local_refs=refs
            def report(label):stage(f'{"Clip" if storyboard else "Scena"} {position+1}/{len(scenes)} · '+label)
            item=self.generate_video(model,settings,local,local_refs,job_id+f'/scene-{position+1:03d}',cancel,report,prompt=prompt,scene=scoped)
            outputs.append(safe_join(self.data,item['path']));p=item['generation'];parameters.append(p)
            if not canvas and 'canvas_width' in p:canvas=saved_canvas(p)
            record.update(completed=position+1,outputs=[relative_output(p) for p in outputs]);save_checkpoint(folder,record)
        result=compose(self,outputs,safe_join(self.data,soundtrack['path']),folder/'video.mp4',cancel,stage,folder/'engine.log',audio_start=audio_start,audio_duration=settings['_video_duration'])
        return {'id':job_id,'name':'Video MiniMax H3.mp4','mime':'video/mp4','path':(folder/'video.mp4').relative_to(self.data).as_posix(),'generation':parameters[0]|{'duration':result['duration'],'audio_start':audio_start,'scenes':len(scenes),'scene_parameters':parameters,'audio_preserved':True,'visual_memory':len(scenes)>1,'recovered_scenes':completed,'editing':'storyboard' if storyboard else 'continuous',**({'storyboard':storyboard} if storyboard else {})}}
