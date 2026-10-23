"""Reuse the same checked melody/separation/alignment pipeline as video remix."""
from pathlib import Path
from .downloads import safe_join
from .music_options import options,worker_options

def generate(engine,model,settings,composition,job_id,cancel,stage):
    config=settings['_music_resing'];source=safe_join(engine.data,config['source']['path'])
    folder=engine.data/'outputs'/job_id;folder.mkdir(parents=True,exist_ok=True)
    runtime=config['runtime'];log=folder/'engine.log'
    def call(op,**kwargs):
        return engine.tool_call('video-remix-worker.py',{'op':op,'runtime':runtime,'folder':str(folder),'source':str(source),**kwargs},cancel,stage,log,timeout=14400)
    stage('Re-sing · preparazione della base originale');engine.stop()
    info=call('probe')
    if not info['has_audio'] or not 3<=info['duration']<=300.5:raise ValueError('Re-sing richiede una canzone da 3 secondi a 5 minuti. Nessun tratto viene tagliato automaticamente.')
    p=worker_options(options(model,settings));p['cot']='full';fields={'mode':'singing','start':0,'end':info['duration'],'style':composition['style'],
        # Re-sing follows the attached song. A saved ABC belongs to ordinary
        # composition and must never bypass source-note alignment/verification.
        'text':composition['lyrics'],'abc':'','clone_voice':False,'reference_start':0,'reference_duration':10}
    result=call('vocal',config=fields,reference=None,music={'files':engine.model_files(model),'options':p})
    output=Path(result['path']).resolve()
    if not output.is_relative_to(folder.resolve()) or not output.is_file():raise RuntimeError('Risultato Re-sing non valido.')
    import json
    report_file=folder/'singing-report.json';report=json.loads(report_file.read_text(encoding='utf-8')) if report_file.is_file() else {}
    return {'id':job_id,'name':composition['title']+' · Re-sing.wav','path':output.relative_to(engine.data.resolve()).as_posix(),'mime':'audio/wav',
            'generation':p|{'engine':'yue2-resing','duration':info['duration'],'source_id':config['source']['id'],'original_preserved':True,'alignment':report.get('alignment',{})}}
