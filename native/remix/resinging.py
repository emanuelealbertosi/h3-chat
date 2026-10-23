"""New lyrics and singing on the separated original accompaniment."""
import hashlib
import json
import math
import statistics
from . import execution, platform_runtime, transcription, cloning, mixing

MAX_SECONDS = 300
DURATION_TOLERANCE = .5


def validate_fields(req):
    enabled = req.get('base_enabled', False)
    if not isinstance(enabled, bool):
        raise ValueError('Scelta della base originale non valida.')
    source = req.get('base_import_id', '')
    if not isinstance(source, str) or len(source) > 200:
        raise ValueError('Canzone originale non valida.')
    result = {'base_enabled': enabled, 'base_import_id': source}
    for key in ('base_start', 'base_end'):
        value = req.get(key, 0)
        if isinstance(value, bool):
            raise ValueError('Intervallo della base originale non valido.')
        try:
            value = float(value)
        except (ValueError, TypeError):
            raise ValueError('Intervallo della base originale non valido.')
        if not math.isfinite(value) or value < 0:
            raise ValueError('Intervallo della base originale non valido.')
        result[key] = value
    return result


def preflight(app, req):
    source=app.original
    duration=app.audio_info(source)['duration']
    if not 3<=duration<=MAX_SECONDS+DURATION_TOLERANCE:raise ValueError('Il nuovo canto richiede un tratto da 3 secondi a 5 minuti.')
    return source,{'duration':duration,'id':'excerpt'},0,duration


def read_notes(path):
    result = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 3:
            raise ValueError('Note vocali non valide.')
        start, end, pitch = map(float, fields)
        if not all(math.isfinite(v) for v in (start, end, pitch)) or not 0 <= start < end or not 0 <= pitch <= 127 or pitch != int(pitch):
            raise ValueError('Note vocali non valide.')
        result.append((start, end, int(pitch)))
    if len(result) > 2000 or any(b[0] < a[0] for a, b in zip(result, result[1:])):
        raise ValueError('Sequenza vocale troppo complessa o non ordinata.')
    return result


def matched_notes(original, generated, verification=False, time_scale=1., time_offset=None):
    """Match pitches in order; timing only breaks ties between repeated notes."""
    n, m = len(original), len(generated)
    if min(n, m) < 6:
        raise ValueError('Non sono state riconosciute abbastanza note cantate per allineare la voce.')
    guess = (0. if verification else generated[0][0] - time_scale*original[0][0]) if time_offset is None else time_offset
    # An added vocal intro is not a reliable estimate of the song's delay.
    if abs(guess)>2.5 and m>n: guess=0.
    previous = list(map(float, range(m + 1)))
    directions = bytearray(n * m)
    for i in range(1, n + 1):
        current = [float(i)] + [0.0] * m
        for j in range(1, m + 1):
            same = original[i-1][2] == generated[j-1][2]
            error = abs(time_scale*original[i-1][0] + guess - generated[j-1][0])
            diagonal = previous[j-1] + (0 if same else 1.5) + min(1.5 if verification else .3, error * (.8 if verification else .1)) if error <= 2.5 else math.inf
            choices = (diagonal, previous[j] + 1, current[j-1] + 1)
            k = min(range(3), key=lambda k: choices[k])
            current[j] = choices[k]; directions[(i-1)*m+j-1] = k
        previous = current
    i, j = n, m; matched = []
    while i or j:
        k = directions[(i-1)*m+j-1] if i and j else (1 if i else 2)
        if k == 0:
            if original[i-1][2] == generated[j-1][2]:
                matched.append((original[i-1], generated[j-1]))
            i -= 1; j -= 1
        elif k == 1: i -= 1
        else: j -= 1
    if len(matched) / (n if verification else max(n, m)) < .7:
        raise ValueError('Il nuovo canto si discosta troppo dalla melodia originale. Prova un testo con una metrica più simile.')
    return list(reversed(matched))


def timing_stats(errors):
    errors = sorted(errors)
    return {'median_onset_error_seconds': statistics.median(errors),
            'p90_onset_error_seconds': errors[min(len(errors)-1, math.ceil(.9*len(errors))-1)],
            'max_onset_error_seconds': max(errors)}


