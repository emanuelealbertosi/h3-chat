"""LLM-authored editable graphics with measured narration and deterministic motion."""
import json
import math
import re
from pathlib import Path
from uuid import uuid4
from .downloads import Cancelled,safe_join
from .slides import FORMATS,encode,validate_content
from .message_content import append_text
from . import infographic_screen as screen
from . import infographic_text as typography

MAX_DURATION=600
MAX_SCENES=30

def render_timeout(duration):
    return max(7200,math.ceil(duration*30)+600)

CHOICES={'format':tuple(FORMATS),'style':('auto','professional','playful','comic','editorial','advert','tech'),
 'palette':('auto','natural','pastel','vivid','neon','dark'),'shapes':('auto','soft','sharp','mixed'),
 'pace':('auto','calm','dynamic','spot','explainer'),'images':('auto','provided','generate'),'character_animation':('illustrated','articulated'),
 'music':('auto','none','uploaded','generate','jingle'),'sfx':('none','subtle','strong'),
 'transition':('auto','cut','fade','slide','zoom','wipe'),'voice_style':('auto','serious','lively','spot','warm','radio'),'voice_gender':('auto','female','male','mixed'),
 'output':('video','static'),'corners':('square','soft','round'),'frame':('dark','light'),
 'video_background':('auto','off'),'video_fit':('contain','cover'),'video_end':('freeze','loop'),'video_audio':('mute','keep','duck'),'video_start':('together','panel'),'background':('auto','light','dark','custom'),'animation_engine':('classic','motion')}
DEFAULTS={'format':'9:16','style':'auto','palette':'auto','shapes':'auto','pace':'auto','images':'auto',
 'music':'auto','sfx':'subtle','transition':'auto','transition_seconds':.9,'voice_style':'auto','voice_gender':'auto','output':'video','duration':30,'scenes':3,'voice':True,'image_model':'','corners':'square','frame':'dark','character_animation':'illustrated',
 'video_background':'auto','video_id':'','video_fit':'contain','video_end':'freeze','video_audio':'mute','video_start':'together','background_style':None,'background':'auto','background_color':'#f7f3e8','animation_engine':'classic','sprite_ids':[]}|screen.DEFAULTS|typography.DEFAULTS
CHOICES.update(typography.CHOICES)
CHOICES['visual_mode']=('normal','decorative','sequence')
DEFAULTS['visual_mode']='normal'
from .infographic_voices import CHOICES as VOICE_PROFILES
CHOICES['voice_profile']=VOICE_PROFILES
DEFAULTS['voice_profile']='auto'

def plan_regia(engine,base,brief,schema,settings,cancel,stage,scenes):
    """Bound planning separately from the user's final-output allowance.

    Retry a stalled grammar as ordinary JSON; the LLM still authors every field.
    Neither failed partial output nor reasoning becomes a new source on retry.
    """
    class Stalled(ValueError):pass
    duration=settings.get('_infographic',{}).get('duration',30)
    tuning=settings|{'think_level':'off','temperature':min(settings['temperature'],.3),
        'max_tokens':min(settings['max_tokens'],max(2400,scenes*700,duration*6)), 'llm_timeout':min(settings.get('llm_timeout',1800),max(180,scenes*20,duration))}
    instruction='Scrivi SOLO un oggetto JSON completo e conciso secondo lo schema. Non scrivere ragionamenti, HTML, codice Python o il contenuto integrale delle fonti. La regia è una scaletta, non il prodotto finale. Rispetta il numero di scene.\n'
    checked=[0]
    def progress(text):
        # Some constrained decoders loop on legal whitespace or repeated text.
        if len(text)-checked[0]<256:return
        checked[0]=len(text)
        tail=text[-1600:]
        if len(tail)==1600 and (not tail.strip() or any(tail.endswith(tail[-n:]*8) for n in range(1,161))):
            raise Stalled('La pianificazione ripete testo senza avanzare.')
    for attempt in range(2):
        if cancel.is_set():raise Cancelled()
        if attempt:stage('Infografica · secondo tentativo di regia breve')
        checked[0]=0
        request=base+[{'role':'user','content':instruction+brief+'\nSchema JSON: '+json.dumps(schema,ensure_ascii=False)}]
        try:
            raw,finish=engine.completion(request,tuning,cancel,on_text=progress,schema=schema if not attempt else None)
            if finish=='length':raise Stalled('Il modello non ha concluso la scaletta nel budget di pianificazione.')
            raw=raw.strip()
            if raw.startswith('```'):raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw,flags=re.I)
            plan=json.loads(raw)
            if not isinstance(plan,dict) or not isinstance(plan.get('scenes'),list) or len(plan['scenes'])!=scenes or plan.get('delivery') not in ('serious','lively','spot','warm'):raise ValueError('Regia infografica non valida.')
            for row in plan['scenes']:
                if not isinstance(row,dict) or any(not isinstance(row.get(k),str) or not row[k].strip() or len(row[k])>(12000 if k=='narration' else 6000) for k in ('title','purpose','narration')):raise ValueError('Scena infografica non valida.')
            if not isinstance(plan.get('title'),str) or not 1<=len(plan['title'])<=150:raise ValueError('Titolo infografica non valido.')
            if any(not isinstance(plan.get(k),str) or len(plan[k])>6000 for k in ('visual_direction','music_style','jingle_lyrics')):raise ValueError('Direzione artistica o musica non valida.')
            return plan
        except (ValueError,TypeError):
            if attempt:raise ValueError('Il modello non ha completato una regia valida dopo due tentativi. Non è un esaurimento del contesto: prova a rigenerare o cambia modello LLM.') from None

