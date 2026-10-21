import {videoConversionProgress} from './video-conversion-progress.js';

export function videoResplit(host,{data,source,api,chatId,resplit,isSubmitting=()=>false,setPending=()=>{},onError}){
 const origin=data.resplit_source||(data.imported?source:null);if(!origin)return;
 const controls=document.createElement('section');controls.className='video-edit-source';controls.dataset.resplit='';
 controls.innerHTML='<label class="field"><span>Nuova durata dei segmenti</span><select data-resplit-seconds aria-label="Nuova durata dei segmenti"><option value="10">10 secondi</option><option value="15">15 secondi</option></select></label><button type="button" class="btn small" data-resplit-video>Risuddividi dal video originale</button><p class="small-note">Riparte dal video originale. Le modifiche, i tagli e le selezioni attuali non verranno mantenuti nella nuova timeline. I video già generati restano in galleria.</p><p class="small-note" role="status" data-resplit-status></p>';
 host.after(controls);const select=controls.querySelector('select'),button=controls.querySelector('button'),status=controls.querySelector('[role="status"]');
 select.value=String(data.segment_seconds|| (Number(localStorage.getItem('h3.video-import.segment-seconds'))===10?10:15));
 button.onclick=async()=>{
  if(isSubmitting())return;
  const seconds=Number(select.value);
  if(!window.confirm(`Risuddividere il video originale in segmenti da ${seconds} secondi?\n\nLe modifiche, i tagli, le versioni selezionate e le istruzioni attuali non verranno mantenuti nella nuova timeline. I video già generati resteranno in galleria.`))return;
  const inputs=[...controls.closest('form').querySelectorAll('button,input,select,textarea')].map(input=>[input,input.disabled]);
  setPending(true);for(const [input] of inputs)input.disabled=true;status.textContent='Preparazione della nuova suddivisione…';
  const progress=videoConversionProgress(controls,{api,path:'/chats/'+chatId+'/video-import-progress/'+origin+'?segment_seconds='+seconds,label:'Preparazione della nuova suddivisione…'});
  try{await resplit(origin,seconds);localStorage.setItem('h3.video-import.segment-seconds',String(seconds));}
  catch(e){status.textContent='';onError(e.message);}
  finally{progress.stop();status.textContent='';for(const [input,disabled] of inputs)input.disabled=disabled;setPending(false);}
 };
}
