"""Plan every illustration once, then keep one image model warm for the batch."""
import json
import time
from uuid import uuid4
from .downloads import Cancelled
from .image_options import options as image_options
from .visual_routing import assistant_format
from .loras import for_model as loras_for_model


def create(app,job,outline,history,settings,model,cancel,stage,log_path,meta):
    opts=settings['_slides'];selected=opts.get('image_model') or settings.get('create_model')
    image_model=app.engine.require_model(selected,'create')
    form=assistant_format(image_model)
    style='tag descrittivi in inglese separati da virgole, nessuna frase narrativa' if form=='tags' else 'istruzioni visive precise in inglese, in linguaggio naturale'
    schema={'type':'object','properties':{'images':{'type':'array','minItems':1,'maxItems':len(outline['slides']),
        'items':{'type':'object','properties':{'slide':{'type':'integer','minimum':1,'maximum':len(outline['slides'])},
             'prompt':{'type':'string'},'description':{'type':'string'}},'required':['slide','prompt','description'],'additionalProperties':False}}},
        'required':['images'],'additionalProperties':False}
    request=history+[{'role':'user','content':'Prepara in UNA risposta tutte le immagini della presentazione. Massimo una per slide; ometti quelle dove non aiutano.\n'+
        'Scaletta: '+json.dumps(outline,ensure_ascii=False)+'\nStile: '+opts.get('design','professional')+'\n'+
        'Il campo prompt deve contenere '+style+'. description è una breve descrizione italiana dell’illustrazione.\n'+
        'Genera illustrazioni, scene o metafore pertinenti. Nessun testo piccolo, grafico numerico, formula o citazione dentro immagini: questi saranno HTML/SVG precisi. Non attribuire valore documentale alle illustrazioni generate.'}]
    planning=settings|{'think_level':'off','temperature':.3,'max_tokens':min(settings['context']//2,settings['prompt_max_tokens'],max(1024,len(outline['slides'])*240))}
    label='Slide · piano unico delle illustrazioni · '+image_model['name'];last=0
    stage(label)
    def progress(text):
        nonlocal last
        if text and time.monotonic()-last>.8:
            stage(label+f' · {len(text)} caratteri ricevuti');last=time.monotonic()
    # Completion returns (text, finish_reason) only when a stream callback is supplied.
    # Streaming also preserves the planned token budget instead of the router's 768-token cap.
    raw,finish=app.engine.completion(request,planning,cancel,on_text=progress,schema=schema)
    if finish=='length':raise ValueError('Piano immagini incompleto: aumenta i token Assistant immagini o il contesto LLM.')
    plan=json.loads(raw).get('images');seen=set()
    if not isinstance(plan,list) or not 1<=len(plan)<=len(outline['slides']):raise ValueError('Piano immagini non valido.')
    for item in plan:
        if not isinstance(item,dict) or type(item.get('slide')) is not int or not 1<=item['slide']<=len(outline['slides']) or item['slide'] in seen:
            raise ValueError('Il piano immagini contiene una slide non valida o ripetuta.')
        for key,limit in (('prompt',4000),('description',800)):
            if not isinstance(item.get(key),str) or not item[key].strip() or len(item[key])>limit:raise ValueError('Descrizione immagine non valida.')
        seen.add(item['slide'])
    meta['slide_image_plan']=plan
    tuning=settings|{'memory_policy':'on_demand','ram_cache_gb':0,'_image_model':image_model['id'],
                      '_loras':[] if image_model.get('remote_media') else loras_for_model(json.loads(job['payload']).get('loras',[]),image_model)}
    # Switching once here releases the LLM even when the normal chat policy is resident.
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
    app.engine.stop();app.engine.start_llama(model,settings,log_path,cancel,stage=stage)
    meta.setdefault('slide_timing',{})['images_seconds']=round(time.monotonic()-started,2)
    meta['slide_image_model']=image_model['name']
    return assets,{item['asset_id']:f"Illustrazione generata per la slide {item['slide']}: "+item['description'] for item in plan}
