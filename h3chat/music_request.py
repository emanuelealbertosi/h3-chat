"""Capture the chosen music engine and its chat-local controls in the job."""
import copy
from .music_options import validate,options

def capture(app,settings,body,media):
    result=copy.deepcopy(settings)
    ident=body.get('music_model','')
    if not isinstance(ident,str) or len(ident)>150:raise ValueError('Modello musicale non valido.')
    if ident:
        model=app.engine.require_model(ident,'music')
        result['music_model']=ident;result['music_quality']='model'
    else:model=app.catalog.get(result['music_model'],{})
    parameters=body.get('music_parameters')
    if parameters is not None:
        if not result.get('_music') and not body.get('music'):raise ValueError('Attiva Music per impostare i parametri musicali.')
        if not model:raise ValueError('Scegli un modello musicale.')
        if model.get('architecture')=='minimax-music':
            from .minimax_music import validate as check
        else:check=validate
        check(parameters,partial=True)
        result.setdefault('music_overrides',{}).setdefault(model['id'],{}).update(parameters)
        result['_music_request_parameters']=dict(parameters)
    resing=body.get('music_resing',False)
    if type(resing) is not bool:raise ValueError('Scelta Re-sing non valida.')
    if resing:
        if not body.get('music'):raise ValueError('Attiva Music per usare Re-sing.')
        model=app.engine.require_model(result['music_model'],'music')
        if model.get('architecture')=='minimax-music' or model.get('remote_media'):raise ValueError('Re-sing sulla melodia originale richiede un modello YuE2 locale. Selezionalo nelle impostazioni Music.')
        if body.get('music_fields',{}).get('instrumental'):raise ValueError('Re-sing richiede un testo cantato: disattiva Strumentale.')
        from .remix_runtime import ready,settings as remix_settings
        runtime=remix_settings(app.root);status=ready(app.root,runtime)
        if not all(status[k] for k in ('media','separation','score')):raise ValueError('Re-sing: completa separazione e lettura spartiti in Setup → Remix audio.')
        audio=[m for m in media if m.get('mime','').startswith('audio/')]
        if len(audio)!=1 or len(media)!=1:raise ValueError('Re-sing richiede una sola canzone audio in allegato.')
        result['_music_resing']={'source':audio[0],'runtime':runtime}
    else:result['_music_resing']=None
    if model and body.get('music'):options(model,result,randomize=False)
    return result