def check_phrase_coverage(original, matched):
    # A good global ratio must not hide an entire missing refrain or phrase.
    recognized = {o for o,g in matched}; original_phrases = []
    for note in original:
        if not original_phrases or note[0]-original_phrases[-1][-1][1] > .6:
            original_phrases.append([])
        original_phrases[-1].append(note)
    if any(len(phrase)>=3 and sum(note in recognized for note in phrase)/len(phrase)<.7 for phrase in original_phrases):
        raise ValueError('Una frase del nuovo canto non corrisponde alla melodia originale: il mix è stato fermato.')
    return original_phrases


def phrase_alignment(original, generated, allow_phrases=True, verification=False):
    """Keep good constant alignments; repair only reliable phrase offsets."""
    matched = matched_notes(original, generated,verification=verification)
    check_phrase_coverage(original, matched)
    delay = statistics.median(g[0] - o[0] for o, g in matched)
    stats = timing_stats(abs(g[0] - o[0] - delay) for o, g in matched)
    report = {'original_notes': len(original), 'generated_notes': len(generated), 'matching_notes': len(matched),
              'vocal_delay_seconds': delay, **stats, 'method': 'SheetSage2 note recognition; constant delay only'}
    constant_ok = abs(delay) <= 2.5 and stats['p90_onset_error_seconds'] <= .2 and stats['max_onset_error_seconds'] <= .65
    if constant_ok and (not allow_phrases or stats['p90_onset_error_seconds'] <= .08):
        return report
    message = 'Il nuovo canto cambia troppo ritmo rispetto alla base. Non è stato possibile riallinearlo senza distorsioni: prova un testo più vicino alla metrica originale.'
    if not allow_phrases or abs(delay) > 2.5:
        raise ValueError(message)
    groups = []
    for o, g in matched:
        if not groups or (o[0]-groups[-1][-1][0][1] > .6 and g[0]-groups[-1][-1][1][1] > .6):
            groups.append([])
        groups[-1].append((o,g))
    if len(groups) < 2 or any(len(group) < 3 for group in groups):
        if constant_ok: return report
        raise ValueError(message)
    anchors = []; errors = []; shifts = []
    for group in groups:
        shift = statistics.median(g[0]-o[0] for o,g in group)
        shifts.append(shift)
        errors.extend(abs(g[0]-o[0]-shift) for o,g in group)
        # Keep consonant attacks and note releases out of the tempo-adjusted
        # gaps: WSOLA needs a little audio context around each phrase.
        a, b = group[0][0][0]-.12, group[-1][0][1]+.12
        anchors.extend([{'source':a+shift,'target':a}, {'source':b+shift,'target':b}])
    corrected = timing_stats(errors)
    rates = [(b['source']-a['source'])/(b['target']-a['target']) for a,b in zip(anchors,anchors[1:])]
    # Offset changes are safe only when the available gaps can absorb them.
    # A fixed spread limit rejects long pauses even with a small tempo change;
    # the per-gap rate and the final audio verification are the actual limits.
    if max(map(abs,shifts)) > 2.5 or corrected['p90_onset_error_seconds'] > .2 or corrected['max_onset_error_seconds'] > .65 or any(not .85 <= rate <= 1.18 for rate in rates):
        if constant_ok: return report
        raise ValueError(message)
    return report | {'method':'SheetSage2 phrase alignment; pitch-preserving gap adjustment',
                     'phrases':len(groups), 'anchors':anchors, 'predicted_corrected_timing':corrected,
                     'min_gap_tempo':min(rates), 'max_gap_tempo':max(rates)}


