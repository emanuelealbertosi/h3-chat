"""Agent adapters for the same background library and composition used by Slide UI."""
import copy
import json
import time


def definitions():
    from .agent_tools import obj,string,ID
    from .slide_style import IMAGE_CUES
    style=obj({'base':{'type':'string','enum':['auto','plain','gradient','collection']},
        'decorations':{'type':'boolean'},'set_id':ID,'asset_ids':{'type':'array','items':ID,'maxItems':24},
        'opacity':{'type':'integer','minimum':5,'maximum':45},'veil':{'type':'string','enum':['auto','light','dark']}})
    return {
      'list_slide_backgrounds':('Elenca i set di sfondi e le immagini disponibili, con tipo e formato. Usa questi ID in background_style di create_slides.',obj({})),
      'create_slide_backgrounds':('Crea veri sfondi o cornici nella raccolta H3, con centro libero e margini riservati. Richiede il permesso immagini. Restituisce background_style da passare a create_slides; non genera slide.',obj({
          'name':string(100),'prompt':string(4000),'count':{'type':'integer','minimum':1,'maximum':24},
          'format':{'type':'string','enum':['16:9','9:16','4:3','1:1']},'model_id':string(150),
          'kind':{'type':'string','enum':['frame','soft']},'margin':{'type':'integer','minimum':5,'maximum':25},
          'palette':{'type':'string','enum':['pastel','natural','blue','warm','mono']},
          'design':{'type':'string','enum':list(IMAGE_CUES),'description':'Direzione artistica: professional, playful o comic. Conserva stile, tema e tecnica espliciti della richiesta nel prompt.'},
          'tone':{'type':'string','enum':['light','dark']}},['name','prompt','count'])),
      'apply_slide_background':('Applica alla presentazione uno sfondo della raccolta o una immagine già salvata nella stessa chat. Le cornici riservano un margine interno; non rigenera immagini né contenuti. Usa poi inspect_slides per misurare il nuovo spazio.',obj({
          'artifact_id':ID,'background_style':style,'image_artifact_id':ID,
          'image_number':{'type':'integer','minimum':1,'maximum':50},
          'kind':{'type':'string','enum':['frame','soft']},'margin':{'type':'integer','minimum':5,'maximum':25}},['artifact_id']))}


def execute(ctx,name,args):
    from . import slide_backgrounds as library
    from . import slide_background_style as composition
    from .agent_tools import artifact,deck_of
    if name=='list_slide_backgrounds':
        return {'sets':[{'id':v['id'],'name':v['name'],'options':v['options'],
            'images':[{'id':i['media']['id'],'name':i['media']['name']} for i in v['images']]}
            for v in library.listing(ctx.app)['items']]}
    if name=='create_slide_backgrounds':
        from .lab_image_model import select
        from .execution_mode import guard_intent
        local=ctx.tool_settings();guard_intent(ctx.app.effective_settings(local),'create')
        ident=select(ctx.app.engine,local,args.get('model_id',''))
        model=ctx.app.engine.require_model(ident,'create')
        from .slide_style import explicit_design
        saved=ctx.settings.get('_agent',{}).get('slide_defaults',{})
        design=explicit_design(ctx.state['request']) or args.get('design') or saved.get('design','professional')
        config=library.options({'name':args['name'],'variants':args['count'],'model':ident,
            'format':args.get('format','16:9'),'kind':args.get('kind','frame'),
            'margin':args.get('margin',12),'palettes':[args.get('palette','blue')],'tone':args.get('tone','light'),'design':design})
        request={'options':config,'tasks':library.plan(config,args['prompt'],model,local),'prompt':args['prompt']}
        meta=ctx.tool_meta()
        library.render(ctx.tool_app,ctx.tool_job(),ctx.tool_payload,local|{'_slide_backgrounds':request},ctx.cancel,ctx.stage,meta)
        value=meta['artifact'];style={'base':'collection','set_id':ctx.action['id'],
            'asset_ids':[m['id'] for m in value['media']]}
        return ctx.artifact_result(value)|{'background_style':composition.options(style),'art_direction':{'design':design,'prompt':args['prompt']}}
    value=copy.deepcopy(artifact(ctx.app,ctx.job['chat_id'],args['artifact_id']));deck=deck_of(value)
    if bool(args.get('image_artifact_id'))==bool(args.get('background_style')):
        raise ValueError('Scegli background_style oppure image_artifact_id, una sola sorgente sfondo.')
    if args.get('image_artifact_id'):
        source=artifact(ctx.app,ctx.job['chat_id'],args['image_artifact_id']);number=args.get('image_number',1)
        if number>len(source['media']) or not source['media'][number-1]['mime'].startswith('image/'):
            raise ValueError('Scegli un’immagine dell’artefatto della stessa chat.')
        image=copy.deepcopy(source['media'][number-1])
        image['slide_background']={'kind':args.get('kind','frame'),'format':deck['format'],
            'margin':args.get('margin',12),'opacity':20,'tone':'light'}
        # Retain the actual file ratio, including older square frames; never stretch it.
        generation=image.get('generation',{})
        if generation.get('width') and generation.get('height'):
            image['slide_background']['format']=f"{generation['width']}:{generation['height']}"
        collection={'id':ctx.action['id'],'name':'Sfondo · '+source['title'][:80],'created':time.time(),
            'chat_id':ctx.job['chat_id'],'status':'done','options':image['slide_background'],
            'images':[{'media':image}],'total':1}
        library.save(ctx.app,collection)
        style=composition.options({'base':'collection','set_id':collection['id'],'asset_ids':[image['id']]})
    else:style=composition.options(args['background_style'])
    backgrounds=composition.resolve(ctx.app,style)
    ids={m['id'] for m in backgrounds}
    value['media']=[m for m in value['media'] if m['id'] not in ids]+backgrounds
    if style:composition.assign(deck,style,value['media'])
    else:
        deck.pop('background_style',None)
        for page in deck['pages']:page.pop('background_asset_id',None)
    from .slides import PREFIX
    value['content']=PREFIX+json.dumps(deck,ensure_ascii=False)+'\n```'
    ctx.tool_app.save_artifact(ctx.job['chat_id'],value['title'],value['content'],value['media'])
    return ctx.artifact_result(value)|{'background_style':style,'layout_check_required':True}
