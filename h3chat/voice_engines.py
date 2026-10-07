"""Optional local TTS families, independent parameters and portable checkpoints."""
import hashlib,json,math
from pathlib import Path
from .external_models import absolute_path

ENGINES={'higgs':'Higgs Audio v3','qwen':'Qwen3-TTS 1.7B','chatterbox':'Chatterbox Multilingual V3'}
PARAMS={
 'qwen':{'temperature':(.1,1.5,.8),'top_p':(.05,1,.95),'top_k':(1,100,50),'repetition_penalty':(1,2,1.05),'max_new_tokens':(128,4096,2048),'chunk_chars':(100,600,400),'pause_ms':(0,2000,180)},
 'chatterbox':{'temperature':(.1,1.5,.8),'exaggeration':(0,2,.65),'cfg_weight':(0,1,.35),'min_p':(0,.5,.05),'top_p':(.05,1,1.),'repetition_penalty':(1,2,1.2),'chunk_chars':(100,600,300),'pause_ms':(0,2000,180)}}
INTEGERS={'top_k','max_new_tokens','chunk_chars','pause_ms'}
SPEAKERS=('Vivian','Serena','Uncle_Fu','Dylan','Eric','Ryan','Aiden','Ono_Anna','Sohee')
LANGUAGES=('Italian','English','Chinese','Japanese','Korean','German','French','Russian','Portuguese','Spanish','Auto')
CHATTER_LANGUAGES=('it','en','ar','da','de','el','es','fi','fr','he','hi','ja','ko','ms','nl','no','pl','pt','ru','sv','sw','tr','zh')
DEFAULTS={'voice_engine':'higgs','voice_qwen_model_path':'','voice_qwen_device':'gpu','voice_qwen_precision':'bf16',
 'voice_qwen_language':'Italian','voice_qwen_female_speaker':'Vivian','voice_qwen_male_speaker':'Ryan',
 'voice_qwen_instruction':'Parla in italiano con pronuncia chiara e naturale. Narrazione partecipe e vivace, varia ritmo e intonazione, sottolinea i concetti senza enfasi teatrale.',
 'voice_chatterbox_model_path':'','voice_chatterbox_device':'gpu','voice_chatterbox_language':'it'}
for engine,fields in PARAMS.items():
 for key,(_,_,value) in fields.items():DEFAULTS['voice_'+engine+'_'+key]=value

def params(engine,settings,overrides=None):
 result={k:settings.get('voice_'+engine+'_'+k,v[2]) for k,v in PARAMS[engine].items()}
 result.update(overrides or {})
 if set(result)-set(PARAMS[engine]) - ({'instruction'} if engine=='qwen' else set()):raise ValueError('Parametri TTS non validi.')
 for key,(lo,hi,_) in PARAMS[engine].items():
  value=result[key]
  if type(value) not in ((int,) if key in INTEGERS else (int,float)) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Parametro '+ENGINES[engine]+' non valido: '+key)
 if engine=='qwen':
  result.setdefault('instruction',settings.get('voice_qwen_instruction',DEFAULTS['voice_qwen_instruction']))
  if not isinstance(result['instruction'],str) or len(result['instruction'])>2000:raise ValueError('Istruzioni Qwen TTS: massimo 2000 caratteri.')
 return result

def validate_overrides(value):
 if not isinstance(value,dict) or set(value)-set(PARAMS):raise ValueError('Parametri Voice per motore non validi.')
 for engine,fields in value.items():
  if not isinstance(fields,dict):raise ValueError('Parametri Voice non validi.')
  params(engine,DEFAULTS,fields)
 return value

def checkpoint(folder,engine):
 path=absolute_path(folder)
 for p in [path,*sorted(path.glob('snapshots/*'),reverse=True),*sorted(path.glob('models--*/snapshots/*'),reverse=True)]:
  if engine=='qwen':
   try:config=json.loads((p/'config.json').read_text(encoding='utf-8'))
   except (OSError,ValueError):continue
   if config.get('model_type')!='qwen3_tts' or config.get('tts_model_type') not in ('custom_voice','voice_design','base'):continue
   required=('config.json','model.safetensors','tokenizer_config.json','vocab.json','merges.txt','speech_tokenizer/model.safetensors','speech_tokenizer/config.json')
  else:required=('t3_mtl23ls_v3.safetensors','s3gen.pt','ve.pt','grapheme_mtl_merged_expanded_v1.json','conds.pt')
  if all((p/n).is_file() for n in required):return str(p)
 raise ValueError('Scegli la cartella completa '+ENGINES[engine]+', con pesi e componenti ufficiali.')

