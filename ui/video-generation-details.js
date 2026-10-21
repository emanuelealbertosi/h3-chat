const number=value=>Number.isFinite(value)?value.toLocaleString('it-IT',{maximumFractionDigits:3}):null;
const file=path=>typeof path==='string'?path.split(/[\\/]/).at(-1):null;
const yes=value=>typeof value==='boolean'?(value?'Attivo':'Disattivato'):null;

export function generationRows(p,meta={}){
 const rows=[],add=(label,value)=>{if(value!==null&&value!==undefined&&value!=='')rows.push([label,String(value)]);};
 add('Modello',p.model_name||meta.model||p.model_id);
 if(Number.isInteger(p.reused_clips))add('Montaggio',`${p.replaced_clips?.length??0} clip modificate · ${p.reused_clips} riutilizzate`);
 add('File modello',file(p.model_file));
 add('Durata',number(p.duration)&&number(p.duration)+' s');
 add('Risoluzione',p.width&&p.height?`${p.width} × ${p.height}`:null);
 add('Formato',p.aspect);add('Risoluzione impostata',number(p.megapixels)&&number(p.megapixels)+' MP');
 add('Fotogrammi al secondo',number(p.fps));add('Passi',number(p.steps));add('CFG',number(p.cfg));
 add('Sampler',p.sampler);add('Scheduler',p.scheduler);add('Seed',Number.isFinite(p.seed)?String(p.seed):null);
 add('Shift video / audio',p.shift_video!=null&&p.shift_audio!=null?`${p.shift_video} / ${p.shift_audio}`:null);
 add('Attenzione richiesta',p.attention_requested||p.attention);
 add('Attenzione utilizzata',p.attention_backend);if(p.attention_chunks_mode&&(p.attention==='veda'||p.attention_requested==='veda'))add('Scelta gruppi VEDA',p.attention_chunks_mode==='manual'?'Esplicita':'Automatica');add('Gruppi attenzione effettivi',number(p.attention_chunks));if(p.attention_chunks_requested!=null&&p.attention_chunks_requested!==p.attention_chunks)add('Gruppi richiesti',number(p.attention_chunks_requested));
 if(p.veda)add('VEDA effettiva',p.veda.active?'Attiva'+(p.veda.fallback_reason?' · '+p.veda.fallback_reason:''):'Non utilizzata'+(p.veda.fallback_reason?' · '+p.veda.fallback_reason:''));
 add('Offload',yes(p.offload));add('PDD',yes(p.pdd_enabled));
 if(p.pdd_enabled)add('Adattatore PDD',file(p.pdd_lora));
 const applied=p.loras_applied,loras=applied??p.loras;
 if(Array.isArray(loras))add(applied?'LoRA applicati':'LoRA salvati',loras.filter(x=>x.weight!==0).map(x=>`${x.file||file(x.path)||x.name} · peso ${x.weight}`).join('; ')||'Nessuno');
 const source=p.source_video;
 if(source){
  const aligned=source.conditioning==='aligned'||p.source_conditioning==='aligned';
  add('Guida video',aligned?'Allineata · stessa griglia dell’uscita':'Riferimento leggero');
  add('Dimensioni guida',source.width&&source.height?`${source.width} × ${source.height}`:null);
  if(!aligned)add('Risoluzione riferimento',number(source.megapixels)&&number(source.megapixels)+' MP');
  add('Fotogrammi sorgente',number(source.frames));
  if(source.anchored_frames?.length)add('Fotogrammi guida',source.anchored_frames.join(', '));
 }
 add('Lip-sync',yes(p.lip_sync));add('Audio guida per MiniMax',yes(p.audio_guide));add('Audio originale conservato',yes(p.audio_preserved));
 add('Motore',p.engine==='minimax-h3'?'MiniMax H3':p.engine);add('Qualità',p.quality==='medium'?'Media':p.quality==='high'?'Alta':p.quality);
 add('Tempo di campionamento',number(p.sampling_seconds)&&number(p.sampling_seconds)+' s');
 const memory=(p.memory||[]).map(x=>x.reserved_mb).filter(Number.isFinite);
 if(memory.length)add('VRAM riservata · massimo campionato',number(Math.max(...memory)/1024)+' GiB');
 return rows;
}

function table(p,meta){
 const list=document.createElement('dl');list.className='video-generation-grid';
 for(const [name,value] of generationRows(p,meta)){const row=document.createElement('div'),label=document.createElement('dt'),text=document.createElement('dd');label.textContent=name;text.textContent=value;row.append(label,text);list.append(row);}
 return list;
}

export function appendGenerationDetails(target,media,meta={}){
 const p=media.generation||meta.video_parameters;
 if(!p||typeof p!=='object'||p.imported_video)return;
 const details=document.createElement('details');details.className='video-generation-details';
 const summary=document.createElement('summary');summary.textContent='Impostazioni di generazione';details.append(summary,table(p,meta));
 const note=document.createElement('p');note.className='small-note';note.textContent='Valori salvati con questo video. I parametri non registrati dalle versioni precedenti non vengono ricostruiti dalle Preferenze.';details.append(note);
 if(p.scene_parameters?.length>1){
  const clips=document.createElement('details'),title=document.createElement('summary');title.textContent='Impostazioni delle singole clip · '+p.scene_parameters.length;clips.append(title);
  p.scene_parameters.forEach((clip,index)=>{const item=document.createElement('details'),label=document.createElement('summary');label.textContent='Clip '+(index+1)+(clip.model_name?' · '+clip.model_name:'');item.append(label,table(clip));clips.append(item);});details.append(clips);
 }
 target.append(details);
}
