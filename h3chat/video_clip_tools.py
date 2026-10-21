"""Owned timeline intervals exported, decorated or replaced through the shared queue."""
import copy
import hashlib
import json
import math
from uuid import uuid4
from .downloads import safe_join, Cancelled
from .video_edit import source, clip_source, interval
from .video_resume import save
from . import video_versions


def target(app, chat_id, body):
    value = source(app, chat_id, body.get('source'), body.get('segment_seconds'))
    number = body.get('clip')
    if type(number) is not int or not 1 <= number <= len(value['record']['timeline']):
        raise ValueError('Seleziona una clip della timeline.')
    selected = video_versions.choices(app, chat_id, body['source'], value, body.get('versions'))
    video_versions.apply(value, selected, app.data)
    scene = value['record']['timeline'][number - 1]
    patch = {'clip': number}
    if 'start' in body or 'end' in body:
        if any(type(body.get(k)) not in (int, float) or not math.isfinite(body[k]) for k in ('start', 'end')):
            raise ValueError('Indica entrambi i tempi del tratto.')
        if not 0 <= body['start'] < body['end'] <= scene['duration'] + 1e-6:
            raise ValueError('Il tratto deve restare dentro la clip.')
        patch.update(start=body['start'], end=body['end'])
    first, last = interval(patch, scene)
    if not 0 <= first < last <= scene['frames']:
        raise ValueError('Il tratto deve restare dentro la clip.')
    command = {'source': body['source'], 'clip': number, 'start': first / 24, 'end': last / 24,
               'versions': value['record']['selected_versions'].copy()}
    if value['record'].get('import_segment_seconds'):
        command['segment_seconds'] = value['record']['import_segment_seconds']
    return value, command


def dimensions(value, index):
    params = value['record']['parameters'][index]
    shape = value.get('source_size') or params
    width, height = shape.get('width'), shape.get('height')
    if any(type(n) is not int or n < 2 for n in (width, height)):
        raise ValueError('Il formato originale della clip non è disponibile.')
    return width // 2 * 2, height // 2 * 2


def request(app, chat_id, body):
    action = body.get('action')
    if action not in ('export', 'replace', 'infographic'):
        raise ValueError('Operazione sullo spezzone non valida.')
    value, command = target(app, chat_id, body)
    settings = app.store.settings() | {'_assistant': False, '_rag': False, '_video_clip': command | {'action': action}}
    media = []
    prompt = f"{'Esporta' if action == 'export' else 'Sostituisci'} clip {command['clip']} · {command['start']:g}–{command['end']:g} s"
    canvas = False
    if action == 'replace':
        media = app.validate_media([{'id': body.get('media_id')}])
        if not media[0]['mime'].startswith('video/'):
            raise ValueError('La sostituzione deve essere un video dalla tua area.')
        settings['_video_clip']['media'] = media[0]
        label = body.get('label', 'Video importato')
        if not isinstance(label, str) or len(label) > 150:
            raise ValueError('Nome della versione non valido.')
        settings['_video_clip']['label'] = label
    elif action == 'infographic':
        from .infographics import options
        from .slides import FORMATS
        prompt = body.get('prompt', '')
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 24000:
            raise ValueError('Descrivi split screen, scritte ed effetti.')
        if command['end'] - command['start'] < .1:
            raise ValueError('Scegli almeno un decimo di secondo per l’infografica.')
        width, height = dimensions(value, command['clip'] - 1)
        fmt = min(FORMATS, key=lambda key: abs(math.log((FORMATS[key][0] / FORMATS[key][1]) / (width / height))))
        opts = options(value=body.get('infographic', {}))
        # "Title at 4 seconds" is an effect cue, not a new clip duration.
        from .infographic_screen import prompt_timing
        prompt_timing(prompt, opts)
        # Exact timeline clocks override the indicative duration of regular infographics.
        opts.update(format=fmt, duration=max(5, math.ceil(command['end'] - command['start'])),
                    scenes=1, voice=False, music='none', sfx='none', images='provided',
                    output='video', video_audio='keep', video_background='auto', video_end='freeze')
        app.engine.require_model(settings['chat_model'], 'chat')
        settings.pop('_video_clip')
        settings.update(_video_clip_infographic=command, _lab='infographic', _infographic=opts, _assistant=True, _rag=settings.get('rag_enabled',True))
        canvas = True
    ident = app.store.enqueue(chat_id, prompt.strip(), media, settings, canvas, [])
    app.wake.set()
    return {'job_id': ident, 'canvas': canvas, 'intent': 'infographic' if canvas else 'video'}