def tempo_alignment(original, generated):
    """Recover a small uniform tempo drift, requiring the whole vocal sequence."""
    if min(len(original),len(generated))<20 or original[-1][0]-original[0][0]<10:
        raise ValueError('Non ci sono abbastanza note per verificare una variazione di tempo.')
    def fit(pairs):
        sample=pairs[::max(1,math.ceil(len(pairs)/100))]
        slopes=[(h[0]-g[0])/(p[0]-o[0]) for i,(o,g) in enumerate(sample) for p,h in sample[i+1:] if p[0]-o[0]>10]
        if not slopes:raise ValueError('Estensione vocale insufficiente per stimare il tempo.')
        scale=statistics.median(slopes)
        return scale,statistics.median(g[0]-scale*o[0] for o,g in pairs)
    candidates=[]
    for guess in (1.,.985,1.015,.97,1.03):
        try:
            pairs=matched_notes(original,generated,time_scale=guess)
            for _ in range(2):
                scale,offset=fit(pairs)
                if not .97-1e-7<=scale<=1.03+1e-7 or abs(offset)>2.5:raise ValueError('Variazione di tempo troppo grande.')
                pairs=matched_notes(original,generated,verification=True,time_scale=scale,time_offset=offset)
            scale,offset=fit(pairs)
            if not .97-1e-7<=scale<=1.03+1e-7 or abs(scale-1)<.003 or abs(offset)>2.5 or len(pairs)/max(len(original),len(generated))<.7:
                continue
            phrases=check_phrase_coverage(original,pairs)
            stats=timing_stats(abs((g[0]-offset)/scale-o[0]) for o,g in pairs)
            if stats['p90_onset_error_seconds']>.15 or stats['max_onset_error_seconds']>.45:continue
            candidates.append({'original_notes':len(original),'generated_notes':len(generated),'matching_notes':len(pairs),
                'vocal_delay_seconds':offset,'tempo_scale':scale,'voice_tempo_change_percent':(scale-1)*100,
                'method':'SheetSage2 bounded tempo alignment; pitch-preserving voice correction',
                'phrases':len(phrases),'predicted_corrected_timing':stats,**stats})
        except ValueError:continue
    if not candidates:raise ValueError('Il tempo del nuovo canto non è correggibile con sufficiente affidabilità.')
    return max(candidates,key=lambda r:(r['matching_notes'],-r['p90_onset_error_seconds']))


def alignment(original, generated, allow_phrases=True, verification=False):
    try:return phrase_alignment(original,generated,allow_phrases=allow_phrases,verification=verification)
    except ValueError as original_error:
        # A verification must only measure the rendered audio, never propose
        # another correction that would make its own timing test pass.
        if not allow_phrases or verification:raise
        try:return tempo_alignment(original,generated)
        except ValueError:raise original_error


def phrase_intervals(report, duration, source_duration):
    """Extend the phrase map at slope one, keeping missing edges silent."""
    anchors = report['anchors']
    first, last = anchors[0], anchors[-1]
    lead = first['source']-first['target']; tail = last['source']-last['target']
    a = {'source':max(0.,lead), 'target':max(0.,-lead)}
    b = {'source':min(source_duration,duration+tail), 'target':min(duration,source_duration-tail)}
    points = [a] + [p for p in anchors if a['target'] < p['target'] < b['target']] + [b]
    if len(points)<2 or any(y['source']<=x['source'] or y['target']<=x['target'] for x,y in zip(points,points[1:])):
        raise ValueError('La mappa dei tempi del canto non è utilizzabile.')
    return points


