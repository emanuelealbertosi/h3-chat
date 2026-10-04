export function initProjectRagOptions({host,api,getState,refresh,showError,notify}){
 host.insertAdjacentHTML('afterbegin',`<div class="project-rag-options"><h4>Indicizzazione e ricerca</h4><div class="project-actions" aria-label="Dispositivo RAG"><button type="button" class="btn small" data-project-rag-device="cpu" aria-pressed="false">CPU</button><button type="button" class="btn small" data-project-rag-device="gpu" aria-pressed="false">GPU · NVIDIA CUDA</button></div><label class="check"><input type="checkbox" data-project-rag-visual> Indicizza immagini e pagine illustrate con Ovis</label><p class="small-note" data-project-rag-note></p><p class="small-note">La scelta vale per tutti i progetti. CPU può essere molto lenta con Ovis e libri illustrati. Premi Aggiorna indice per applicare una nuova modalità ai documenti già caricati. Vision della chat resta una scelta separata.</p></div>`);
 const buttons=[...host.querySelectorAll('[data-project-rag-device]')],visual=host.querySelector('[data-project-rag-visual]'),note=host.querySelector('[data-project-rag-note]');let busy=false,locked=false,pending=null;
 function render(indexing=false){
  locked=indexing;const s={...(getState()?.settings||{}),...pending},ovis=s.rag_embedding_profile==='ovis'&&!!s.rag_embedding_model;
  for(const b of buttons){b.disabled=busy||locked;b.setAttribute('aria-pressed',String(s.rag_device===b.dataset.projectRagDevice));b.classList.toggle('primary',s.rag_device===b.dataset.projectRagDevice);}
  visual.disabled=busy||locked||!ovis;visual.checked=s.rag_visual!==false;
  note.textContent=ovis?(s.rag_visual!==false?'Ovis · testo, immagini e pagine illustrate · ':'Ovis · solo testo · ')+(s.rag_device==='gpu'?'GPU':'CPU'):'Il modello scelto indicizza solo testo. Per immagini e pagine illustrate scegli Ovis nelle Preferenze.';
 }
 async function save(patch){busy=true;pending=patch;render(locked);try{await api('/knowledge/options',patch);await refresh();notify('Opzioni RAG salvate.');}catch(e){showError(e);}finally{busy=false;pending=null;render(locked);}}
 for(const b of buttons)b.onclick=()=>save({rag_device:b.dataset.projectRagDevice});
 visual.onchange=()=>save({rag_visual:visual.checked});render();return {render};
}
