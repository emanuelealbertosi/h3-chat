"""Local vocal balancing. No model/runtime dependency beyond the bundled FFmpeg."""
import hashlib, json, math, re, shutil

DEFAULTS={'automatic':True,'voice_db':0.0,'compression':True,'ambience':0.0}

def validate(value=None):
 if value is None:value={}
 if not isinstance(value,dict) or set(value)-set(DEFAULTS):raise ValueError('Impostazioni mix non valide.')
 result=DEFAULTS|value
 for key in ('automatic','compression'):
  if not isinstance(result[key],bool):raise ValueError('Scelta mix non valida.')
 for key,lo,hi in (('voice_db',-12,12),('ambience',0,100)):
  try:v=float(result[key])
  except (TypeError,ValueError):raise ValueError('Valore mix non valido.')
  if not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Valore mix fuori intervallo.')
  result[key]=v
 return result

def measure(app,path,d,run):
 # Read only this invocation's JSON, never an earlier analysis in the job log.
 log=d/'engine.log';offset=log.stat().st_size if log.exists() else 0
 run([str(app.FFMPEG),'-hide_banner','-nostdin','-i',str(path),'-af','loudnorm=I=-16:TP=-2:LRA=11:print_format=json','-f','null','-'])
 with log.open('rb') as f:f.seek(offset);text=f.read().decode('utf-8',errors='replace')
 matches=re.findall(r'\{\s*"input_i"[^}]+\}',text)
 if not matches:raise RuntimeError('Misurazione del volume non riuscita.')
 data=json.loads(matches[-1])
 def finite(key):
  value=float(data[key]);return value if math.isfinite(value) else None
 return {'lufs':finite('input_i'),'peak_db':finite('input_tp')}

def matching_gain(reference,converted):
 # Never amplify silence or extremely weak separation residue.
 if reference['lufs'] is None or converted['lufs'] is None:return 0.0
 if min(reference['lufs'],converted['lufs'])<-60:return 0.0
 return max(-18.0,min(12.0,reference['lufs']-converted['lufs']))

def render(app,job,d,converted,source,runner=None):
 opts=validate(job['request'].get('mix'))
 run=runner or (lambda args:app.run_job_process(job,d,args,append=True,phase=('Bilanciamento voce e musica',95)))
 base=[source/n for n in ('drums.wav','bass.wav','other.wav') if (source/n).is_file()]
 def ff(inputs,filters,out,codec='pcm_f32le'):
  args=[str(app.FFMPEG),'-y','-v','error','-nostdin']
  for p in inputs:args+=['-i',str(p)]
  run(args+['-filter_complex',filters,'-ar','48000','-ac','2','-c:a',codec,str(out)])
 def summation(count,vocal='anull'):
  parts=f'[0:a]aformat=channel_layouts=stereo,{vocal}[a0];'
  parts+=''.join(f'[{i}:a]aformat=channel_layouts=stereo[a{i}];' for i in range(1,count))
  return parts+''.join(f'[a{i}]' for i in range(count))+f'amix=inputs={count}:duration=longest:normalize=0'
 # Float retains the old unbalanced sum without baking clipping into the backup.
 before=d/'mix-before.wav'
 if not before.exists():ff([converted]+base,summation(len(base)+1),before)
 processed=d/'voice-mix.wav';filters='anull'
 if opts['compression']:filters='acompressor=threshold=0.125:ratio=2:attack=15:release=160:makeup=1:knee=2.8'
 # A quiet, adjustable room echo. It is not extraction of the original reverb.
 if opts['ambience']:
  wet=opts['ambience']/100
  filters+=f',aecho=1:1:37|61|89:{wet*.10:.5f}|{wet*.07:.5f}|{wet*.04:.5f}'
 # Match duration to the dry voice, including for an optional ambience tail.
 duration=app.audio_info(converted)['duration']
 ff([converted],filters+f',atrim=duration={duration}',processed)
 vocal=measure(app,processed,d,run);reference=None;gain=0.0
 if opts['automatic'] and (source/'vocals.wav').is_file():
  reference=measure(app,source/'vocals.wav',d,run);gain=matching_gain(reference,vocal)
 total=gain+opts['voice_db'];floating=d/'mix-float.wav'
 ff([processed]+base,summation(len(base)+1,f'volume={total:.6f}dB'),floating)
 stats=measure(app,floating,d,run)
 master=min(0.0,-2.0-stats['peak_db']) if stats['peak_db'] is not None else 0.0
 out=d/'audio.wav';ff([floating],f'volume={master:.6f}dB',out,'pcm_s24le')
 app.write_json(d/'mix-report.json',{'settings':opts,'reference_voice':reference,'processed_voice':vocal,'automatic_voice_gain_db':gain,'voice_gain_db':total,'master_gain_db':master,'mix_before_master':stats,'ambience_note':'Ambiente regolabile, non copia degli effetti originali.'})
 floating.unlink(missing_ok=True)
 return out