def render_aligned_voice(app, source, output, report, duration, source_duration, ff):
    if 'anchors' not in report:
        delay = report['vocal_delay_seconds']
        # Demucs emits 44.1 kHz. Delay samples and the final frame count use
        # 48 kHz, so normalize before applying either operation.
        filters = f'aformat=sample_rates=48000:channel_layouts=stereo,atrim=start={max(0,delay):.8f},asetpts=PTS-STARTPTS'
        scale=report.get('tempo_scale',1.)
        if 'tempo_scale' in report:filters+=f',atempo={scale:.10f}'
        if delay < 0: filters += f',adelay={round(-delay/scale*48000)}S:all=1'
        # adelay's initial silence may have NOPTS timestamps. atrim and the
        # output muxer can discard that silence unless we stamp every sample.
        filters += f',asetpts=N/SR/TB,apad,atrim=end_sample={round(duration*48000)}'
        ff(['-i',source,'-af',filters,'-ar','48000','-ac','2','-c:a','pcm_s24le',output], 'Allineamento del nuovo canto',82)
        return
    points = phrase_intervals(report,duration,source_duration)
    # Small overlapping margins avoid clicks at the joins. Only the voice enters
    # this graph; the accompaniment never passes through a tempo filter.
    filters = []; count = len(points)-1
    rates = [(b['source']-a['source'])/(b['target']-a['target']) for a,b in zip(points,points[1:])]
    margins = [0.]
    for i in range(1,len(points)-1):
        p = points[i]
        margins.append(min(.015,(p['target']-points[i-1]['target'])/4,(points[i+1]['target']-p['target'])/4,
                           p['source']/max(rates[i-1:i+1]),(source_duration-p['source'])/max(rates[i-1:i+1])))
    margins.append(0.)
    filters.append(f'[0:a]aresample=48000,asplit={count}'+''.join(f'[s{i}]' for i in range(count)))
    for i,(a,b) in enumerate(zip(points,points[1:])):
        rate = rates[i]; left, right = margins[i:i+2]
        span = b['target']-a['target']+left+right
        tempo = f'atempo={rate:.10f},' if abs(rate-1)>1e-7 else ''
        frames = round(span*48000)
        filters.append(f'[s{i}]atrim=start={a["source"]-left*rate:.8f}:end={b["source"]+right*rate:.8f},asetpts=PTS-STARTPTS,{tempo}asetpts=N/SR/TB,apad=whole_len={frames},atrim=end_sample={frames}[v{i}]')
    current = 'v0'
    for i in range(1,count):
        joined = f'j{i}'
        filters.append(f'[{current}][v{i}]acrossfade=d={2*margins[i]:.8f}:c1=tri:c2=tri[{joined}]')
        current = joined
    frames = round(duration*48000)
    filters.append(f'[{current}]asetpts=N/SR/TB,adelay={round(points[0]["target"]*48000)}S:all=1,asetpts=N/SR/TB,apad=whole_len={frames},atrim=end_sample={frames}[aligned]')
    graph = output.parent/'voice-alignment.ffscript'
    graph.write_text(';'.join(filters),encoding='utf-8')
    ff(['-i',source,'-filter_complex_script',graph,'-map','[aligned]','-ar','48000','-ac','2','-c:a','pcm_s24le',output], 'Correzione del ritmo vocale',82)


