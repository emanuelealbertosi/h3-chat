"""Plan every illustration once, then keep one image model warm for the batch."""
import json
import time
from uuid import uuid4
from .downloads import Cancelled
from .image_options import options as image_options, configured, ASPECTS
from .visual_routing import assistant_format
from .loras import for_model as loras_for_model
from .slide_style import brief as style_brief,image_prompt
from .slide_colors import brief as color_brief
from .remote_llm import EmptyCompletion,StructuredCompletionError


def plan_images(engine,outline,history,settings,image_model,cancel,stage):
    """Plan bounded groups before switching to the single image generation batch."""
    opts=settings['_slides'];count=len(outline['slides']);form=assistant_format(image_model)
    style='tag descrittivi in inglese separati da virgole, nessuna frase narrativa' if form=='tags' else 'istruzioni visive precise in inglese, in linguaggio naturale'
    limit=min(settings['context']//2,settings['prompt_max_tokens'])
    # Editorial descriptions also consume context; use smaller groups while
    # preserving the existing short-outline budget for legacy callers.
    size=max(1,min(count,limit//(1000 if any('editorial' in row for row in outline['slides']) else 320)));plan=[]
    common='Prepara le immagini della presentazione. Massimo una per slide. Se l’utente chiede una immagine per ogni slide, pianificale per tutte; altrimenti ometti quelle dove non aiutano.\n'+\
        'Scaletta completa: '+json.dumps({k:v for k,v in outline.items() if k!='slides'}|{'slides':[{k:row[k] for k in ('title','purpose')} for row in outline['slides']]},ensure_ascii=False)+'\nStile: '+opts.get('design','professional')+'\n'+\
        style_brief(opts.get('design','professional'))+(color_brief(opts) if opts.get('engine','llm')=='llm' else '')+'\n'+\
        'Scegli aspect per il riquadro previsto: 16:9 o 3:2 per immagini ampie, 3:4 o 2:3 per un pannello laterale verticale, 4:3 per una figura orizzontale. Usa 1:1 solo quando il layout richiede davvero un quadrato. Pianifica insieme formato e proposta grafica della pagina; rispetta eventuali proporzioni delle immagini richieste esplicitamente dall’utente. Componi il soggetto con margini utili a un lieve ritaglio, senza scritte.\n'+\
        'Il campo prompt deve contenere '+style+'. description è una breve descrizione italiana dell’illustrazione.\n'+\
        'Ogni prompt deve essere autosufficiente: traduci in inglese lo stile visivo e la direzione artistica della scaletta, includendo palette, trattamento e composizione coerenti. Il motore immagini non vede questa conversazione: non scrivere soltanto «come le slide» o un soggetto senza stile. Mantieni una stessa famiglia visiva per tutte le illustrazioni, variando soggetti e composizione.\n'+\
        'Genera soltanto illustrazioni, scene o metafore pertinenti, MAI slide o infografiche con scritte. Nessun testo, neppure grande: vietati titoli, sottotitoli, parole, lettere, numeri, etichette, formule, citazioni, loghi e watermark dentro immagini. Mantieni cartelli e schermi vuoti. Tutte le scritte saranno HTML/SVG precisi separati. Non attribuire valore documentale alle illustrazioni generate.'
    if settings.get('_motion_character_backgrounds'):common+='\nQueste immagini sono SOLO SCENARI e oggetti: escludi tutti i personaggi, persone, figure, volti e parti del corpo. I personaggi articolati saranno inseriti separatamente dal motore; non creare duplicati statici nelle immagini di fondo.'
    common+='\nLa tecnica delle immagini richiesta esplicitamente nel prompt prevale sul trattamento illustrativo generico: per fotografie o immagini fotorealistiche non aggiungere painterly, painting, canvas texture, cartoon o illustration. Il divieto di scritte non impone un mezzo pittorico. Se sono ricostruzioni storiche AI, mantieni la dichiarazione di ricostruzione nei testi HTML, senza presentarle come fotografie documentali.'
    reusable=settings.get('_slide_reusable_images',[])
    if reusable:
        common+='\nRIUSO AUTORIZZATO: '+json.dumps([{'asset_id':x['media']['id'],**{k:x[k] for k in ('description','aspect','width','height')}} for x in reusable],ensure_ascii=False)+'\nL’utente ha scelto di riutilizzare le immagini: preferisci una figura già disponibile quando è adatta, senza rigenerarla inutilmente. Per ogni illustrazione scegli reuse_asset_id dal catalogo SOLO se soggetto, stile e proporzioni sono appropriati alla nuova scaletta e alle istruzioni attuali. Puoi riassegnare una figura a una pagina diversa. Se serve una figura nuova, uno stile diverso o il prompt chiede di rifarla, usa reuse_asset_id vuoto e prepara il nuovo prompt. Non riutilizzare soltanto perché il numero di slide coincide. Non inventare ID.'
    def produce(numbers):
        schema={'type':'object','properties':{'images':{'type':'array','minItems':0,'maxItems':len(numbers),
            'items':{'type':'object','properties':{'slide':{'type':'integer','enum':numbers},
                 'prompt':{'type':'string'},'description':{'type':'string'},'aspect':{'type':'string','enum':list(ASPECTS[1:])}},'required':['slide','prompt','description','aspect'],'additionalProperties':False}}},
            'required':['images'],'additionalProperties':False}
        if reusable:
            schema['properties']['images']['items']['properties']['reuse_asset_id']={'type':'string','enum':['']+[x['media']['id'] for x in reusable]}
            schema['properties']['images']['items']['required'].append('reuse_asset_id')
        tuning=settings|{'think_level':'off','temperature':.3,'max_tokens':min(limit,max(1024,len(numbers)*240))}
        label=f'Slide · piano illustrazioni · pagine {numbers[0]}–{numbers[-1]}/{count} · '+image_model['name'];last=0
        def progress(text):
            nonlocal last
            if text and time.monotonic()-last>.8:
                stage(label+f' · {len(text)} caratteri ricevuti');last=time.monotonic()
        for attempt in range(2 if len(numbers)==1 else 1):
            if cancel.is_set():raise Cancelled()
            stage(label+(' · nuovo tentativo conciso' if attempt else ''))
            instruction=common+'\nRestituisci SOLO JSON images per queste pagine: '+json.dumps(numbers)+'. Usa i numeri globali della scaletta, senza rinumerarli. Gli altri gruppi verranno pianificati separatamente, prima di generare tutte le immagini insieme. Non omettere una pagina per risparmiare token se è richiesta una immagine per ogni pagina.\n'+\
                f'Budget di output: {tuning["max_tokens"]} token. Prompt concisi: circa {max(20,min(100,tuning["max_tokens"]//(4*len(numbers))))} parole per immagine, descrizioni di una frase. Nessun commento o campo extra.'
            instruction+='\nContenuti e proposta grafica delle sole pagine di questo gruppo:\n'+json.dumps([
                {'slide':n,**{k:v[:1200] for k,v in outline['slides'][n-1].get('editorial',{}).items() if k in ('content','visual_plan')}} for n in numbers],ensure_ascii=False)
            if attempt:instruction+=' Il risultato precedente era incompleto: restituisci subito un JSON completo e più conciso.'
            try:
                raw,finish=engine.completion(history+[{'role':'user','content':instruction}],tuning,cancel,on_text=progress,schema=schema)
                if finish=='length':raise StructuredCompletionError('Output limit reached')
                try:value=json.loads(raw)
                except (ValueError,TypeError) as exc:raise StructuredCompletionError('Incomplete image plan JSON') from exc
            except (EmptyCompletion,StructuredCompletionError) as exc:
                if len(numbers)>1:
                    stage('Slide · piano immagini incompleto · divido il gruppo di pagine')
                    middle=len(numbers)//2;produce(numbers[:middle]);produce(numbers[middle:]);return
                if not attempt:continue
                raise ValueError(f'Piano immagini incompleto per la pagina {numbers[0]} dopo due tentativi (limite {tuning["max_tokens"]} token): aumenta i token Assistant immagini o il contesto LLM.') from exc
            items=value.get('images') if isinstance(value,dict) and set(value)=={'images'} else None;seen=set()
            if not isinstance(items,list) or len(items)>len(numbers):raise ValueError('Piano immagini non valido.')
            for item in items:
                if not isinstance(item,dict) or type(item.get('slide')) is not int or item['slide'] not in numbers or item['slide'] in seen:
                    raise ValueError('Il piano immagini contiene una slide non valida o ripetuta.')
                for key,max_size in (('prompt',4000),('description',800)):
                    if not isinstance(item.get(key),str) or not item[key].strip() or len(item[key])>max_size:raise ValueError('Descrizione immagine non valida.')
                item.setdefault('aspect','3:4' if opts.get('format')=='9:16' else '4:3')
                if item['aspect'] not in ASPECTS[1:]:raise ValueError('Formato dell’illustrazione slide non valido.')
                if item.get('reuse_asset_id') and item['reuse_asset_id'] not in {x['media']['id'] for x in reusable}:raise ValueError('Immagine da riusare non autorizzata.')
                item['prompt']=image_prompt(item['prompt'],opts.get('design','professional'),form);seen.add(item['slide'])
            plan.extend(items);return
    for start in range(1,count+1,size):produce(list(range(start,min(count+1,start+size))))
    if not plan:raise ValueError('Piano immagini non valido: nessuna illustrazione pianificata.')
    return plan


def create(app,job,outline,history,settings,model,cancel,stage,log_path,meta,*,restore_llm=True,additional_plan=(),only_additional=False):
    from .lab_image_model import select
    opts=settings['_slides'];selected=select(app.engine,settings,opts.get('image_model'))
    reusable=[]
    if opts.get('reuse_images_from'):
        from .slide_image_reuse import resolve
        reusable=resolve(app,job['chat_id'],opts['reuse_images_from'])
    image_model=app.engine.require_model(selected,'create')
    plan=[] if only_additional else plan_images(app.engine,outline,history,settings|{'_slide_reusable_images':reusable} if reusable else settings,image_model,cancel,stage)
    plan+=copy_plans(additional_plan)
    meta['slide_image_plan']=plan
    cache={x['media']['id']:dict(x) for x in reusable}
    meta['slide_image_cache']=list(cache.values())[-100:]
    tuning=settings|{'memory_policy':'on_demand','ram_cache_gb':0,'_image_model':image_model['id'],
                      '_loras':[] if image_model.get('remote_media') else loras_for_model(json.loads(job['payload']).get('loras',[]),image_model)}
    # Make the local batch exclusive before allocating any image weights,
    # even with a resident policy or other previously warmed model processes.
    if cancel.is_set():raise Cancelled()
    pool={x['media']['id']:x for x in reusable}
    # Recheck availability after planning; a file removed meanwhile is regenerated.
    from .downloads import safe_join
    for item in plan:
        previous=pool.get(item.get('reuse_asset_id'))
        if previous and not safe_join(app.data,previous['media']['path']).is_file():item.pop('reuse_asset_id',None)
    needs_generation=any(not pool.get(item.get('reuse_asset_id')) for item in plan)
    if needs_generation and not image_model.get('remote_media'):
        stage('Slide · rilascio completo dei motori locali prima del batch immagini')
        app.engine.stop()
    started=time.monotonic();assets=[]
    for index,item in enumerate(plan):
        if cancel.is_set():raise Cancelled()
        previous=pool.get(item.get('reuse_asset_id'))
        if previous:
            image=dict(previous['media']);item.update(asset_id=image['id'],width=previous['width'],height=previous['height'],aspect=previous['aspect'],reused=True)
            if image['id'] not in {m['id'] for m in assets}:assets.append(image)
            stage(f'Slide · riuso immagine {index+1}/{len(plan)} · '+item['description'])
            meta['slide_generated_images']=assets[:]
            app.store.update_answer(job,'Sto riutilizzando le immagini pertinenti della presentazione.',meta=meta)
            continue
        label=f'Slide · immagini {index+1}/{len(plan)} · {image_model["name"]}'
        stage(label)
        saved=configured(image_model,settings)
        area=saved.get('megapixels',saved['width']*saved['height']/1_000_000)
        tuning['_image_options']=image_options(image_model,settings,f"Formato {item['aspect']} {area:g} MP")
        item.update(width=tuning['_image_options']['width'],height=tuning['_image_options']['height'])
        image=app.engine.generate(image_model,tuning,item['prompt'],[],uuid4().hex,cancel,lambda step:stage(label+' · '+step))
        image['name']=('Personaggio · parti animabili: ' if item.get('role')=='character_parts' else f"Slide {item['slide']} · illustrazione generata: ")+item['description']
        assets.append(image)
        item['asset_id']=image['id']
        if not item.get('role'):
            cache[image['id']]={'media':dict(image),'description':item['description'],'aspect':item['aspect'],'width':item['width'],'height':item['height']}
            meta['slide_image_cache']=list(cache.values())[-100:]
        meta['slide_generated_images']=assets
        app.store.update_answer(job,'Sto preparando le immagini della presentazione.',meta=meta)
    # The final composition receives text descriptions, without recaptioning generated images.
    if cancel.is_set():raise Cancelled()
    if needs_generation and not image_model.get('remote_media'):
        stage('Slide · rilascio motore immagini'+(' e ripristino LLM per la composizione' if restore_llm else ' per il prossimo passaggio'))
        app.engine.stop()
        if restore_llm:app.engine.start_llama(model,settings,log_path,cancel,stage=stage)
    meta.setdefault('slide_timing',{})['images_seconds']=round(time.monotonic()-started,2)
    meta['slide_image_model']=image_model['name']
    meta['slide_images_reused']=sum(bool(p.get('reused')) for p in plan)
    meta['slide_images_created']=sum(not p.get('reused') for p in plan)
    return assets,{item['asset_id']:f"Illustrazione generata per la slide {item['slide']}: "+item['description']+f". Formato {item['aspect']}, {item['width']}×{item['height']} px." for item in plan}


def copy_plans(plans):
    import copy
    if not isinstance(plans,(list,tuple)) or len(plans)>2:raise ValueError('Piano personaggi: al massimo due nuovi fogli parti per generazione.')
    for p in plans:
        if not isinstance(p,dict) or p.get('role')!='character_parts' or p.get('slide')!=0 or p.get('aspect')!='2:3' or not isinstance(p.get('prompt'),str) or not 1<=len(p['prompt'])<=6000:raise ValueError('Piano foglio parti non valido.')
    return copy.deepcopy(list(plans))
