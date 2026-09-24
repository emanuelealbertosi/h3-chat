"""Music-specific operations share Engine's LLM and resident process pool."""
import array
import base64
import json
import wave
from pathlib import Path
from .downloads import Cancelled
from .music_options import options, validate_fields
from .music_routing import MUSIC_BRIEF, direct_composition
from .music_runtime import backend, executable

class MusicEngine:
 def start_music(self,model,settings,log_path,cancel,stage=None):
  session=self._activate('music',model,settings,log_path,cancel,stage=stage)
  if session.ready and session.alive():return session
  kind=backend(settings)
  if kind not in ('cpu','cuda'):raise ValueError('YuE2 richiede CPU oppure NVIDIA CUDA. Scegli il motore Musica nelle impostazioni.')
  worker=executable(self.root,kind)
  if not worker:raise ValueError('Installa il motore Musica '+kind.upper()+' dal Setup.')
  with self.process_lock:
   if cancel.is_set():raise Cancelled()
   session.start([worker],ipc=True,cwd=worker.parent)
  session.wait('hello',cancel,30)
  session.send({'op':'load','files':session.files,'backend':kind,'threads':settings['music_threads']})
  session.wait('ready',cancel,300,stage)
  session.ready=True
  return session

 def refine_music(self,history,prompt,fields,settings,cancel,log_path,stage):
  if not settings.get('_assistant',True):return direct_composition(prompt,fields),None
  model=self.require_model(settings['chat_model'],'chat')
  stage('Assistant · stile e testo del brano')
  self.start_llama(model,settings,log_path,cancel,stage=stage)
  previous=[{'role':m['role'],'text':m['content'][-3000:],'composition':m.get('meta',{}).get('music_composition')} for m in history[-6:] if m['status']=='done']
  content=json.dumps({'request':prompt,'fields':fields,'conversation':previous},ensure_ascii=False)
  schema={'type':'object','properties':{k:{'type':'boolean' if k=='instrumental' else 'string'} for k in ('title','style','lyrics','abc','instrumental')},'required':['title','style','lyrics','abc','instrumental'],'additionalProperties':False}
  tuning=settings|{'think_level':'off','max_tokens':min(settings['music_prompt_max_tokens'],settings['context']//2)}
  raw,finish=self.completion([{'role':'system','content':MUSIC_BRIEF},{'role':'user','content':content}],tuning,cancel,on_text=lambda _:None,schema=schema)
  if finish=='length':raise ValueError('Assistant ha raggiunto il limite: aumenta contesto/token oppure scrivi un brano più breve.')
  try:result=validate_fields(json.loads(raw))
  except (ValueError,TypeError) as exc:raise ValueError('Assistant non ha restituito una composizione valida. Riprova o disattivalo e inserisci stile e testo.') from exc
  if not result['style'] or not result['lyrics']:raise ValueError('Assistant deve preparare sia stile sia testo del brano.')
  if result['instrumental']:result['lyrics']='[Instrumental]'
  return result,{'model':model['name'],'max_tokens':tuning['max_tokens']}

 def generate_music(self,model,settings,composition,job_id,cancel,stage):
  folder=self.data/'outputs'/job_id;folder.mkdir(parents=True,exist_ok=True)
  output=folder/'audio.wav';opts=options(model,settings)
  if composition['abc'] and opts['cot']=='off':raise ValueError('Per usare ABC scegli Melodia o Melodia e accordi nelle preferenze Musica.')
  stage('Caricamento / riuso · '+model['name'])
  session=self.start_music(model,settings,folder/'engine.log',cancel,stage=stage)
  request={'op':'generate','output':str(output),'style':composition['style'],'lyrics':composition['lyrics'],'abc':composition['abc'],
    'cot':opts['cot'],'seed':opts['seed'],'options':{k:v for k,v in opts.items() if k not in ('cot','seed')}}
  (folder/'composition.json').write_text(json.dumps(composition|{'parameters':opts},ensure_ascii=False,indent=2),encoding='utf-8')
  stage('Generazione musica · '+model['name'])
  session.send(request)
  try:done=session.wait('done',cancel,14400,stage)
  except RuntimeError as exc:raise RuntimeError(self.failure(session.log_path,str(exc))) from exc
  if cancel.is_set():raise Cancelled()
  try:
   with wave.open(str(output)) as audio:
    if audio.getnframes()==0:raise ValueError('Audio vuoto')
    actual={'sample_rate':audio.getframerate(),'channels':audio.getnchannels(),'duration':audio.getnframes()/audio.getframerate()}
  except (OSError,ValueError,wave.Error) as exc:raise RuntimeError('Il motore non ha prodotto un WAV valido.') from exc
  flags=json.loads((folder/'generation_flags.json').read_text()) if (folder/'generation_flags.json').exists() else {}
  tokens=folder/'abc_tokens.i32'
  if tokens.is_file():
   values=array.array('i');values.frombytes(tokens.read_bytes())
   vocab={}
   for line in Path(session.files['tokenizer']).read_text(encoding='utf-8').splitlines():
    encoded,number=line.split();vocab[int(number)]=base64.b64decode(encoded)
   score=b''.join(vocab.get(i,b'') for i in values).decode('utf-8','replace')
   if score.strip():(folder/'score.abc').write_text(score,encoding='utf-8')
  session.uses+=1
  parameters=opts|actual|flags
  return {'id':job_id,'name':composition['title']+'.wav','path':output.relative_to(self.data).as_posix(),'mime':'audio/wav','generation':parameters}
