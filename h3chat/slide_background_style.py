"""Validated slide background choices and stable, workspace-owned asset assignments."""
import math
import re

ID=re.compile('[a-f0-9]{32}')


def options(value):
    if value is None:return None
    if not isinstance(value,dict) or set(value)-{'base','decorations','set_id','asset_ids','opacity','veil'}:raise ValueError('Impostazioni dello sfondo slide non valide.')
    result={'base':'plain','decorations':False,'set_id':'','asset_ids':[],'opacity':20,'veil':'auto'}|value
    if result['base'] not in ('plain','gradient','collection') or type(result['decorations']) is not bool:raise ValueError('Scegli Plain, Gradient o Raccolta e le decorazioni desiderate.')
    if result['veil'] not in ('auto','light','dark'):raise ValueError('Velatura slide non valida.')
    if type(result['opacity']) is not int or not 5<=result['opacity']<=45:raise ValueError('Intensità sfondo: scegli da 5 a 45%.')
    ids=result['asset_ids']
    if not isinstance(result['set_id'],str) or not isinstance(ids,list) or len(ids)>24 or any(not isinstance(i,str) or not ID.fullmatch(i) for i in ids) or len(set(ids))!=len(ids):raise ValueError('Selezione degli sfondi non valida.')
    if result['base']=='collection':
        if not ID.fullmatch(result['set_id']) or not ids:raise ValueError('Scegli un batch dalla raccolta e almeno uno sfondo.')
    else:result.update(set_id='',asset_ids=[])
    return result


def resolve(app,style,existing=()):
    style=options(style)
    if not style or style['base']!='collection':return []
    from .slide_backgrounds import listing
    collection=next((s for s in listing(app)['items'] if s['id']==style['set_id']),None)
    available={item['media']['id']:item['media'] for item in collection['images']} if collection else {}
    # Existing decks retain their own authorized assets even if their library
    # recipe has gone away. New sends never accept client paths or foreign sets.
    available.update({m['id']:m for m in existing if m.get('slide_background') and m['id'] in style['asset_ids']})
    if any(ident not in available for ident in style['asset_ids']):raise ValueError('Uno degli sfondi selezionati non è più disponibile. Riapri la raccolta: nessuna sostituzione automatica.')
    media=[available[ident] for ident in style['asset_ids']]
    app.validate_media([{'id':m['id']} for m in media],canvas=True)
    return media


def validate_deck(deck,media):
    style=options(deck.get('background_style'))
    if not style:return
    if deck.get('infographic',{}).get('video'):raise ValueError('Scegli uno sfondo statico oppure un video di sfondo.')
    available={m['id'] for m in media if m.get('mime','').startswith('image/')}
    if style['base']=='collection' and not set(style['asset_ids'])<=available:raise ValueError('Manca uno sfondo negli allegati della presentazione.')
    for page in deck['pages']:
        if style['base']=='collection' and page.get('background_asset_id') not in style['asset_ids']:raise ValueError('Assegnazione dello sfondo slide non valida.')


def assign(deck,style,media):
    style=options(style)
    if not style:return
    deck['background_style']=style
    if style['base']=='collection':
        for index,page in enumerate(deck['pages']):page['background_asset_id']=style['asset_ids'][index%len(style['asset_ids'])]
    validate_deck(deck,media)


def geometry(deck,page,media):
    from .slides import FORMATS
    width,height=FORMATS[deck['format']];style=options(deck.get('background_style'))
    result={'x':0,'y':0,'width':width,'height':height}
    if not style or style['base']!='collection':return result
    asset=next((m for m in media if m['id']==page.get('background_asset_id')),None)
    if not asset:raise ValueError('Sfondo della slide non disponibile.')
    meta=asset.get('slide_background',{})
    if meta.get('kind')!='frame':return result
    ratio=str(meta.get('format',deck['format'])).split(':')
    try:a,b=map(float,ratio);fraction=float(meta.get('margin',12))/100
    except (ValueError,TypeError):raise ValueError('Margini della cornice non validi.') from None
    if not all(math.isfinite(n) and n>0 for n in (a,b)) or not .05<=fraction<=.25:raise ValueError('Margini della cornice non validi.')
    fit=min(width/a,height/b);w=a*fit;h=b*fit
    return {'x':(width-w)/2+w*fraction,'y':(height-h)/2+h*fraction,'width':w*(1-2*fraction),'height':h*(1-2*fraction)}


def brief(deck,page,media):
    style=options(deck.get('background_style'))
    if not style:return ''
    box=geometry(deck,page,media)
    text=f'\nSFONDO GESTITO DALL’APP: {style["base"]}. '
    text+='Lo sfondo e le eventuali decorazioni sono già composti dall’app: non disegnarli e non inserire le immagini decorative come figure o prove documentali. '
    text+='Crea solo il contenuto su fondo trasparente, senza un altro pannello opaco a tutta pagina. Le superfici locali di card, grafici e callout restano consentite. '
    text+=f'Area di composizione effettiva {box["width"]:.0f}×{box["height"]:.0f} px; l’app la posiziona entro la cornice. Usa main/section responsive al 100% di questa area, non 100vw/100vh o posizioni fixed. Non ridurre i caratteri per far entrare testo eccessivo. '
    text+='Mantieni contrasto leggibile; le decorazioni non sostituiscono le figure informative.'
    return text
