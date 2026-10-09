export function initVideoQuality({read,save,getState}){
 const holder=document.querySelector('#video-hint');
 holder.insertAdjacentHTML('afterbegin','<label>Qualità <select id="video-quality" aria-label="Qualità video MiniMax"><option value="high">Alta · preset attuale</option><option value="medium">Media · più rapida</option></select></label><p id="video-quality-summary" class="small-note"></p>');
 const select=document.querySelector('#video-quality');
 select.onchange=()=>save({...read(),video_quality:select.value});
 return {render(){
  const state=getState();if(!state)return;
  const medium=read().video_quality==='medium';select.value=medium?'medium':'high';
  const model=state.models.find(m=>m.id===state.settings.video_model),v={...state.video_options?.defaults,...state.settings.video_overrides?.[model?.id]};
  const mp=medium?Math.min(v.megapixels??.7,.5):v.megapixels??.7,steps=medium?Math.min(v.steps??12,8):v.steps??12;
  document.querySelector('#video-quality-summary').textContent=(model?.remote_media&&!medium?'Alta conserva i parametri del server.':`${medium?'Media':'Alta'} · circa ${mp.toLocaleString('it-IT')} MP · ${steps} passi.`)+' Media riduce dettaglio e rifinitura per generare più rapidamente; mantiene durata e proporzioni. Il lip-sync usa almeno 8 passi. Questi profili valgono per MiniMax, non per Manim o infografiche HTML.';
 }};
}
