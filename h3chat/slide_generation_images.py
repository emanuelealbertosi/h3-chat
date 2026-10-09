"""Plan every illustration once, then keep one image model warm for the batch."""
import json
import time
from uuid import uuid4
from .downloads import Cancelled
from .image_options import options as image_options
from .visual_routing import assistant_format
from .loras import for_model as loras_for_model
from .slide_style import brief as style_brief,image_prompt
from .remote_llm import EmptyCompletion,StructuredCompletionError


def plan_images(engine,outline,history,settings,image_model,cancel,stage):
    """Plan bounded groups before switching to the single image generation batch."""
    opts=settings['_slides'];count=len(outline['slides']);form=assistant_format(image_model)
    style='tag descrittivi in inglese separati da virgole, nessuna frase narrativa' if form=='tags' else 'istruzioni visive precise in inglese, in linguaggio naturale'
    limit=min(settings['context']//2,settings['prompt_max_tokens'])
    size=max(1,min(count,limit//320));plan=[]
    common='Prepara le immagini della presentazione. Massimo una per slide. Se l’utente chiede una immagine per ogni slide, pianificale per tutte; altrimenti ometti quelle dove non aiutano.\n'+\
        'Scaletta completa: '+json.dumps(outline,ensure_ascii=False)+'\nStile: '+opts.get('design','professional')+'\n'+\
        style_brief(opts.get('design','professional'))+'\n'+\
        'Il campo prompt deve contenere '+style+'. description è una breve descrizione italiana dell’illustrazione.\n'+\
        'Ogni prompt deve essere autosufficiente: traduci in inglese lo stile visivo e la direzione artistica della scaletta, includendo palette, trattamento e composizione coerenti. Il motore immagini non vede questa conversazione: non scrivere soltanto «come le slide» o un soggetto senza stile. Mantieni una stessa famiglia visiva per tutte le illustrazioni, variando soggetti e composizione.\n'+\
        'Genera illustrazioni, scene o metafore pertinenti. Nessun testo piccolo, grafico numerico, formula o citazione dentro immagini: questi saranno HTML/SVG precisi. Non attribuire valore documentale alle illustrazioni generate.'
    def produce(numbers):
        schema={'type':'object','properties':{'images':{'type':'array','minItems':0,'maxItems':len(numbers),
            'items':{'type':'object','properties':{'slide':{'type':'integer','enum':numbers},
                 'prompt':{'type':'string'},'description':{'type':'string'}},'required':['slide','prompt','description'],'additionalProperties':False}}},
            'required':['images'],'additionalProperties':False}
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
                item['prompt']=image_prompt(item['prompt'],opts.get('design','professional'),form);seen.add(item['slide'])
            plan.extend(items);return
    for start in range(1,count+1,size):produce(list(range(start,min(count+1,start+size))))
    if not plan:raise ValueError('Piano immagini non valido: nessuna illustrazione pianificata.')
    return plan


def create(app,job,outline,history,settings,model,cancel,stage,log_path,meta):
    opts=settings['_slides'];selected=opts.get('image_model') or settings.get('create_model')
    image_model=app.engine.require_model(selected,'create')
    plan=plan_images(app.engine,outline,history,settings,image_model,cancel,stage)
    meta['slide_image_plan']=plan
    tuning=settings|{'memory_policy':'on_demand','ram_cache_gb':0,'_image_model':image_model['id'],
                      '_loras':[] if image_model.get('remote_media') else loras_for_model(json.loads(job['payload']).get('loras',[]),image_model)}
    # Make the local batch exclusive before allocating any image weights,
    # even with a resident policy or other previously warmed model processes.
    if cancel.is_set():raise Cancelled()
    if not image_model.get('remote_media'):
        stage('Slide · rilascio completo dei motori locali prima del batch immagini')
        app.engine.stop()
    started=time.monotonic();assets=[]
    for index,item in enumerate(plan):
        if cancel.is_set():raise Cancelled()
        label=f'Slide · immagini {index+1}/{len(plan)} · {image_model["name"]}'
        stage(label)
        tuning['_image_options']=image_options(image_model,settings)
        image=app.engine.generate(image_model,tuning,item['prompt'],[],uuid4().hex,cancel,lambda step:stage(label+' · '+step))
        image['name']=f"Slide {item['slide']} · illustrazione generata: "+item['description']
        assets.append(image)
        item['asset_id']=image['id']
        meta['slide_generated_images']=assets
        app.store.update_answer(job,'Sto preparando le immagini della presentazione.',meta=meta)
    # The final composition receives text descriptions, without recaptioning generated images.
    if cancel.is_set():raise Cancelled()
    if not image_model.get('remote_media'):
        stage('Slide · rilascio motore immagini e ripristino LLM per la composizione')
        app.engine.stop();app.engine.start_llama(model,settings,log_path,cancel,stage=stage)
    meta.setdefault('slide_timing',{})['images_seconds']=round(time.monotonic()-started,2)
    meta['slide_image_model']=image_model['name']
    return assets,{item['asset_id']:f"Illustrazione generata per la slide {item['slide']}: "+item['description'] for item in plan}
