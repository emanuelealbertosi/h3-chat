"""One transcription per child process; GPU memory is released on exit."""
import argparse,json,os,sys,time,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--root',required=True);p.add_argument('--backend',choices=['cuda','cpu'],default='cuda');p.add_argument('--threads',type=int,default=8);a=p.parse_args()
root=Path(a.root);out=Path(a.output)
sys.path[:0]=[str(root),str(root/'native')]
from remix import platform_runtime
settings=json.loads(os.environ['H3_REMIX_MODELS'])
temp=root/'data/tmp';temp.mkdir(parents=True,exist_ok=True)
cuda_cache=root/'data/cuda-cache';cuda_cache.mkdir(parents=True,exist_ok=True)
os.environ.update(TEMP=str(temp),TMP=str(temp),CUDA_CACHE_PATH=str(cuda_cache),HF_HOME=str(root/'data/hf-cache'),HF_MODULES_CACHE=str(root/'data/hf-cache/modules'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',PYTHONUTF8='1',TOKENIZERS_PARALLELISM='false',PATH=str(root/'runtime')+os.pathsep+os.environ['PATH'])
req=json.loads((out/'request.json').read_text(encoding='utf-8'))
def progress(fields):
 fields['updated']=time.time();tmp=out/'progress.tmp';tmp.write_text(json.dumps(fields),encoding='utf-8');tmp.replace(out/'progress.json');print(json.dumps(fields),flush=True)
try:
 progress({'stage':'loading','message':'Caricamento del modello locale'})
 import torch,numpy as np
 from transformers import AutoModel
 from transformers.dynamic_module_utils import get_cached_module_file
 torch.set_num_threads(a.threads)
 if a.backend=='cuda' and not torch.cuda.is_available():raise RuntimeError('CUDA non disponibile. Seleziona CPU in Sistema o verifica il driver NVIDIA.')
 # Transformers copies only direct local imports. The updated tokenizer adds
 # chord_spelling_sheetsage2 as a transitive dependency of the model class.
 get_cached_module_file(settings['sheet_model'],'tokenization_sheetsage2.py',local_files_only=True)
 model=AutoModel.from_pretrained(settings['sheet_model'],base_model_path=settings['mert_model'],trust_remote_code=True,local_files_only=True).eval().to(a.backend)
 from remix.notation import install_export_compatibility
 install_export_compatibility(model)
 progress({'stage':'audio','message':'Lettura della registrazione'})
 args=[str(root/'runtime/remix/ffmpeg.exe'),'-v','error','-nostdin','-protocol_whitelist','file,pipe','-ss',str(req['start']),'-i',a.input,'-t',str(req['end']-req['start']),'-vn','-ac','1','-ar','24000','-f','f32le','pipe:1']
 decoded=subprocess.run(args,capture_output=True,timeout=600,creationflags=0x08000000 if os.name=='nt' else 0)
 if decoded.returncode:raise RuntimeError(decoded.stderr.decode(errors='replace')[-1500:])
 waveform=np.frombuffer(decoded.stdout,dtype='<f4').copy()
 result=model.transcribe(waveform,sampling_rate=24000,output_dir=str(out),melody_only=req['melody_only'],progress=progress,dtype='bf16' if a.backend=='cuda' else 'fp32')
 import pretty_midi,io
 midi=pretty_midi.PrettyMIDI(io.BytesIO(result['midi']))
 tracks=[{'name':i.name,'notes':[{'pitch':n.pitch,'velocity':n.velocity,'start':n.start,'end':n.end} for n in i.notes]} for i in midi.instruments if not i.is_drum]
 (out/'preview-notes.json').write_text(json.dumps({'duration':result['duration_seconds'],'tracks':tracks}),encoding='utf-8')
 progress({'stage':'complete','message':'Spartito e MIDI pronti' if result.get('abc') else 'Note e MIDI pronti; spartito ABC non disponibile'})
except Exception as e:
 progress({'stage':'error','message':str(e)})
 import traceback;traceback.print_exc();sys.exit(1)
