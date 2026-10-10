export function initVideoQuality({read,save,getState}){
 const holder=document.querySelector('#video-hint');
 holder.insertAdjacentHTML('afterbegin','<label>Qualità <select id="video-quality" aria-label="Qualità video MiniMax"><option value="high">Alta · preset attuale</option><option value="medium">Media · più rapida</option></select></label><p id="video-quality-summary" class="small-note"></p>');
 const select=document.querySelector('#video-quality');
 holder.insertAdjacentHTML('beforeend','<label>Regia <select id="video-editing" aria-label="Regia video"><option value="continuous">Continuazione · movimento continuo</option><option value="storyboard">Storyboard · stacchi</option></select></label><p id="video-editing-summary" class="small-note"></p>');
 const editing=document.querySelector('#video-editing');
 editing.onchange=()=>save({...read(),video_editing:editing.value,...(editing.value==='storyboard'?{assistant:true}:{})});
 select.onchange=()=>save({...read(),video_quality:select.value});
 return {render(){
  const state=getState();if(!state)return;
  const medium=read().video_quality==='medium';select.value=medium?'medium':'high';
  editing.value=read().video_editing==='storyboard'?'storyboard':'continuous';
  document.querySelector('#video-editing-summary').textContent=editing.value==='storyboard'?'Scrivi nel prompt il numero di clip, per esempio «9 clip»: Assistant On lo rispetta e raggruppa gli stacchi interni senza altre generazioni. Ogni clip dura al massimo 15 secondi; senza un numero usa il minimo necessario. Il numero appare durante la pianificazione, prima di caricare MiniMax. La canzone resta continua. Solo MiniMax standalone.':'Ogni clip continua il fotogramma finale del precedente. Adatto a un movimento o un’azione senza stacchi.';
  const model=state.models.find(m=>m.id===state.settings.video_model),v={...state.video_options?.defaults,...state.settings.video_overrides?.[model?.id]};
  const mp=medium?Math.min(v.megapixels??.7,.5):v.megapixels??.7,steps=medium?Math.min(v.steps??12,8):v.steps??12;
  document.querySelector('#video-quality-summary').textContent=(model?.remote_media&&!medium?'Alta conserva i parametri del server.':`${medium?'Media':'Alta'} · circa ${mp.toLocaleString('it-IT')} MP · ${steps} passi.`)+' Media riduce dettaglio e rifinitura per generare più rapidamente; mantiene durata e proporzioni. Il lip-sync usa almeno 8 passi. Questi profili valgono per MiniMax, non per Manim o infografiche HTML.';
 }};
}
