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
  document.querySelector('#video-editing-summary').textContent=editing.value==='storyboard'?'Descrivi le scene, i tempi e le immagini da usare. Assistant On pianifica inquadrature da 1 a 15 secondi, con stacchi reali e riferimenti scelti per scena. Allega o richiama la canzone: resta continua sotto tutto il video. Solo MiniMax standalone.':'Ogni clip continua il fotogramma finale del precedente. Adatto a un movimento o un’azione senza stacchi.';
  const model=state.models.find(m=>m.id===state.settings.video_model),v={...state.video_options?.defaults,...state.settings.video_overrides?.[model?.id]};
  const mp=medium?Math.min(v.megapixels??.7,.5):v.megapixels??.7,steps=medium?Math.min(v.steps??12,8):v.steps??12;
  document.querySelector('#video-quality-summary').textContent=(model?.remote_media&&!medium?'Alta conserva i parametri del server.':`${medium?'Media':'Alta'} · circa ${mp.toLocaleString('it-IT')} MP · ${steps} passi.`)+' Media riduce dettaglio e rifinitura per generare più rapidamente; mantiene durata e proporzioni. Il lip-sync usa almeno 8 passi. Questi profili valgono per MiniMax, non per Manim o infografiche HTML.';
 }};
}