def runtime_ready(root,engine):
 root=Path(root)
 try:
  files=json.loads((root/'runtimes.json').read_text(encoding='utf-8'))['voice_'+engine]['files']
  marker=json.loads((root/('runtime/voice-'+engine+'/ready.json')).read_text(encoding='utf-8'))
  if marker.get('manifest')!=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest():return False
 except (OSError,ValueError,KeyError):return False
 return all((root/path).is_file() for path in ('runtime/vision/packages/numpy/__init__.py','runtime/vision/packages/safetensors/__init__.py',
  'runtime/voice-extras/packages/torch/__init__.py','runtime/voice-extras/packages/torchaudio/__init__.py',
  'runtime/voice-'+engine+'/packages/'+('qwen_tts' if engine=='qwen' else 'chatterbox')+'/__init__.py'))

def mark_ready(root,engine):
 root=Path(root);files=json.loads((root/'runtimes.json').read_text(encoding='utf-8'))['voice_'+engine]['files']
 folder=root/('runtime/voice-'+engine);folder.mkdir(parents=True,exist_ok=True)
 p=folder/'ready.writing';p.write_text(json.dumps({'manifest':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()}));p.replace(folder/'ready.json')

def validate(settings):
 if settings.get('voice_engine','higgs') not in ENGINES:raise ValueError('Motore Voice non valido.')
 for engine in PARAMS:
  params(engine,settings)
  if settings.get('voice_'+engine+'_device','gpu') not in ('cpu','gpu'):raise ValueError('Dispositivo TTS non valido.')
  path=settings.get('voice_'+engine+'_model_path','')
  if not isinstance(path,str):raise ValueError('Percorso TTS non valido.')
  if path:checkpoint(path,engine)
 if settings.get('voice_qwen_precision','bf16') not in ('bf16','8bit','4bit'):raise ValueError('Precisione Qwen TTS non valida.')
 if settings.get('voice_qwen_language','Italian') not in LANGUAGES or settings.get('voice_chatterbox_language','it') not in CHATTER_LANGUAGES:raise ValueError('Lingua TTS non valida.')
 for gender in ('female','male'):
  if settings.get('voice_qwen_'+gender+'_speaker',DEFAULTS['voice_qwen_'+gender+'_speaker']) not in SPEAKERS:raise ValueError('Voce Qwen non valida.')

def selected(settings):return settings.get('_voice_fields',{}).get('engine') or settings.get('voice_engine','higgs')

def configure(root,settings,choice):
 engine=selected(settings)
 if not runtime_ready(root,engine):raise ValueError('Installa la base del motore e i componenti '+ENGINES[engine]+' nel Setup → Voice.')
 path=checkpoint(settings.get('voice_'+engine+'_model_path') or str(Path(root)/'models'/('Qwen3-TTS-1.7B-CustomVoice' if engine=='qwen' else 'Chatterbox-Multilingual-V3')),engine)
 options=params(engine,settings,settings.get('_voice_fields',{}).get('params',{}).get(engine))
 cfg=options|{'engine':engine,'model_path':path,'device':'cuda' if settings.get('voice_'+engine+'_device','gpu')=='gpu' else 'cpu',
             'language':settings.get('voice_'+engine+'_language',DEFAULTS['voice_'+engine+'_language'])}
 if engine=='qwen':
  cfg.update(precision=settings.get('voice_qwen_precision','bf16'),speaker=settings.get('voice_qwen_'+choice['gender']+'_speaker',DEFAULTS['voice_qwen_'+choice['gender']+'_speaker']))
  directions=[]
  for k,v in choice.items():
   if k in ('pitch','speed','emotion','expressiveness') and v not in ('normal','neutral','natural'):directions.append(k+': '+v)
  cfg['instruction']+=(' Interpretazione: '+', '.join(directions)+'.') if directions else ''
  model_type=json.loads((Path(path)/'config.json').read_text())['tts_model_type'];cfg['model_kind']=model_type
  if model_type=='voice_design':cfg['instruction']+=' Voce '+('maschile.' if choice['gender']=='male' else 'femminile.')
  if model_type!='base':return cfg,{'id':cfg['speaker'] if model_type=='custom_voice' else 'voice-design','reference':'','transcript':''}
 ref=settings['voice_references'][choice['gender']]
 if not ref['path'] or not Path(ref['path']).is_file():raise ValueError('Scegli un campione vocale, preferibilmente italiano, nel Setup → Voice.')
 return cfg,{'id':choice['gender']+':'+Path(ref['path']).stem,'reference':ref['path'],'transcript':ref['transcript']}
