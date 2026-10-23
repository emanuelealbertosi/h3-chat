import {generationRows} from './video-generation-details.js';

const keys=['width','height','steps','cfg','sampler','scheduler','seed','negative_prompt','strength','aspect','megapixels','moss_turbo','moss_turbo_previous'];
export function imageRecipeParameters(recipe){
 if(!recipe?.reusable||recipe.kind!=='image')throw Error(recipe?.warnings?.join(' ')||'Ricetta originale incompleta.');
 const p=recipe.parameters;
 if(!Number.isInteger(p.seed)||p.seed<0)throw Error('Seed effettivo non disponibile.');
 return Object.fromEntries(keys.filter(k=>p[k]!==undefined).map(k=>[k,p[k]]));
}

export function imageRecipePrompt(recipe){
 const p=imageRecipeParameters(recipe);
 // A historical random-seed directive must not randomize the restored recipe.
 return recipe.prompt.replace(/\bseed\s*[:=]?\s*(?:(?:fisso|fixed)\s*[:=]?\s*)?(-?\d+|casual[ei]|random(?:ico|ica|ized)?)\b/gi,(text,value)=>Number(value)===p.seed?text:'seed '+p.seed);
}

export function appendCreationDetails(host,media,{api,meta={},onReuseImage,load=false}={}){
 if(!media?.mime?.startsWith('image/')&&!media?.mime?.startsWith('video/'))return;
 const image=media.mime.startsWith('image/'),parameters=media.generation||(image?meta?.image_parameters:meta?.video_parameters)||{};
 const box=document.createElement('details');box.className='creation-details no-export';
 const summary=document.createElement('summary');summary.textContent='Dati di creazione'+(Number.isInteger(parameters.seed)?' · Seed '+parameters.seed:'');
 const body=document.createElement('div'),status=document.createElement('p');status.className='small-note';status.setAttribute('role','status');
 const toolbar=document.createElement('div');toolbar.className='image-creation-actions';
 const download=document.createElement('button');download.type='button';download.className='text-button';download.textContent='Scarica dati (.json)';download.disabled=true;toolbar.append(download);
 let reuse;
 if(image&&onReuseImage){reuse=document.createElement('button');reuse.type='button';reuse.className='text-button';reuse.textContent='Riusa impostazioni';reuse.title='Prepara modello, prompt, seed, riferimenti e LoRA nella bozza della chat. Non avvia una generazione.';reuse.disabled=true;toolbar.prepend(reuse);}
 box.append(summary,body,toolbar,status);host.append(box);let recipe,pending;
 function show(value){
  recipe=value;body.replaceChildren();const p=value.parameters||{};
  summary.textContent='Dati di creazione'+(Number.isInteger(p.seed)?' · Seed '+p.seed:'');
  const table=document.createElement('dl');table.className='video-generation-grid';
  for(const [name,text] of generationRows(p,{model:value.model?.name})){const row=document.createElement('div'),label=document.createElement('dt'),content=document.createElement('dd');label.textContent=name;content.textContent=text;row.append(label,content);table.append(row);}body.append(table);
  for(const [name,text] of [['Prompt',value.prompt],['Negative prompt',p.negative_prompt]])if(text){const title=document.createElement('strong'),pre=document.createElement('pre');title.textContent=name;pre.textContent=text;pre.style.whiteSpace='pre-wrap';body.append(title,pre);}
  status.textContent=value.warnings?.length?value.warnings.join(' '):image?(p.metadata_embedded?'La ricetta è anche nel PNG. ':'')+'Riusa impostazioni prepara una bozza con Assistant Off, usando il prompt effettivo. Il risultato può cambiare se cambia il motore.':'Ricetta recuperata dall’app. Scarica anche il JSON per conservarla con il filmato.';
  download.disabled=!Object.keys(p).length;if(reuse){reuse.disabled=!value.reusable;reuse.title=value.reusable?'Prepara modello, prompt, seed, riferimenti e LoRA nella bozza. Non avvia una generazione.':value.warnings?.join(' ')||'Dati originali incompleti.';}
 }
 async function fetchRecipe(){
  if(pending)return pending;
  pending=(async()=>{
   if(!api){show({kind:image?'image':'video',model:{name:parameters.model||meta?.model},prompt:parameters.prompt||meta?.image_prompt,parameters,warnings:[],reusable:false});return;}
   box.setAttribute('aria-busy','true');status.textContent='Recupero dei dati originali…';
   try{show(await api('/media/'+media.id+'/generation'));}catch(e){status.textContent=e.message;pending=null;}
   finally{box.removeAttribute('aria-busy');}
  })();return pending;
 }
 download.onclick=()=>{if(!recipe)return;const blob=new Blob([JSON.stringify(recipe,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=(media.name||'creazione')+'.h3.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 if(reuse)reuse.onclick=async()=>{reuse.disabled=true;reuse.setAttribute('aria-busy','true');try{await onReuseImage(recipe);}catch(e){status.textContent=e.message;}finally{reuse.disabled=!recipe?.reusable;reuse.removeAttribute('aria-busy');}};
 box.addEventListener('toggle',()=>{if(box.open)fetchRecipe();});
 if(load)fetchRecipe();return box;
}