def requested(prompt):
    return bool(re.search(r'\b(?:crea\w*|genera\w*|fammi|realizza\w*|create|generate)\b[\s\S]{0,150}\b(?:infografic\w*|infographic\w*)\b',prompt,re.I))

def options(prompt='',value=None):
    if value is not None and (not isinstance(value,dict) or set(value)-set(DEFAULTS)):raise ValueError('Opzioni infografica non valide.')
    result=DEFAULTS|dict(value or {})
    mode=list(re.finditer(r'\b(?:modalit[àa]|infografica)\s+(normale|decorativa)\b',prompt,re.I))
    if mode:result['visual_mode']='normal' if mode[-1][1].lower()=='normale' else 'decorative'
    if re.search(r'\b(?:piano[ -]sequenza|plan[ -]s[eé]quence)\b',prompt,re.I) and not re.search(r'\b(?:senza|no)\s+piano[ -]sequenza\b',prompt,re.I):result['visual_mode']='sequence'
    if re.search(r'\bmotion\s+graphics\b',prompt,re.I):result['animation_engine']='motion'
    if re.search(r'\b(?:modalit[àa]|motore)\s+classic[oa]\b',prompt,re.I):result['animation_engine']='classic'
    actors=list(re.finditer(r'\bpersonaggi?\s+articolat[oi]\b',prompt,re.I))
    if actors:
        prefix=prompt[max(0,actors[-1].start()-40):actors[-1].start()]
        if re.search(r'\b(?:senza|nessun|nessuno|nessuni|evita|non\s+usare|non\s+creare)\s+(?:i\s+|un\s+)?$',prefix,re.I):result['character_animation']='illustrated'
        else:result.update(character_animation='articulated',animation_engine='motion')
    if re.search(r'\b(?:ritmo|stile)\s+(?:rapido\s+)?(?:youtube|yt)\b',prompt,re.I):result['pace']='explainer'
    if result['visual_mode'] in ('decorative','sequence'):result.update(animation_engine='classic',character_animation='illustrated')
    if result['character_animation']=='articulated' and result['animation_engine']!='motion':raise ValueError('I personaggi articolati richiedono Motion Graphics.')
    ids=result['sprite_ids']
    if not isinstance(ids,list) or len(ids)>12 or any(not isinstance(i,str) or not re.fullmatch('[0-9a-f]{32}',i) for i in ids) or len(set(ids))!=len(ids):raise ValueError('Selezione sprite non valida.')
    if result['animation_engine']=='motion' and result.get('layout','full')!='full':raise ValueError('Motion Graphics usa la scena libera multilivello: scegli composizione Intero. I riquadri restano disponibili nella modalità classica.')
    if not isinstance(result['background_color'],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',result['background_color']):raise ValueError('Colore sfondo infografica non valido.')
    requested=list(re.finditer(r'\b(?:sfondo|fondale|background)\s+(?:principale\s+)?(chiaro|bianco|scuro|nero|light|dark|#[0-9a-fA-F]{6})\b',prompt,re.I))
    if requested:
        color=requested[-1][1].lower()
        result['background']='custom' if color.startswith('#') else 'light' if color in ('chiaro','bianco','light') else 'dark'
        if color.startswith('#'):result['background_color']=color
    from .slide_background_style import options as background_options
    result['background_style']=background_options(result['background_style'])
    if result['background_style']:result.update(video_background='off',video_id='')
    timing_span=screen.prompt_timing(prompt,result)
    screen.validate(result)
    typography.validate(result)
    for key,choices in CHOICES.items():
        if result[key] not in choices:raise ValueError('Opzione infografica non valida: '+key)
    for key,lo,hi in (('duration',5,MAX_DURATION),('scenes',1,MAX_SCENES)):
        if type(result[key]) is not int or not lo<=result[key]<=hi:raise ValueError('Infografica: '+key+' fuori intervallo.')
    if type(result['voice']) is not bool or not isinstance(result['image_model'],str) or len(result['image_model'])>150:raise ValueError('Voce o modello infografica non valido.')
    if type(result['transition_seconds']) not in (int,float) or not math.isfinite(result['transition_seconds']) or not .15<=result['transition_seconds']<=2:raise ValueError('Transizioni infografica: durata da 0,15 a 2 secondi.')
    if not isinstance(result['video_id'],str) or len(result['video_id'])>150:raise ValueError('Riferimento video non valido.')
    duration_prompt=prompt if timing_span is None else prompt[:timing_span[0]]+prompt[timing_span[1]:]
    minute=re.search(r'\b(\d+)\s*(?:minut[oi]\b|minutes?\b|min\b)(?:\s*(?:e|and)?\s*(\d+)\s*(?:secondi|seconds|sec\b|s\b))?',duration_prompt,re.I)
    match=re.search(r'\b(\d+)\s*(?:secondi|seconds|sec\b|s\b)',duration_prompt,re.I)
    if minute or match:
        duration=int(minute[1])*60+int(minute[2] or 0) if minute else int(match[1])
        if not 5<=duration<=MAX_DURATION:raise ValueError('Infografiche animate: durata da 5 secondi a 10 minuti.')
        result['duration']=duration
    count=re.search(r'\b(\d+)\s*(?:scen[ae]|scenes)\b',prompt,re.I)
    if count:
        if not 1<=int(count[1])<=MAX_SCENES:raise ValueError('Infografiche: scegli da 1 a 30 scene.')
        result['scenes']=int(count[1])
    for fmt in FORMATS:
        if fmt in prompt:result['format']=fmt;break
    from .infographic_audio import narration_disabled
    if narration_disabled(prompt):result['voice']=False
    from .infographic_audio import prompt_voice
    result.update(prompt_voice(prompt))
    if re.search(r'\b(?:senza effetti sonori|no sfx)\b',prompt,re.I):result['sfx']='none'
    if re.search(r'\b(?:statica|statico|solo immagine)\b',prompt,re.I):result['output']='static'
    if result['music']=='auto':
        result['music']='jingle' if re.search(r'\bjingle\b',prompt,re.I) else 'generate' if re.search(r'\b(?:musica|musichetta|sottofondo musicale)\b',prompt,re.I) and not re.search(r'\bsenza\s+musica\b',prompt,re.I) else 'none'
    return result


def background_direction(opts):
    from .slide_colors import brief
    return brief({k:opts[k] for k in ('background','background_color')})+('\nSfondo automatico: scegli la luminosità in base al tema, al prompt e alle fonti. Lo stile tech o spot e gli accenti vivaci NON impongono nero, blu notte o neon. Alterna superfici chiare e colori coerenti quando opportuno. frame riguarda solo gli angoli esterni del video, non il fondale delle scene.' if opts.get('background','auto')=='auto' else '')

def validate_motion(deck):
    motion=deck.get('infographic')
    if not motion:return
    if not isinstance(motion,dict) or motion.get('version')!=1:raise ValueError('Timeline infografica non valida.')
    durations=motion.get('durations')
    if not isinstance(durations,list) or not 1<=len(durations)<=MAX_SCENES or len(durations)!=len(deck['pages']) or any(type(v) not in (int,float) or not math.isfinite(v) or not .1<=v<=MAX_DURATION for v in durations) or math.fsum(durations)>MAX_DURATION+1e-6:raise ValueError('Durate infografica non valide: massimo 10 minuti e 30 scene.')
    if motion.get('transition') not in ('cut','fade','slide','zoom','wipe') or motion.get('sfx') not in CHOICES['sfx']:raise ValueError('Effetti infografica non validi.')
    graph_version=motion.get('scene_format_version')
    if graph_version is not None and graph_version!=2:raise ValueError('Versione Motion Graphics non supportata.')
    if graph_version==2:
        from .infographic_scene import validate as validate_scene
        for index,page in enumerate(deck['pages']):
            graph=page.get('motion_scene')
            if graph is None and page.get('status')!='ready':continue
            graph=validate_scene(graph)
            if abs(graph['duration']-durations[index])>1e-6:raise ValueError('Durata Motion Graphics diversa dalla timeline della scena '+str(index+1)+'.')
            width,height=FORMATS[deck['format']]
            if abs(graph['width']/graph['height']-width/height)>1e-6:raise ValueError('Proporzioni Motion Graphics diverse dal documento.')
        rigs=motion.get('rigs',[])
        if not isinstance(rigs,list) or len(rigs)>14:raise ValueError('Catalogo personaggi del progetto non valido.')
        if rigs:
            from .motion_rigs import validate_rig
            for rig in rigs:validate_rig(validate_scene(rig['scene']),rig['rig'])
    elif any('motion_scene' in page for page in deck['pages']):raise ValueError('Specifica il formato Motion Graphics v2 per queste scene.')
    if 'options' in motion:options(value=motion['options'])
    if 'video' in motion:
        from .infographic_video import validate
        validate(motion['video'])
    if 'videos' in motion:
        from .infographic_video import validate
        videos=motion['videos']
        if not isinstance(videos,list) or not 1<=len(videos)<=6:raise ValueError('Video dei riquadri non validi.')
        for video in videos:validate(video)
        if len({v['asset_id'] for v in videos})!=len(videos):raise ValueError('Video duplicati nei riquadri.')

def build(app,job,payload,history,settings,model,cancel,stage,log,meta):
    # Regenerate/queued jobs retain the settings snapshot from their creation.
    # Complete newly introduced options at execution time without changing the
    # stored snapshot or the user's model presets.
    opts=options(value=settings.get('_infographic'));settings=settings|{'_infographic':opts}
    folder=app.data/'outputs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
    from .slide_context import compact_history
    from .slide_html import generate as generate_html
    from .infographic_animation import HTML_BRIEF,ensure as ensure_animation
    from .infographic_layout import brief as layout_brief,ensure as ensure_layout
    from .voice import synthesize
    from .narrated_manim import measured_scenes
    from .infographic_video import select_many
    video_items=select_many(opts,payload['media']);videos=[];posters=[]
    for index,item in enumerate(video_items):
        stage(f'Infografica · lettura video {index+1}/{len(video_items)}')
        relative=(folder/f'video-poster-{index+1}.jpg').relative_to(app.data).as_posix()
        info=app.engine.tool_call('infographic-video-worker.py',{'data':str(app.data),'media':[item],'id':item['id'],'poster':relative},cancel,stage,log)
        poster={'id':uuid4().hex,'name':'Anteprima · '+item['name'],'mime':'image/jpeg','path':relative};posters.append(poster)
        videos.append(info|{'asset_id':item['id'],'poster_id':poster['id'],'fit':opts['video_fit'],'end':opts['video_end'],'sound':opts['video_audio'] if index==0 else 'mute'})
    video=videos[0] if videos and opts['layout']=='full' else None
    poster=posters[0] if video else None
    assets=[];seen=set()
    recent=[x for m in history for x in m.get('media',[]) if x.get('mime','').startswith('image/')][-32:]
    for item in meta.pop('_slide_assets',[])+recent:
        if item.get('mime','').startswith('image/') and not item.get('slide_background') and item['id'] not in seen and item['path'].startswith(('uploads/','outputs/','document-cache/')):seen.add(item['id']);assets.append(item)
    assets=assets[:32]
    import shutil
    for index,item in enumerate(assets):
        if item['path'].startswith('document-cache/'):
            target=folder/'scan-pages'/(item['id']+'.png');target.parent.mkdir(exist_ok=True)
            shutil.copyfile(safe_join(app.data,item['path']),target);assets[index]=item|{'path':target.relative_to(app.data).as_posix()}
    app.engine.start_llama(model,settings,log,cancel,stage=stage)
    descriptions={}
    analysis_assets=assets+posters
    if analysis_assets and settings.get('vision_enabled',True) and model.get('vision',{}).get('enabled',False):
        from .slide_vision import describe
        descriptions=describe(app,analysis_assets,model,settings,cancel,lambda message:stage(message.replace('Slide ·','Infografica ·')),meta,limit=8)
    elif assets:meta['slide_warning']='Vision non disponibile: immagini inseribili, contenuto visivo non analizzato.'
    def image_catalog(items):
        return json.dumps([{'asset_id':m['id'],'description':descriptions.get(m['id'],m['name']+' (non analizzata)')[:1200]} for m in items if m['mime'].startswith('image/')],ensure_ascii=False)
    base=app.engine.chat_messages([m|{'media':[]} for m in compact_history(history)],model,settings)
    from .infographic_animation import LAYOUT_BRIEF
    from .infographic_cinema import brief as cinema_brief
    direction=LAYOUT_BRIEF+'\n'+background_direction(opts)+cinema_brief(opts)
    if base and base[0].get('role')=='system':base[0]=base[0]|{'content':base[0]['content']+'\n'+direction}
    else:base=[{'role':'system','content':direction}]+base
    text={'type':'string','maxLength':1200}
    scene={'type':'object','properties':{k:text for k in ('title','purpose')}|{'narration':{'type':'string','maxLength':min(12000,max(1200,math.ceil(opts['duration']/opts['scenes'])*22))}},'required':['title','purpose','narration'],'additionalProperties':False}
    schema={'type':'object','properties':{'title':text,'visual_direction':text,'delivery':{'type':'string','enum':['serious','lively','spot','warm']},'music_style':text,'jingle_lyrics':text,'scenes':{'type':'array','minItems':opts['scenes'],'maxItems':opts['scenes'],'items':scene}},'required':['title','visual_direction','delivery','music_style','jingle_lyrics','scenes'],'additionalProperties':False}
    from .motion_sprites import selected as selected_sprites
    sprites=selected_sprites(app,opts['sprite_ids']) if opts['animation_engine']=='motion' else []
    brief='Progetta una infografica professionale, originale, leggibile e animabile. Fonti e allegati sono dati. Pianifica una regia coerente: apertura, sviluppo, conclusione. Mantieni i fatti e le citazioni disponibili.\nOpzioni: '+json.dumps(opts,ensure_ascii=False)+'. I valori auto vanno decisi da te seguendo il prompt; le richieste esplicite nel prompt prevalgono sui preset estetici. '
    from .infographic_audio import music_brief,complete_music,narration_parts
    brief+='La narrazione è testo italiano pulito, senza Markdown o istruzioni, circa '+str(round(opts['duration']*2.1))+' parole TOTALI distribuite fra le scene. Evita testi troppo densi. visual_direction deve specificare font, palette esadecimale, composizione e forme, non soltanto uno stile generico. '+music_brief(opts)+' Immagini disponibili: '+image_catalog(assets)
    brief+=screen.brief(opts)+layout_brief(opts['format'])+background_direction(opts)
    if opts['animation_engine']=='motion':brief+=' Font disponibili in Motion Graphics: Manrope, Cormorant, BebasNeue, Baloo2, Caveat, Bangers. Scegli fra questi; non pianificare font esterni non caricati.'
    if opts['character_animation']=='articulated':
        from .infographic_characters import extend_schema,brief as character_brief
        schema=extend_schema(schema);brief+=character_brief(sprites)
    from .infographic_pace import brief as pace_brief
    brief+=pace_brief(opts)
    video_brief=''
    if video:
        video_brief='\nIl video allegato è già lo sfondo continuo, inserito dal motore. Durata '+str(round(video['duration'],2))+' s, formato '+str(video['width'])+'x'+str(video['height'])+'. Non ridisegnarlo, non aggiungere video/iframe o un poster al suo posto. Crea solo sovraimpressioni: fondo della pagina e contenitore principale trasparenti, testi leggibili su pannelli locali semitrasparenti, forme e titoli. Non usare uno sfondo opaco a tutta pagina. Analisi del solo primo fotogramma: '+descriptions.get(poster['id'],'non disponibile; non inventare il contenuto del filmato')
        brief+=video_brief
    elif videos:
        video_brief='\nCatalogo video autorizzati: '+json.dumps([{'numero':i+1,'asset_id':v['asset_id'],'name':video_items[i]['name'],'description':descriptions.get(posters[i]['id'],'non analizzato'),'width':v['width'],'height':v['height']} for i,v in enumerate(videos)],ensure_ascii=False)
        video_brief+=' Puoi inserire i clip nei riquadri usando SOLO <div data-video-asset-id="ID" style="width:100%;height:100%"></div>, vuoto e con dimensioni esplicite. Il motore inserisce il filmato autorizzato, continuativo fra scene. Non scrivere tag video/iframe, URL o poster sostitutivi. Usa altri elementi per testi in sovraimpressione. Scegli tu gli abbinamenti seguendo il prompt; puoi usare immagini e grafici nei riquadri senza video.'
        brief+=video_brief
    stage('Infografica · regia, contenuti e narrazione')
    plan=plan_regia(app.engine,base,brief,schema,settings,cancel,stage,opts['scenes'])
    if opts['character_animation']=='articulated':
        from .infographic_characters import validate_plan
        validate_plan(plan,sprites)
    plan=complete_music(app.engine,base,plan,opts,settings,cancel,stage)
    (folder/'regia.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    references=[{'id':s['citation'],'label':s['name']+' · '+s['location']} for s in meta.get('rag_sources',[])]
    references.extend({'id':d.get('citation','D'+str(i)),'label':d['name']+' · '+', '.join(d.get('locations',[]))} for i,d in enumerate(meta.get('documents',[]),1))
    references += [{'id':'D'+str(i),'label':d['name']} for i,d in enumerate(meta.get('documents',[]),1)]
    references += [{'id':'W'+str(i),'label':s['title'],'url':s['url']} for i,s in enumerate(meta.get('web_sources',[]),1)]
    references += [{'id':'I'+str(i),'label':m['name']} for i,m in enumerate(assets,1)]
    deck={'version':1,'engine':'llm','title':plan['title'],'format':opts['format'],'theme':'lagoon','typography':'modern','design':'professional','detail':'concise','references':references,
        'pages':[{'title':s['title'][:150],'html':'','status':'pending','notes':s['narration'],'sources':[]} for s in plan['scenes']],'active':0,
        'infographic':{'version':1,'durations':[opts['duration']/opts['scenes']]*opts['scenes'],'transition':'fade' if opts['transition']=='auto' else opts['transition'],'sfx':opts['sfx'],'options':opts,'delivery':plan['delivery']}}
    if settings.get('_video_clip_target'):
        target=settings['_video_clip_target']
        deck['infographic']['timeline_target']=target
        deck['infographic']['durations']=[target['end']-target['start']]
    media=list(assets)+video_items+posters
    from .slide_background_style import assign as assign_backgrounds,brief as background_brief
    media.extend(m for m in settings.get('_slide_background_assets',[]) if m['id'] not in {a['id'] for a in media})
    assign_backgrounds(deck,opts.get('background_style'),media)
    if opts['animation_engine']=='motion':
        if video or videos or opts.get('background_style'):raise ValueError('Motion Graphics sperimentale: usa scena libera senza video di sfondo o raccolta sfondi. La modalità classica conserva queste opzioni.')
        media.extend(m for s in sprites for m in s.get('media',[]) if m['id'] not in {a['id'] for a in media})
        deck['infographic']['scene_format_version']=2
    if video:deck['infographic']['video']=video
    elif videos:deck['infographic']['videos']=videos
    def publish():
        artifact={'title':deck['title'],'content':encode(deck),'media':list(media)};meta['artifact']=artifact
        app.save_artifact(job['chat_id'],artifact['title'],artifact['content'],artifact['media']);app.store.update_answer(job,'Sto componendo l’infografica nel canvas.',meta=meta)
        return artifact
    publish()
    from .lab_image_model import select
    selected=select(app.engine,settings,opts.get('image_model'))
    generate_backgrounds=opts['images']=='generate' or (opts['animation_engine']=='classic' and opts['images']=='auto' and not assets and not videos and selected)
    new_characters=opts['character_animation']=='articulated' and bool(plan['characters'])
    if generate_backgrounds or new_characters:
        from .slide_generation_images import create
        image_settings=settings|{'_slides':{'image_model':selected,'format':opts['format'],'design':'playful' if opts['style'] in ('playful','comic') else 'professional'}}
        from .infographic_characters import additional_plan
        extras=additional_plan(plan) if opts['character_animation']=='articulated' else []
        image_settings['_motion_character_backgrounds']=opts['character_animation']=='articulated'
        generated,captions=create(app,job,{'title':plan['title'],'visual_direction':plan['visual_direction'],'slides':plan['scenes']},base,image_settings,model,cancel,lambda message:stage(message.replace('Slide ·','Infografica ·')),log,meta,restore_llm=False,additional_plan=extras,only_additional=not generate_backgrounds)
        descriptions.update(captions)
        media+=generated;publish()
    if opts['character_animation']=='articulated':
        from .infographic_characters import prepare as prepare_characters
        sprites,prepared=prepare_characters(app,job,plan,sprites,media,meta.get('slide_image_plan',[]),cancel,stage,log)
        media+=prepared;deck['infographic']['rigs']=[s for s in sprites if s.get('rig')];meta['motion_character_count']=len(deck['infographic']['rigs']);publish()
    voice_path=None;music_path=None;timings=None
    if opts['voice'] and opts['output']=='video':
        delivery=plan['delivery'] if opts['voice_style']=='auto' else opts['voice_style']
        from .infographic_voices import configure as voice_profile
        voice_settings,profile=voice_profile(app.root,settings,opts,delivery)
        meta['infographic_voice_profile']=profile
        parts=narration_parts(plan,opts['voice_gender'],voice_settings['voice_gender'])
        if profile!='configured':
            for part in parts:part['sentence_cues']=False
        result,voice_media=synthesize(app,folder/'voice',parts,voice_settings,'',cancel,stage,log,meta)
        timings=measured_scenes(result,plan);deck['infographic']['durations']=[t['duration'] for t in timings]
        if sum(deck['infographic']['durations'])>MAX_DURATION:raise ValueError('La narrazione supera dieci minuti: chiedi un testo più breve.')
        voice_path=folder/'voice/voce.wav';media+=voice_media
        deck['infographic']['voice_id']=voice_media[0]['id'];publish()
    if opts['music']=='uploaded':
        from .soundtrack import select
        item=select(payload['prompt'],payload['media'],history)
        if not item:raise ValueError('Allega una traccia audio oppure selezionala dalla galleria.')
        music_path=safe_join(app.data,item['path']);media.append(item)
        deck['infographic']['music_id']=item['id']
    elif opts['music'] in ('generate','jingle') and opts['output']=='video':
        music_model=app.engine.require_model(settings['music_model'],'music');app.engine.stop()
        composition={'title':plan['title']+' · '+('jingle' if opts['music']=='jingle' else 'musica'),'style':plan['music_style'],'lyrics':plan['jingle_lyrics'] if opts['music']=='jingle' else '[Instrumental]','abc':'','instrumental':opts['music']!='jingle'}
        if opts['music']=='jingle' and not composition['lyrics'].strip():raise ValueError('Il modello non ha preparato il testo del jingle.')
        item=app.engine.generate_music(music_model,settings|{'memory_policy':'on_demand'},composition,uuid4().hex,cancel,stage);media.append(item);music_path=safe_join(app.data,item['path']);app.engine.stop();publish()
        deck['infographic']['music_id']=item['id']
    app.engine.start_llama(model,settings,log,cancel,stage=stage)
    width,height=FORMATS[opts['format']]
    for index,page in enumerate(deck['pages']):
        if cancel.is_set():raise Cancelled()
        duration=deck['infographic']['durations'][index];deck['active']=index;page['status']='writing';publish()
        if opts['animation_engine']=='motion':
            from .infographic_storyboard import generate as generate_scene
            timing={'kind':'measured-scene' if voice_path else 'manual-duration','duration':duration,'word_alignment':False,'cues':timings[index]['cues'] if timings else []}
            page['timing']=timing
            try:
                sprite_trace={}
                def verify_scene(graph):
                    stage('Motion Graphics · verifica CPU dei testi e delle risorse')
                    check_deck=deck|{'pages':[page|{'status':'ready','html':'<main>Motion Graphics</main>','motion_scene':graph}], 'infographic':deck['infographic']|{'durations':[duration]}}
                    report=app.engine.tool_call('infographic-worker.py',{'mode':'motion-check','data':str(app.data),'deck':check_deck,'media':media,'voice':None,'music':None,'output':str(folder/'motion-check.mp4')},cancel,stage,log,timeout=120)
                    errors=[p['error'] for p in report['pages'] if p.get('error')]
                    if errors:raise ValueError('; '.join(errors))
                from .infographic_art import scene_request,requested_logo
                authored=scene_request(plan,index,meta.get('slide_image_plan',[]),requested_logo(payload['prompt'],payload['media'],len(plan['scenes'])))
                authored['pace_direction']=pace_brief(opts)
                sheets={p['asset_id'] for p in meta.get('slide_image_plan',[]) if p.get('role')=='character_parts'}|{m['id'] for s in sprites if s.get('rig') for m in s.get('media',[])}
                page['motion_scene']=generate_scene(app.engine,base,authored,width,height,duration,settings,cancel,stage,sprites,timing,[{'id':m['id'],'name':m['name'],'description':descriptions.get(m['id'],'Contenuto non analizzato')} for m in media if m.get('mime') in ('image/png','image/jpeg','image/webp') and m['id'] not in sheets],verify_scene,folder/f'motion-scene-{index+1}',sprite_trace)
                page['sprite_usage']=sprite_trace.get('sprites',[])
                page['html']='<main><p>Motion Graphics · scena strutturata</p></main>';page['sources']=[];page['status']='ready';publish()
            except Exception:page['status']='interrupted';publish();raise
            continue
        request=base+[{'role':'user','content':HTML_BRIEF+'\nCrea solo questa scena dell’infografica, in HTML/CSS libero. Opzioni: '+json.dumps(opts,ensure_ascii=False)+'\nDirezione artistica: '+plan['visual_direction']+'\nScaletta completa: '+json.dumps(plan['scenes'],ensure_ascii=False)+'\nSCENA '+str(index+1)+': '+json.dumps(plan['scenes'][index],ensure_ascii=False)+'\nViewport: '+str(width)+' x '+str(height)+' px. Durata: '+str(duration)+' secondi. Immagini autorizzate: '+image_catalog(media)+'\nFonti citabili: '+json.dumps(references,ensure_ascii=False)+'. Indica riferimenti reali con [R1], [D1], [W1] se pertinenti; non inventare citazioni.'+
          '\nNon usare CSS animation o transition, né JavaScript. Per ogni elemento da animare assegna data-motion="fade|slide|zoom|pan|blur|wipe|strobe|typewriter|appear|bump|drop|wave|flip", data-start="secondi", data-duration="secondi", data-out="secondi opzionali per uscita", data-ease="smooth|linear|snap". start e duration restano entro la durata della scena; data-out è l’inizio della dissolvenza finale. I valori temporali sono numeri decimali. Il motore applica i movimenti a questi elementi senza cambiare il layout. Distribuisci gli ingressi durante la narrazione, non tutti al secondo zero. Per typewriter usa un singolo titolo o una riga. Usa zoom/pan sulle immagini, fade/slide/blur sui testi, strobe solo se richiesto. Mantieni testo leggibile e gerarchia tipografica forte. Grafici e numeri devono essere HTML/SVG precisi. Non ripetere lo stesso layout per tutte le scene.'+video_brief+screen.brief(opts,duration)+typography.brief(opts)}]
        last=[0]
        def writing(value):
            import time
            if time.monotonic()-last[0]>.8:page['html']=value[-80000:];publish();last[0]=time.monotonic()
        planned=[{'id':p['asset_id'],'description':p.get('description','')} for p in meta.get('slide_image_plan',[]) if p.get('slide')==index+1 and p.get('asset_id')]
        request[-1]['content']+=layout_brief(opts['format'])+cinema_brief(opts)
        if opts.get('visual_mode')=='sequence' and planned:
            request[-1]['content']+='\nIMMAGINI ASSEGNATE A QUESTA SCENA (da usare realmente, non ridisegnare come fondali SVG): '+json.dumps(planned,ensure_ascii=False)
        request[-1]['content']+=background_brief(deck,page,media)
        stage(f'Infografica · composizione HTML {index+1}/{len(deck["pages"])}')
        try:
            html=generate_html(app.engine,request,settings|{'think_level':'off'},cancel,writing,stage,f'Infografica · scena {index+1}')
            html,warning=ensure_layout(app,job,deck,index,media,request,settings|{'think_level':'off'},cancel,html,writing,stage,log)
            if warning:page['layout_warning']=warning
            html=screen.ensure_panels(app.engine,request,settings|{'think_level':'off'},cancel,html,opts,writing)
            if opts['output']=='video':
                html=ensure_animation(app.engine,request,settings|{'think_level':'off'},cancel,html,duration,writing,stage)
                if not screen.valid_panels(html,opts):raise ValueError('La correzione dell’animazione ha perso i riquadri: rigenera la scena.')
            from .infographic_cinema import ensure as ensure_cinema
            html=ensure_cinema(app.engine,request,settings|{'think_level':'off'},cancel,html,opts,writing,stage,planned=planned)
            if not screen.valid_panels(html,opts):raise ValueError('La composizione ha perso i pannelli richiesti: rigenera la scena.')
            page['html']=html;page['sources']=list(dict.fromkeys(k for k in re.findall(r'\[([RDWI]\d+)\]',html) if k in {r['id'] for r in references}));page['status']='ready';publish()
        except Exception:
            page['status']='interrupted';publish();raise
    validate_motion(deck);validate_content(encode(deck),media)
    (folder/'infografica.json').write_text(json.dumps(deck,ensure_ascii=False,indent=2),encoding='utf-8')
    media.append({'id':uuid4().hex,'name':'infografica.json','mime':'application/json','path':(folder/'infografica.json').relative_to(app.data).as_posix()})
    if opts['output']=='video':
        app.engine.stop();stage('Infografica · rendering e montaggio audio')
        from .video_clip_tools import render_options
        app.engine.tool_call('infographic-worker.py',{'data':str(app.data),'deck':deck,'media':media,'voice':str(voice_path) if voice_path else None,'music':str(music_path) if music_path else None,'output':str(folder/'infografica.mp4')}|render_options(deck),cancel,stage,log,timeout=render_timeout(sum(deck['infographic']['durations'])))
        from .video_clip_tools import signature,record_render
        record_render(folder/'infografica.mp4',deck)
        media.append({'id':uuid4().hex,'name':deck['title']+'.mp4','mime':'video/mp4','path':(folder/'infografica.mp4').relative_to(app.data).as_posix(),
            'generation':{'infographic_signature':signature(deck)}})
    meta['infographic']=deck['infographic'];return publish()

def enqueue_render(app,chat_id,body):
    artifact=app.store.canvas_history.get(chat_id,body.get('artifact_id'))
    content=artifact['content'];media=artifact['media'];validate_content(content,media)
    if not content.startswith('```h3-slides\n'):raise ValueError('Seleziona prima un’infografica nel canvas.')
    deck=json.loads(content[len('```h3-slides\n'):-4])
    if not deck.get('infographic') or any(p.get('status')!='ready' for p in deck['pages']):raise ValueError('Completa prima l’infografica.')
    settings=app.store.settings()|{'_infographic_render':{'deck':deck,'media':media}}
    ident=app.store.enqueue(chat_id,'Esporta l’infografica modificata in MP4.',[],settings,True,[]);app.wake.set()
    return {'job_id':ident,'canvas':True}

def render_saved(app,job,settings,cancel,stage,log,meta):
    saved=settings['_infographic_render'];deck=saved['deck'];media=list(saved['media']);folder=app.data/'outputs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
    paths={m['id']:m for m in media};motion=deck['infographic']
    def audio_path(key):
        item=paths.get(motion.get(key))
        return str(safe_join(app.data,item['path'])) if item and item['mime'].startswith('audio/') else None
    app.engine.stop();stage('Infografica · rendering delle modifiche')
    from .video_clip_tools import render_options
    app.engine.tool_call('infographic-worker.py',{'data':str(app.data),'deck':deck,'media':media,'voice':audio_path('voice_id'),'music':audio_path('music_id'),'output':str(folder/'infografica.mp4')}|render_options(deck),cancel,stage,log,timeout=render_timeout(sum(motion['durations'])))
    source_ids={v['asset_id'] for v in motion.get('videos',[])}|{motion.get('video',{}).get('asset_id')}
    from .video_clip_tools import signature,record_render
    record_render(folder/'infografica.mp4',deck)
    media=[m for m in media if not m['mime'].startswith('video/') or m['id'] in source_ids]+[{'id':uuid4().hex,'name':deck['title']+'.mp4','mime':'video/mp4','path':(folder/'infografica.mp4').relative_to(app.data).as_posix(),
        'generation':{'infographic_signature':signature(deck)}}]
    artifact={'title':deck['title'],'content':encode(deck),'media':media};meta['artifact']=artifact;meta['infographic']=motion
    app.save_artifact(job['chat_id'],artifact['title'],artifact['content'],media);return artifact