def process(app, job, d):
    req = job['request']; source, meta, start, end = preflight(app, req)
    app.check_cancel(job['id']); s = app.settings()
    app.write_json(d/'request.json', req); app.write_json(d/'source.json', meta)
    def run(args, label, pct):
        app.check_cancel(job['id'])
        app.run_job_process(job, d, list(map(str, args)), append=True, phase=(label, pct))
        app.check_cancel(job['id'])
    def ff(args, label, pct):
        run([app.FFMPEG, '-y', '-v', 'error', '-nostdin', '-protocol_whitelist', 'file,pipe', *args], label, pct)
    def separate(audio, folder, label, pct):
        folder.mkdir(exist_ok=True)
        ff(['-i', audio, '-ar', '44100', '-ac', '2', folder/'input.wav'], label, pct)
        run([app.ENGINE, '--task', 'sep', '--family', 'htdemucs', '--model', app.separation_model(), '--backend', s['backend'],
             '--threads', s['threads'], '--audio', folder/'input.wav', '--out-dir', folder, '--log', '--metrics'], label, pct)
        if not all((folder/(name+'.wav')).is_file() for name in ('vocals', 'drums', 'bass', 'other')):
            raise RuntimeError('Separazione incompleta: il nuovo canto non è stato rimixato.')
    def transcribe(audio, folder, duration, label, pct):
        folder.mkdir(exist_ok=True)
        app.write_json(folder/'request.json', {'start': 0, 'end': duration, 'melody_only': False})
        run([execution.transcription_python(app.ROOT, s['backend']), '-u', app.ROOT/'native/remix/transcribe_worker.py', '--input', audio,
             '--output', folder, '--root', app.ROOT, '--backend', platform_runtime.transcription_backend(s['backend']), '--threads', s['threads']], label, pct)
        return read_notes(folder/'melody_vocal.lab')
    original = d/'original.wav'
    ff(['-i', source, '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s24le', original], 'Preparazione della canzone originale', 3)
    whole_duration = app.audio_info(original)['duration']; end = min(end, whole_duration)
    duration = end - start
    if duration < 3: raise ValueError('Il tratto selezionato non contiene abbastanza audio.')
    stems = d/'stems'; separate(original, stems, 'Separazione della base originale', 10)
    excerpt = d/'source-excerpt.wav'
    ff(['-ss', start, '-i', original, '-t', duration, '-ar', '48000', '-ac', '2', excerpt], 'Preparazione del tratto cantato', 20)
    score_dir = d/'source-score'
    original_notes = [] if req.get('abc') else transcribe(excerpt, score_dir, duration, 'Lettura della melodia originale', 25)
    if not req.get('abc') and len(original_notes) < 6: raise ValueError('Il tratto scelto non contiene abbastanza canto riconoscibile.')
    score = req.get('abc') or app.read_abc(score_dir/'score.abc')
    if not score.strip(): raise RuntimeError('La melodia originale non ha prodotto uno spartito utilizzabile.')
    (d/'score.abc').write_text(score, encoding='utf-8', newline='\n')
    generated = d/'generated'; generated.mkdir(exist_ok=True)
    style = req['style'] or 'Italian, clear solo lead singing, steady tempo, follow the supplied score exactly, no extra intro, no backing vocals'
    options = dict(req['options']); options.setdefault('num_inference_steps', 48)
    generation_req = req | {'style': style, 'abc': score, 'cot': 'full', 'base_enabled': False, 'clone_enabled': False, 'options': options}
    run(app.command_for({'kind': 'generate', 'request': generation_req}, generated), 'Generazione del nuovo canto', 45)
    flags = json.loads((generated/'generation_flags.json').read_text(encoding='utf-8')) if (generated/'generation_flags.json').exists() else {}
    if flags.get('audio_truncated') or flags.get('abc_truncated'):
        raise ValueError('Il nuovo canto ha raggiunto la durata massima o il limite token. Aumenta la durata massima, lasciala vuota oppure scegli un tratto più breve; controlla anche i limiti nelle opzioni avanzate.' if 'max_duration' in options else 'Il nuovo canto è stato troncato dal limite token. Scegli un tratto più breve o aumenta il limite nelle opzioni avanzate.')
    generated_duration = app.audio_info(generated/'audio.wav')['duration']
    generated_notes = [] if req.get('abc') else transcribe(generated/'audio.wav', d/'generated-score', generated_duration, 'Controllo dei tempi del nuovo canto', 65)
    report = {'vocal_delay_seconds':0,'tempo_scale':generated_duration/duration,'method':'User ABC; duration fit only, note alignment not verified'} if req.get('abc') else alignment(original_notes, generated_notes)
    if req.get('abc') and not .5<=report['tempo_scale']<=2:raise ValueError('Il nuovo canto ha una durata troppo diversa dal tratto: scegli un testo o uno spartito più adatto.')
    report.update({'start': start, 'end': end, 'original_duration': duration, 'generated_duration': generated_duration})
    app.write_json(d/'alignment.json', report)
    fresh_stems = d/'generated-stems'; separate(generated/'audio.wav', fresh_stems, 'Estrazione del nuovo canto', 75)
    aligned = d/'new-singing.wav'
    render_aligned_voice(app,fresh_stems/'vocals.wav',aligned,report,duration,generated_duration,ff)
    if original_notes and ('anchors' in report or 'tempo_scale' in report):
        verification = d/'alignment-check.wav'
        inputs = ['-i',aligned]
        for name in ('drums','bass','other'): inputs += ['-i',stems/(name+'.wav')]
        filters = '[0:a]aformat=sample_rates=48000:channel_layouts=stereo[v];'
        filters += ''.join(f'[{i}:a]atrim=start={start:.8f}:end={end:.8f},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo[b{i}];' for i in range(1,4))
        filters += '[v][b1][b2][b3]amix=inputs=4:duration=first:normalize=0'
        ff(inputs+['-filter_complex',filters,'-ar','48000','-ac','2','-c:a','pcm_f32le',verification], 'Verifica del canto sulla base originale',83)
        checked = transcribe(verification,d/'aligned-score',duration,'Ricontrollo del ritmo corretto',84)
        def verify(notes):
            timing = alignment(original_notes,notes,allow_phrases=False,verification=True)
            if abs(timing['vocal_delay_seconds']) > .12:
                raise ValueError('Il canto riallineato conserva un ritardo troppo grande: il mix è stato fermato.')
            return timing
        try:
            verified = verify(checked)
            report['verification_source'] = 'original-backing-mix'
        except ValueError as mixed_error:
            # In a dense mix SheetSage2 sometimes tags an entire sung refrain as
            # instrumental. Recheck the actual replacement voice alone, with
            # the same pitch, phrase coverage and timing requirements. Never
            # rescue a missing voice by matching the unchanged accompaniment.
            isolated = transcribe(aligned,d/'aligned-vocal-score',duration,'Ricontrollo della voce isolata',85)
            verified = verify(isolated)
            report['verification_source'] = 'isolated-replacement-vocals'
            report['mixed_verification_error'] = str(mixed_error)
        report['verified_timing'] = verified
        app.write_json(d/'alignment.json',report)
    fresh_voice = aligned
    if req.get('clone_enabled'):
        reference = d/'reference.wav'
        ff(['-i', app.voice_sample(req['clone_voice']), '-ar', '44100', '-ac', '1', reference], 'Preparazione della tua voce', 85)
        converted = d/'converted-singing.wav'
        cloning.convert_voice(app, job, d, aligned, reference, converted, s)
        if abs(app.audio_info(converted)['duration']-duration) > .25:
            raise RuntimeError('La conversione ha cambiato la durata del canto: il mix è stato fermato.')
        fresh_voice = converted
    # Match the replacement section itself: the retained vocals elsewhere in
    # the song must not hide a quiet new voice from the full-song loudness check.
    if req['mix']['automatic']:
        reference_excerpt = d/'reference-singing.wav'
        ff(['-ss', start, '-i', stems/'vocals.wav', '-t', duration, '-ar', '48000', '-ac', '2', reference_excerpt], 'Bilanciamento del tratto cantato', 88)
        measure = lambda path: mixing.measure(app, path, d, lambda args: run(args, 'Bilanciamento del tratto cantato', 88))
        gain = mixing.matching_gain(measure(reference_excerpt), measure(fresh_voice))
        balanced = d/'balanced-singing.wav'
        ff(['-i', fresh_voice, '-af', f'volume={gain:.8f}dB,apad,atrim=duration={duration:.8f}', '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s24le', balanced], 'Bilanciamento del tratto cantato', 88)
        fresh_voice = balanced
        report['excerpt_voice_gain_db'] = gain
        app.write_json(d/'alignment.json', report)
    # Preserve the original singing outside the selected range and every instrumental sample timing.
    parts = []
    if start > 0: parts.append(('original', 0, start))
    parts.append(('new', 0, duration))
    if whole_duration-end > .0001: parts.append(('original', end, whole_duration))
    filters = []
    for i, (which, a, b) in enumerate(parts):
        index = 0 if which == 'original' else 1
        filters.append(f'[{index}:a]atrim=start={a:.8f}:end={b:.8f},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,apad,atrim=duration={b-a:.8f}[p{i}]')
    filters.append(''.join(f'[p{i}]' for i in range(len(parts))) + f'concat=n={len(parts)}:v=0:a=1[out]')
    ff(['-i', stems/'vocals.wav', '-i', fresh_voice, '-filter_complex', ';'.join(filters), '-map', '[out]', '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s24le', d/'voce.wav'], 'Inserimento sulla base originale', 90)
    final = app.mix_voice(job, d, d/'voce.wav', source=stems, runner=lambda args: run(args, 'Bilanciamento del nuovo canto', 95))
    result = app.audio_info(final) | {'regenerated_vocals': True, 'original_preserved': True, 'source_kind': 'import', 'import_id': req['base_import_id'],
                                    'base_start': start, 'base_end': end, 'alignment': report, 'cloned': req.get('clone_enabled', False)}
    if req.get('clone_enabled'): result.update({'voice': req['clone_voice'], 'voice_steps': req['voice_steps']})
    def digest(path):
        with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
    app.write_json(d/'manifest.json', {'result': result, 'sha256': {name: digest(d/name) for name in ('audio.wav', 'original.wav', 'voce.wav', 'score.abc', 'alignment.json')}})
    return result
