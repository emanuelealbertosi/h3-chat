import {escape as esc} from './render.js';

export const modelLabel=model=>model?.identity?.label||model?.name||'Scegli un modello';
export function modelIdentityHtml(model){
  if(!model)return '';
  if(model.api)return `<div class="model-identity-info"><strong>Modello tramite API</strong><p>${esc(model.api_config?.model||model.name)}</p></div>`;
  const info=model.identity;if(!info)return '';
  return `<div class="model-identity-info"><strong>File LLM ${model.ready?'selezionato':'previsto'}</strong><span class="model-filename">${esc(info.filename)}</span><span class="model-path">${esc(info.path)}</span><button type="button" class="text-button" data-copy-model-path="${esc(info.path)}">Copia percorso</button><details><summary>Nome e metadati del file</summary><dl><dt>Nome salvato nell’app</dt><dd>${esc(info.alias||'—')}</dd><dt>Nome interno GGUF</dt><dd>${esc(info.gguf_name||'Non dichiarato')}</dd><dt>Architettura dichiarata</dt><dd>${esc(info.architecture||'Non dichiarata')}</dd></dl><p>Il nome interno può essere generico o diverso dal nome del file. Il file indicato sopra identifica i pesi effettivamente configurati.</p></details></div>`;
}

export function initModelIdentity({getModel,act,notify}){
  document.body.insertAdjacentHTML('beforeend','<dialog id="llm-identity-dialog" class="entry-dialog model-identity-dialog"><h2>Modello LLM della chat</h2><div id="llm-identity-body"></div><div class="dialog-actions"><button id="llm-identity-close" type="button" class="btn">Chiudi</button></div></dialog>');
  document.querySelector('#model-name').onclick=()=>{document.querySelector('#llm-identity-body').innerHTML=modelIdentityHtml(getModel());document.querySelector('#llm-identity-dialog').showModal();};
  document.querySelector('#llm-identity-close').onclick=()=>document.querySelector('#llm-identity-dialog').close();
  document.addEventListener('click',act(async event=>{const button=event.target.closest('[data-copy-model-path]');if(button){await navigator.clipboard.writeText(button.dataset.copyModelPath);notify('Percorso copiato.');}}));
}