def extract(app, job, command, cancel, stage, log):
    value, command = target(app, job['chat_id'], command)
    index = command['clip'] - 1; first, last = interval(command, value['record']['timeline'][index])
    original = clip_source(value, index); width, height = dimensions(value, index)
    output = app.data / 'outputs' / job['id'] / 'spezzone.mp4'
    result = app.engine.tool_call('video-clip-worker.py', {'source': str(safe_join(app.data, original['path'])),
        'start': original['start'] + first / 24, 'output': str(output), 'frames': last - first, 'width': width, 'height': height,
        'audio': str(safe_join(app.data, value['audio']['path'])),
        'audio_start': value['record'].get('audio_start', 0) + value['record']['timeline'][index]['start'] + first / 24}, cancel, stage, log, timeout=1800)
    item = {'id': uuid4().hex, 'name': f"Clip {command['clip']} · spezzone.mp4", 'mime': 'video/mp4',
        'path': output.relative_to(app.data).as_posix(), 'generation': {'timeline_export': command, **{k: result[k] for k in ('duration', 'fps', 'width', 'height')}}}
    app.store.gallery.register([item], 'generated')
    return item, command


def prepare_infographic(app, job, settings, cancel, stage, log):
    item, command = extract(app, job, settings['_video_clip_infographic'], cancel, stage, log)
    settings['_infographic']['video_id'] = item['id']
    value, _ = target(app, job['chat_id'], command)
    settings['_video_clip_target'] = command | {'render_size': list(dimensions(value, command['clip'] - 1))}
    return item


