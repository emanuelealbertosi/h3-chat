"""Continue a saved long-video plan without running chat, vision or retrieval."""
import copy
import re
from .downloads import safe_join
from .loras import for_model, public
from .soundtrack import select, probe
from .video_resume import checkpoint


CONTEXT_KEYS = ('_video_soundtrack', '_video_duration', '_video_audio_start',
                '_video_audio_source_duration', '_video_segment_seconds',
                '_video_editing', '_video_aspect', '_video_loras')


def render(app, job, payload, settings, cancel, stage, log_path):
    saved = checkpoint(app.data, settings['_video_resume'])
    model = app.engine.require_model(saved.get('model') or settings['video_model'], 'video')
    context = saved.get('request_context') or payload.get('video_resume_context') or {}
    settings = copy.deepcopy(settings)
    settings.update({k:copy.deepcopy(v) for k,v in context.get('settings', {}).items() if k in CONTEXT_KEYS})
    refs = copy.deepcopy(context.get('references', payload.get('media', [])))
    # Legacy checkpoints predate stored runtime references. Resolve the same
    # original history snapshot, never newer prompts or generated answers.
    history = app.store.messages(job['chat_id'], payload['until'])
    if not refs and re.search(r'\b(questa|questo|allegat\w*|precedente|this|previous)\b', payload['prompt'], re.I):
        refs = next(([x for x in m['media'] if x['mime'].startswith(('image/', 'audio/'))]
                     for m in reversed(history[:-1]) if any(x['mime'].startswith(('image/', 'audio/')) for x in m['media'])), [])
    previous = history[:-1] if re.search(r'\b(?:precedente|previous|già generat\w*)\b', payload['prompt'], re.I) else ()
    soundtrack = settings.get('_video_soundtrack') or select(payload['prompt'], refs, previous)
    if not soundtrack:
        raise ValueError('La traccia originale del video da riprendere non è più disponibile. Le clip salvate sono conservate.')
    if not any(x['id'] == soundtrack['id'] for x in refs):refs.append(soundtrack)
    for item in refs:
        if not safe_join(app.data, item['path']).is_file():raise ValueError('Un riferimento originale non è più disponibile. Le clip salvate sono conservate.')
    chosen_loras = for_model(payload.get('loras', []), model)
    settings.update(video_model=model['id'], _video_duration=saved['timeline'][-1]['start']+saved['timeline'][-1]['duration'],
                    _video_audio_start=saved.get('audio_start', 0), _video_soundtrack=soundtrack)
    if '_video_loras' not in settings:
        settings['_video_loras'] = [{'path':x['path'], 'weight':x['weight']} for x in chosen_loras]
    if '_video_audio_source_duration' not in settings:
        settings['_video_audio_source_duration'] = probe(app.engine, app.data, soundtrack, cancel, stage, log_path)['duration']
    meta = {'intent':'video', 'canvas':bool(payload.get('canvas')), 'model':model['name'],
            'execution_mode':'Standalone · GPU · ripresa dalle clip mancanti', 'references':refs,
            'video_plan':saved['plan'], 'assistant_on':settings.get('_assistant', True),
            'loras':public(chosen_loras), 'video_recovery':{'source':settings['_video_resume'],
            'completed':saved['completed'], 'remaining':len(saved['timeline'])-saved['completed']}}
    stage(f'Recupero video · {saved["completed"]}/{len(saved["timeline"])} scene già salvate')
    app.store.update_answer(job, '', meta=meta)
    media = app.engine.generate_long_video(model, settings, saved['plan'], refs, job['id'], cancel, stage, prompt=payload['prompt'])
    meta['video_parameters'] = media['generation']
    if payload.get('canvas'):
        app.save_artifact(job['chat_id'], 'Video MiniMax H3', '', [media])
        meta['artifact'] = {'title':'Video MiniMax H3', 'content':'', 'media':[media]}
        app.store.update_answer(job, 'Ho completato il video nel canvas, conservando le clip già riuscite.', 'done', [], meta)
    else:app.store.update_answer(job, 'Ecco il video completato, con le clip già riuscite conservate.', 'done', [media], meta)
    app.store.execute("UPDATE jobs SET status='done',stage='Video recuperato' WHERE id=?", (job['id'],))
