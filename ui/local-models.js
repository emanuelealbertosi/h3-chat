import {escape as esc} from './render.js';

export function initLocalModels({api,getState,onChange,notify}){
  const $=s=>document.querySelector(s);
  document.body.insertAdjacentHTML('beforeend',`
    <dialog id="local-model-dialog" class="local-model-dialog"><form id="local-model-form">
      <header><div class="eyebrow">USA I FILE CHE HAI GIÀ</div><h2 id="local-model-title">Collega un modello</h2><p>I pesi restano nelle cartelle originali. Puoi usare anche file su un’altra unità.</p></header>
      <div class="local-model-body"><label class="field"><span>Tipo di modello</span><select id="local-model-kind"></select></label>
      <label class="field"><span>Nome nella lista</span><input id="local-model-name" maxlength="150" placeholder="Nome facoltativo"></label>
      <div id="local-model-files"></div><p id="local-model-hint" class="small-note" aria-live="polite"></p>
      <p id="local-model-error" class="local-error" role="alert"></p></div>
      <footer><button type="button" id="local-model-close" class="btn">Annulla</button><button type="submit" id="local-model-save" class="btn primary">Salva collegamento</button></footer>
    </form></dialog>
    <dialog id="model-browser" class="model-browser"><header><h2>Scegli un file modello</h2><p>GGUF o safetensors · il file viene usato dove si trova.</p></header>
      <form id="model-browser-address"><input id="model-browser-path" aria-label="Percorso della cartella" placeholder="Percorso della cartella"><button class="btn" type="submit">Apri</button></form>
      <nav><button id="model-browser-roots" class="text-button">Unità</button><button id="model-browser-up" class="text-button">↑ Cartella superiore</button></nav>
      <div id="model-browser-list"></div><p id="model-browser-error" class="local-error" role="alert"></p>
      <footer><button id="model-browser-close" class="btn">Annulla</button></footer></dialog>`);
  let draft=null,selectedInput=null,parent='',browseTicket=0,suggestTicket=0;
  const guarded=fn=>async(...args)=>{try{await fn(...args);}catch(e){notify(e.message,true);}};
  const read=()=>{draft.name=$('#local-model-name').value;for(const f of $('#local-model-files').querySelectorAll('[data-local-role]'))draft.files[f.dataset.localRole]=f.value;
    draft.projector_mode=$('#local-projector-mode')?.value||'auto';if($('#local-steps')){draft.steps=Number($('#local-steps').value);draft.cfg=Number($('#local-cfg').value);}};
  const pathField=(role,required)=>`<label class="field"><span>${esc(getState().model_role_labels[role])}${required?' *':' · facoltativo'}</span><div class="path-field"><input data-local-role="${role}" aria-label="${esc(getState().model_role_labels[role])}" value="${esc(draft.files[role]||'')}" placeholder="Percorso completo del file" ${required?'required':''}><button type="button" class="btn small" data-browse-role="${role}">Sfoglia</button></div></label>`;
  function renderFiles(){
    const profile=getState().external_profiles[draft.profile];
    $('#local-model-files').innerHTML=profile.required.map(r=>pathField(r,true)).join('')+(draft.profile==='chat'?
      `<label class="field"><span>Vision / mmproj</span><select id="local-projector-mode"><option value="auto">Automatico · stessa cartella del GGUF</option><option value="manual">Scegli un mmproj</option><option value="off">Disattiva vision</option></select><small>Un solo mmproj presente viene usato automaticamente. Se ce ne sono più di uno, scegli il file compatibile.</small></label><div id="local-projector-field">${pathField('mmproj',true)}</div>`:
      profile.optional.map(r=>pathField(r,false)).join('')+`<div class="settings-grid"><label class="field"><span>Passi (0 = Preferenze)</span><input type="number" id="local-steps" min="0" max="100" value="${draft.steps??profile.steps??0}"></label><label class="field"><span>CFG</span><input type="number" id="local-cfg" min="0" max="30" step="0.1" value="${draft.cfg??profile.cfg??7}"></label></div>`);
    if($('#local-projector-mode')){
      $('#local-projector-mode').value=draft.projector_mode||'auto';
      const update=()=>{const automatic=$('#local-projector-mode').value!=='manual';$('#local-projector-field').hidden=automatic;$('#local-projector-field input').disabled=automatic;};
      update();$('#local-projector-mode').onchange=()=>{read();update();};
    }
    for(const b of $('#local-model-files').querySelectorAll('[data-browse-role]'))b.onclick=()=>openBrowser($('#local-model-files').querySelector(`[data-local-role="${b.dataset.browseRole}"]`));
    const main=$('#local-model-files').querySelector(`[data-local-role="${profile.main}"]`);
    main.onchange=()=>suggestComponents();
  }
  async function suggestComponents(){
    read();const profile=getState().external_profiles[draft.profile],path=draft.files[profile.main];
    if(!path)return;
    const ticket=++suggestTicket;$('#local-model-hint').textContent='Controllo dei componenti nella stessa cartella…';
    try{
      const result=await api('/model-files/suggest',{profile:draft.profile,path});
      if(ticket!==suggestTicket||!$('#local-model-dialog').open)return;
      read();
      if(!draft.name){draft.name=result.name;$('#local-model-name').value=draft.name;}
      for(const [role,value] of Object.entries(result.files))if(!draft.files[role])draft.files[role]=value;
      renderFiles();
      const candidates=Object.entries(result.candidates).filter(([,files])=>files.length);
      $('#local-model-hint').textContent=candidates.map(([role,files])=>getState().model_role_labels[role]+': '+files.length+(files.length===1?' file trovato':' file trovati')).join(' · ')||'Nessun componente aggiuntivo riconosciuto nella stessa cartella.';
      if(draft.profile!=='chat')$('#local-model-hint').textContent+=' Controlla i componenti proposti; puoi sceglierli anche da cartelle diverse.';
    }catch(e){if(ticket===suggestTicket)$('#local-model-hint').textContent=e.message;}
  }
  function open(model=null){
    suggestTicket++;
    draft=model?structuredClone(model.external_config):{profile:'chat',name:'',files:{},projector_mode:'auto'};
    $('#local-model-title').textContent=model?'Modifica collegamento':'Collega un modello';
    $('#local-model-kind').innerHTML=Object.entries(getState().external_profiles).map(([id,p])=>`<option value="${id}">${esc(p.label)}</option>`).join('');
    $('#local-model-kind').value=draft.profile;$('#local-model-name').value=draft.name;
    $('#local-model-error').textContent='';$('#local-model-hint').textContent='Il file GGUF principale deve essere la prima parte se il modello è suddiviso.';
    renderFiles();$('#local-model-dialog').showModal();
  }
  $('#local-model-kind').onchange=()=>{read();suggestTicket++;draft.profile=$('#local-model-kind').value;draft.files={};delete draft.steps;delete draft.cfg;$('#local-model-hint').textContent='Scegli il file principale e i componenti richiesti dal modello.';renderFiles();};
  $('#local-model-close').onclick=()=>{$('#local-model-dialog').close();suggestTicket++;};
  $('#local-model-form').onsubmit=async e=>{e.preventDefault();read();$('#local-model-save').disabled=true;$('#local-model-error').textContent='';
    try{const model=await api('/external-models',draft);suggestTicket++;$('#local-model-dialog').close();await onChange(model);notify('Collegamento salvato. Seleziona il modello nel Setup.');}
    catch(error){$('#local-model-error').textContent=error.message;}
    finally{$('#local-model-save').disabled=false;}
  };
  async function openBrowser(input){suggestTicket++;selectedInput=input;$('#model-browser').showModal();await showDirectory(input.value||parent||'');}
  async function showDirectory(path){
    const ticket=++browseTicket;$('#model-browser-path').value=path;$('#model-browser-error').textContent='';$('#model-browser-list').textContent='Lettura della cartella…';
    try{
      const value=await api('/model-files/browse',{path});if(ticket!==browseTicket)return;
      if($('#model-browser-path').value===path)$('#model-browser-path').value=value.path;parent=value.parent;$('#model-browser-up').disabled=value.parent===null;
      $('#model-browser-list').innerHTML=value.entries.map((entry,i)=>`<button type="button" class="browser-entry" data-file-index="${i}"><span>${entry.directory?'▱':'◇'}</span><span>${esc(entry.name)}</span><small>${entry.directory?'Cartella':(entry.size/1024**3).toFixed(2)+' GiB'}</small></button>`).join('')||'<p>Nessun file modello in questa cartella.</p>';
      for(const button of $('#model-browser-list').querySelectorAll('[data-file-index]'))button.onclick=guarded(async()=>{
        const entry=value.entries[Number(button.dataset.fileIndex)];
        if(entry.directory)await showDirectory(entry.path);
        else{selectedInput.value=entry.path;$('#model-browser').close();selectedInput.dispatchEvent(new Event('change',{bubbles:true}));read();}
      });
      if(value.truncated)$('#model-browser-error').textContent='Elenco limitato. Apri una sottocartella o incolla direttamente il percorso del file.';
    }catch(e){if(ticket===browseTicket){$('#model-browser-list').textContent='';$('#model-browser-error').textContent=e.message;}}
  }
  $('#model-browser-address').onsubmit=e=>{e.preventDefault();showDirectory($('#model-browser-path').value);};
  $('#model-browser-roots').onclick=()=>showDirectory('');$('#model-browser-up').onclick=()=>showDirectory(parent||'');
  $('#model-browser-close').onclick=()=>{$('#model-browser').close();browseTicket++;};
  return {open,remove:guarded(async model=>{await api('/external-models/'+model.id,{},'DELETE');await onChange(null,model.id);notify('Collegamento rimosso. I file originali restano al loro posto.');})};
}
