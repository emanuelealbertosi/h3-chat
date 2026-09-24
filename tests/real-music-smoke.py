"""Optional real-weight integration test. Never part of the weight-free CI suite."""
import argparse,json,threading,time,wave,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from h3chat.service import Service
p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--vae',required=True);p.add_argument('--backend',choices=['cpu','cuda'],default='cuda');p.add_argument('--full',action='store_true');p.add_argument('--chat-model');args=p.parse_args()
app=Service(ROOT,ROOT/'work'/('music-smoke-'+str(time.time_ns())),start_worker=False)
try:
 music=app.external_model({'profile':'yue2','files':{'model':args.model,'vae':args.vae}})
 settings={'music_model':music['id'],'chat_model':'','music_backend':args.backend,'memory_policy':'on_demand','ram_cache_gb':0}
 if args.chat_model:
  llm=app.external_model({'profile':'chat','files':{'model':args.chat_model},'projector_mode':'off'})
  settings.update(chat_model=llm['id'],context=8192,max_tokens=1024,vision_enabled=False)
 app.save_settings(settings);pid=None
 for index in range(2):
  if index or not args.full:app.save_settings({'music_overrides':{music['id']:{'cot':'off','num_inference_steps':2,'semantic_min_tokens':200,'semantic_max_tokens':200}}})
  chat=app.store.create_chat();job_id=app.send(chat['id'],{'prompt':'Create a short acoustic pop song about morning light.','music':True,'assistant':bool(args.chat_model) and index==0,'canvas':index==1,'music_fields':{'title':'Morning light','style':'warm acoustic pop, guitar and piano, gentle male voice','lyrics':'[Verse]\nMorning light across the floor\nA new beginning at the door\n\n[Chorus]\nLet the sun rise in my heart\nEvery day a brand new start'}})['job_id']
  job=app.store.one('SELECT * FROM jobs WHERE id=?',(job_id,));app.execute_job(job,threading.Event())
  answer=app.store.chat(chat['id'])['messages'][-1];assert answer['status']=='done',answer['meta']
  if index==0:pid=app.engine.active.process.pid
  else:assert app.engine.active.process.pid==pid;assert answer['media']==[];assert answer['meta']['music_parameters']['audio_truncated']
  media=(answer['meta']['artifact']['media'] if index else answer['media'])[0]
  with wave.open(str(app.data/media['path'])) as wav:assert wav.getnchannels()==2 and wav.getframerate()==48000 and wav.getnframes()>0
  print(json.dumps(media,ensure_ascii=False),flush=True)
 print('PASS. Outputs:',app.data)
finally:app.close()