def signature(deck):
    return hashlib.sha256(json.dumps(deck, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def record_render(output, deck):
    """Canvas media are canonicalized on save; keep the digest beside the owned MP4."""
    output.with_name('infographic-render.json').write_text(json.dumps({'file': output.name, 'signature': signature(deck)}), encoding='utf-8')


def render_options(deck):
    from .slides import FORMATS
    size = deck.get('infographic', {}).get('timeline_target', {}).get('render_size')
    if not isinstance(size, list) or len(size) != 2 or any(type(n) is not int or not 2 <= n <= 16384 or n % 2 for n in size):
        return {}
    viewport = FORMATS[deck['format']]
    if abs(size[0] / size[1] - viewport[0] / viewport[1]) > 1e-6:
        return {}
    return {'output_size': size, 'fps': 24}


def use_infographic(app, chat_id, body):
    from .slides import PREFIX, validate_content
    artifact = app.store.canvas_history.get(chat_id, body.get('artifact_id'))
    validate_content(artifact['content'], artifact['media'])
    if not artifact['content'].startswith(PREFIX):
        raise ValueError('Seleziona l’infografica collegata alla timeline.')
    deck = json.loads(artifact['content'][len(PREFIX):-4])
    motion = deck.get('infographic', {}); command = motion.get('timeline_target')
    if not isinstance(command, dict):
        raise ValueError('Questa infografica non è collegata a uno spezzone.')
    _, command = target(app, chat_id, command)
    if abs(sum(motion['durations']) - command['end'] + command['start']) > 1 / 48:
        raise ValueError('La durata dell’infografica deve coincidere con il tratto della timeline.')
    inputs = {v['asset_id'] for v in motion.get('videos', [])} | {motion.get('video', {}).get('asset_id')}
    movie = next((m for m in reversed(artifact['media']) if m['mime'].startswith('video/') and m['id'] not in inputs), None)
    rendered = {}
    if movie:
        canonical = app.validate_media([{'id': movie['id']}])[0]
        output = safe_join(app.data, canonical['path'])
        try:
            rendered = json.loads(output.with_name('infographic-render.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
    if not movie or rendered.get('file') != output.name or rendered.get('signature') != signature(deck):
        raise ValueError('Esporta / aggiorna MP4 prima di usare questa infografica nella timeline: il filmato deve includere le ultime modifiche.')
    return request(app, chat_id, command | {'action': 'replace', 'media_id': movie['id'], 'label': 'Infografica · ' + deck['title'][:110]})


def render(app, job, payload, settings, cancel, stage, log):
    command = settings['_video_clip']
    if command['action'] == 'export':
        media, _ = extract(app, job, command, cancel, stage, log)
        app.store.update_answer(job, 'Ecco lo spezzone con l’audio originale. Puoi scaricarlo o usarlo dalla galleria.', 'done', [media], {'intent': 'video', 'execution_mode': 'Standalone · CPU · export spezzone'})
    else:
        replace(app, job, payload, command, cancel, stage, log)
    app.store.execute("UPDATE jobs SET status='done',stage='Spezzone pronto' WHERE id=?", (job['id'],))


def replace(app, job, payload, command, cancel, stage, log):
    from .soundtrack import compose
    value, selected = target(app, job['chat_id'], command)
    index = selected['clip'] - 1; original = value['record']; scene = original['timeline'][index]
    first, last = interval(selected, scene); width, height = dimensions(value, index)
    folder = app.data / 'outputs' / job['id']; folder.mkdir(parents=True, exist_ok=True)
    fitted = folder / 'replacement.mp4'
    app.engine.tool_call('video-clip-worker.py', {'source': str(safe_join(app.data, command['media']['path'])),
        'output': str(fitted), 'frames': last - first, 'width': width, 'height': height}, cancel, stage, log, timeout=1800)
    if cancel.is_set():
        raise Cancelled()
    if first or last != scene['frames']:
        from .video_import import prepare
        prepare(app, value, cancel, stage, log, clips=[index + 1])
        output = folder / 'edited.mp4'
        app.engine.tool_call('video-splice-worker.py', {'original': str(safe_join(app.data, original['outputs'][index])),
            'replacement': str(fitted), 'output': str(output), 'start_frame': first, 'end_frame': last, 'total_frames': scene['frames']}, cancel, stage, log, timeout=1800)
    else:
        output = fitted
    record = copy.deepcopy(original)
    record.update(working_timeline=True, revision_source=selected['source'], revision_remount=False,
                  revision_completed=[index + 1], revision_versions=selected['versions'])
    record['outputs'][index] = output.relative_to(app.data).as_posix()
    record.setdefault('clip_sources', [None] * len(record['timeline']))[index] = None
    record['parameters'][index] = {k: v for k, v in record['parameters'][index].items() if k not in ('steps', 'pdd_enabled', 'loras')}
    record['parameters'][index].update(timeline_label=command['label'], deterministic_edit=True,
        replacement_media=command['media']['id'], replacement_interval={'start': first / 24, 'end': last / 24}, duration=scene['duration'], fps=24)
    record['prompts'][index] += '\nPost-produzione: ' + command['label']
    record['edited_clips'] = sorted(set(record.get('edited_clips', [])) | {index + 1})
    record.pop('recreate_recipes', None)
    video_versions.remember(value, record, index)
    save(folder, record)
    preview = folder / f"clip-{index + 1:03d}.mp4"
    compose(app.engine, [output], safe_join(app.data, value['audio']['path']), preview, cancel, stage, log,
            audio_start=record.get('audio_start', 0) + scene['start'], audio_duration=scene['duration'])
    parameters = record['parameters'][index] | {'timeline_id': job['id'], 'clip_only': True, 'post_edit': True,
        'audio_preserved': True, 'clip': index + 1}
    media = {'id': job['id'], 'name': f"Clip {index + 1} · {command['label']}.mp4", 'mime': 'video/mp4',
        'path': preview.relative_to(app.data).as_posix(), 'generation': parameters}
    meta = {'intent': 'video', 'execution_mode': 'Standalone · CPU · sostituzione spezzone', 'references': value['refs'],
            'video_parameters': parameters, 'video_plan': record['plan']}
    app.store.update_answer(job, f"Ho inserito {command['label']} nella clip {index + 1}, conservando durata, formato e audio originale. Premi Riprendi timeline per vedere l’anteprima o montare il video completo.", 'done', [media], meta)
