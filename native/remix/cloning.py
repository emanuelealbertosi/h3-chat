"""Internal segmented SeedVC conversion; derived from H3 vocal tools."""
import hashlib,json,shutil,math,array,sys,wave,statistics
from . import mixing

def voice_steps(value=30):
 if type(value) is not int or value not in (30,50,100):raise ValueError('Qualità voce non valida: scegli 30, 50 o 100 passaggi.')
 return value

def voice_command(app,source,reference,output,settings=None,steps=30,seed=831001):
 s=settings or app.settings()
 # The singing checkpoint needs pitch conditioning; the native default is false.
 return [str(app.ENGINE),'--task','svc','--family','seed_vc','--model',str(app.voice_model()),'--backend',s['backend'],'--threads',str(s['threads']),'--task-route','v1_svc','--request-option',f'num_inference_steps={voice_steps(steps)}','--request-option',f'seed={int(seed)}','--request-option',f'inference_guidance_scale={VOICE_GUIDANCE}','--request-option','f0_condition=true','--request-option','auto_f0_adjust=false','--request-option','semitone_shift=0','--audio',str(source),'--voice-ref',str(reference),'--out',str(output),'--log','--metrics']


VOICE_RATE=44100
VOICE_WINDOW=18*VOICE_RATE
VOICE_OVERLAP=int(.4*VOICE_RATE)
REFERENCE_SECONDS=10
VOICE_GUIDANCE=.4

def reference_window(path):
 # Select a continuous, voiced and reasonably steady excerpt, never concatenate
 # words or train on the silences that happen to begin the uploaded recording.
 with wave.open(str(path),'rb') as inp:
  if (inp.getnchannels(),inp.getsampwidth(),inp.getframerate())!=(1,2,VOICE_RATE):raise ValueError('Formato del campione vocale non valido.')
  values=array.array('h');values.frombytes(inp.readframes(inp.getnframes()))
 if sys.byteorder!='little':values.byteswap()
 if not values:raise ValueError('Il campione vocale è vuoto.')
 block=round(VOICE_RATE*.05);energies=[]
 for i in range(0,len(values),block):
  part=values[i:i+block];energies.append(math.sqrt(sum(x*x for x in part)/len(part))/32768)
 ordered=sorted(energies)
 # A continuous spoken sample may have no quiet blocks: cap the noise estimate
 # against its loud blocks so that steady speech is not all labelled inactive.
 threshold=max(.005,min(ordered[len(ordered)//10]*3,ordered[int(.9*(len(ordered)-1))]*.2))
 window=min(len(values),REFERENCE_SECONDS*VOICE_RATE);width=math.ceil(window/block)
 starts=list(range(0,max(1,len(values)-window+1),round(VOICE_RATE*.25)))
 if starts[-1]!=len(values)-window:starts.append(len(values)-window)
 def score(start):
  part=energies[start//block:start//block+width];median=statistics.median(part)
  variation=sorted(part)[min(len(part)-1,int(.9*len(part)))]/max(median,.001)
  return sum(x>threshold for x in part)/len(part)-.06*math.log2(max(1,variation))
 start=max(starts,key=score);end=start+window
 active=[i for i in range(start//block,min(len(energies),math.ceil(end/block))) if energies[i]>threshold]
 if active:
  start=max(start,active[0]*block-round(.15*VOICE_RATE))
  end=min(end,(active[-1]+1)*block+round(.15*VOICE_RATE))
 part=values[start:end];window=len(part)
 rms=math.sqrt(sum(x*x for x in part)/len(part))/32768;peak=max(abs(x) for x in part)/32768
 if rms<.001 or peak<.005:raise ValueError('Il campione è troppo debole o silenzioso: usa una registrazione parlata chiara.')
 # Modest reference loudness leaves the vocoder room to synthesize without
 # flattening its peaks. Final loudness matching remains the mixer's task.
 factor=min(.04/rms,.75/peak,10.)
 return {'start_sample':start,'end_sample':start+window,'duration':window/VOICE_RATE,
         'gain_db':20*math.log10(factor),'rms':rms,'peak':peak,'activity_threshold':threshold}

def prepare_reference(app,job,d,reference):
 run=lambda args:app.run_job_process(job,d,args,append=True,phase=('Preparazione del riferimento vocale',56))
 full=d/'voice-reference-full.wav';selected=d/'voice-reference.wav'
 run([str(app.FFMPEG),'-y','-v','error','-nostdin','-protocol_whitelist','file,pipe','-i',str(reference),'-ar',str(VOICE_RATE),'-ac','1','-c:a','pcm_s16le',str(full)])
 selection=reference_window(full);app.check_cancel(job['id'])
 filters=f'atrim=start_sample={selection["start_sample"]}:end_sample={selection["end_sample"]},asetpts=PTS-STARTPTS,volume={selection["gain_db"]:.8f}dB'
 run([str(app.FFMPEG),'-y','-v','error','-nostdin','-i',str(full),'-af',filters,'-ar',str(VOICE_RATE),'-ac','1','-c:a','pcm_s16le',str(selected)])
 app.write_json(d/'voice-reference.json',selection)
 return selected

def prepare_voice_input(app,job,d,source):
 run=lambda args:app.run_job_process(job,d,args,append=True,phase=('Preparazione del canto per la conversione',58))
 stats=mixing.measure(app,source,d,run);gain=min(0.,-3.-stats['peak_db']) if stats['peak_db'] is not None else 0.
 path=d/'voice-input.wav'
 run([str(app.FFMPEG),'-y','-v','error','-nostdin','-i',str(source),'-af',f'volume={gain:.8f}dB','-ar',str(VOICE_RATE),'-ac','1','-c:a','pcm_s16le',str(path)])
 app.write_json(d/'voice-input.json',{'gain_db':gain,'source_level':stats,'sample_rate':VOICE_RATE})
 return path

def voice_segments(frames):
 # Bundled native Whisper content extraction truncates at 30 seconds.
 if frames<=0:raise ValueError('La traccia vocale è vuota.')
 result=[];start=0
 while start<frames:
  end=min(start+VOICE_WINDOW,frames);result.append((start,end))
  if end==frames:break
  start=end-VOICE_OVERLAP
 return result

def join_voice_segments(paths,output,check_cancel):
 # Crossfade only the shared samples; never stretch a chunk or shift the base.
 pending=array.array('h')
 with wave.open(str(output),'wb') as out:
  out.setparams((1,2,VOICE_RATE,0,'NONE','not compressed'))
  for index,path in enumerate(paths):
   check_cancel()
   with wave.open(str(path),'rb') as inp:
    if (inp.getnchannels(),inp.getsampwidth(),inp.getframerate())!=(1,2,VOICE_RATE):raise ValueError('Formato segmento vocale non valido.')
    samples=array.array('h');samples.frombytes(inp.readframes(inp.getnframes()))
   if sys.byteorder!='little':samples.byteswap()
   if pending:
    n=len(pending)
    if len(samples)<n:raise ValueError('Segmento vocale troppo corto.')
    # Raised-cosine weights sum to one and have flat endpoints: preserve gain
    # and sample count without a slope discontinuity at either end of the join.
    blended=array.array('h')
    for i in range(n):
     weight=.5-.5*math.cos(math.pi*i/(n-1)) if n>1 else .5
     blended.append(round(pending[i]*(1-weight)+samples[i]*weight))
    if sys.byteorder!='little':blended.byteswap()
    out.writeframes(blended.tobytes());samples=samples[n:]
   pending=samples[-VOICE_OVERLAP:] if index<len(paths)-1 else array.array('h')
   body=samples[:-VOICE_OVERLAP] if pending else samples
   if sys.byteorder!='little':body.byteswap()
   out.writeframes(body.tobytes())

def quiet_voice_segment(path):
 with wave.open(str(path),'rb') as inp:
  if (inp.getnchannels(),inp.getsampwidth())!=(1,2):return False
  values=array.array('h');values.frombytes(inp.readframes(inp.getnframes()))
 if sys.byteorder!='little':values.byteswap()
 return bool(values) and max(abs(x) for x in values)<328 and sum(x*x for x in values)/len(values)<(32768*.001)**2

def convert_voice(app,job,d,source,reference,output,settings=None):
 settings=settings or app.settings()
 steps=voice_steps(job['request'].get('voice_steps',30))
 reference=prepare_reference(app,job,d,reference)
 source=prepare_voice_input(app,job,d,source)
 duration=app.audio_info(source)['duration']
 if not math.isfinite(duration) or duration<=0:raise ValueError('La traccia vocale è vuota.')
 segments=voice_segments(round(duration*VOICE_RATE))
 folder=d/'voice-segments';folder.mkdir(exist_ok=True);paths=[];quiet=[]
 for index,(start,end) in enumerate(segments):
  app.check_cancel(job['id']);src=folder/f'{index:03d}-source.wav';raw=folder/f'{index:03d}-raw.wav';aligned=folder/f'{index:03d}.wav'
  phase=(f'Applicazione della tua voce · {index+1}/{len(segments)} · {steps} passaggi',65+int(27*index/len(segments)))
  app.run_job_process(job,d,[str(app.FFMPEG),'-y','-v','error','-nostdin','-i',str(source),'-af',f'aresample={VOICE_RATE},atrim=start_sample={start}:end_sample={end},asetpts=PTS-STARTPTS','-ar',str(VOICE_RATE),'-ac','1',str(src)],append=True,phase=phase)
  if quiet_voice_segment(src):
   shutil.copy2(src,aligned);paths.append(aligned);quiet.append(index);continue
  app.run_job_process(job,d,voice_command(app,src,reference,raw,settings,steps,job['request'].get('seed',831001)),append=True,phase=phase)
  # The vocoder rounds to mel hops; only pad/trim the tiny rounding difference.
  produced=app.audio_info(raw)['duration']
  if abs(produced-(end-start)/VOICE_RATE)>.25:raise RuntimeError('Durata della voce convertita incoerente: il rimix è stato fermato.')
  app.run_job_process(job,d,[str(app.FFMPEG),'-y','-v','error','-nostdin','-i',str(raw),'-af',f'apad=whole_len={end-start},atrim=end_sample={end-start}','-ar',str(VOICE_RATE),'-ac','1','-c:a','pcm_s16le',str(aligned)],append=True,phase=phase)
  paths.append(aligned)
 join_voice_segments(paths,output,lambda:app.check_cancel(job['id']))
 app.write_json(d/'voice-segments.json',{'sample_rate':VOICE_RATE,'voice_steps':steps,'seed':job['request'].get('seed',831001),'inference_guidance_scale':VOICE_GUIDANCE,'overlap_samples':VOICE_OVERLAP,'max_window_seconds':VOICE_WINDOW/VOICE_RATE,'reference_seconds':REFERENCE_SECONDS,'crossfade':'raised-cosine','pipeline':'prepared-segmented-v2','quiet_passthrough':quiet,'segments':[{'start_sample':a,'end_sample':b} for a,b in segments]})
