import {escape as esc} from './render.js';
import {labImageDefault} from './lab-image-model.js';
import {appendBackgroundGrid} from './background-grid.js';
import {collectionExportButton} from './image-collections.js';
import {deleteCollections} from './collection-delete.js';

const PALETTES=[['pastel','Pastello'],['natural','Naturale'],['blue','Blu e ghiaccio'],['warm','Sabbia e terracotta'],['mono','Monocromatica'],['custom','Personalizzata']];
const defaults={name:'Set di sfondi',kind:'frame',format:'16:9',themes:[],palettes:['pastel'],custom_palette:'',variants:2,margin:12,opacity:20,tone:'light',design:'professional',model:'',megapixels:null,seed_mode:'saved',seed:0};

export function initSlideBackgrounds({api,getState,onRecipe,notify}){
 const dialog=document.createElement('dialog');dialog.id='slide-background-dialog';dialog.className='prompt-options-dialog background-dialog';dialog.setAttribute('aria-labelledby','background-title');
 dialog.innerHTML=`<header><h2 id="background-title">Crea sfondi</h2><button type="button" class="icon-button" aria-label="Chiudi crea sfondi">×</button></header>
 <div class="prompt-options-body"><p>Solo sfondi in batch: descrivi il tema nel prompt della chat e premi Invia. Non vengono create slide e non vengono usati allegati, RAG o Assistant.</p>
 <form class="background-form">
 <label>Nome del set<input name="name" maxlength="100" required></label>
 <label>Tipo<select name="kind"><option value="frame">Cornice · centro libero</option><option value="soft">Sfondo tenue · trama leggera</option></select></label>
 <label>Formato<select name="format"><option>16:9</option><option>9:16</option><option>4:3</option><option>1:1</option></select></label>
 <label>Stile<select name="design"><option value="professional">Serio / professionale</option><option value="playful">Giocoso / colorato</option><option value="comic">Fumettoso</option></select></label>
 <label class="background-wide">Modello immagini<select name="model" aria-label="Modello per gli sfondi"></select></label>
 <label class="background-wide">Temi aggiuntivi, uno per riga<textarea name="themes" rows="3" placeholder="Facoltativo: botanica, spazio… su righe separate. Il prompt principale vale per tutti."></textarea></label>
 <fieldset class="background-wide"><legend>Palette da generare</legend>${PALETTES.map(([key,label])=>`<label><input type="checkbox" name="palette" value="${key}"> ${label}</label>`).join('')}</fieldset>
 <label class="background-wide" data-custom-palette>Palette personalizzata<input name="custom_palette" maxlength="250" placeholder="Es. avorio, salvia e oro tenue"></label>
 <label>Sfondi per ogni tema e palette<input name="variants" type="number" min="1" max="24" required></label>
 <div class="background-batch-total"><span>Totale del batch</span><strong data-total role="status">2 sfondi</strong><small>Il totale aumenta se selezioni più temi o palette.</small></div>
 <label>Megapixel<input name="megapixels" type="number" min="0.25" max="4" step="0.01" placeholder="Impostazioni del modello"></label>
 <label>Centro libero: margine per lato (%)<input name="margin" type="number" min="5" max="25" required></label>
 <label>Intensità consigliata (%)<input name="opacity" type="number" min="5" max="45" required></label>
 <label>Base<select name="tone"><option value="light">Chiara</option><option value="dark">Scura</option></select></label>
 <label>Seed<select name="seed_mode"><option value="saved">Impostazioni del modello</option><option value="random">Casuale per immagine</option><option value="fixed">Fisso per tutto il set</option></select></label>
 <label data-fixed-seed>Seed fisso<input name="seed" type="number" min="0" max="2147483647"></label>
 <p class="small-note background-wide">Passi, sampler e scheduler seguono il modello scelto. Margini e intensità vengono conservati per il riuso futuro. Non è richiesta trasparenza reale al modello: l’originale resta intatto.</p>
 <p class="background-wide" data-batch-count role="status"></p><p class="message-error background-wide" data-error hidden></p>
 </form>
 <details data-background-library><summary>Raccolta sfondi salvati</summary><button type="button" data-refresh-library>Aggiorna raccolta</button><label><input type="checkbox" data-preview> Simula leggibilità con velatura e area testo</label><p class="small-note">La simulazione non modifica le immagini. Lo zoom e Scarica aprono l’originale. Nessuno sfondo viene applicato alle slide.</p><div data-library></div></details></div>
 <footer><button type="button" data-slides>Torna alle slide</button><button type="button" class="btn primary" data-use>Usa modalità sfondi</button></footer>`;
 document.body.append(dialog);
 const form=dialog.querySelector('form'),field=name=>form.elements.namedItem(name),library=dialog.querySelector('[data-library]');
 const button=document.createElement('button');button.type='button';button.className='prompt-choice';button.id='create-backgrounds';button.textContent='Crea sfondi';button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-controls',dialog.id);
 const hint=document.createElement('p');hint.className='small-note background-mode-hint';hint.id='background-mode-hint';hint.hidden=true;
 let active=false,collections=[],loading=false,libraryLoaded=false,signature='';const selectedSets=new Set();
 function read(){
  return {name:field('name').value.trim(),kind:field('kind').value,format:field('format').value,design:field('design').value,model:field('model').value,
   themes:field('themes').value.split('\n').map(t=>t.trim()).filter(Boolean),palettes:[...form.querySelectorAll('[name=palette]:checked')].map(e=>e.value),custom_palette:field('custom_palette').value.trim(),
   variants:Number(field('variants').value),megapixels:field('megapixels').value===''?null:Number(field('megapixels').value),
   margin:Number(field('margin').value),opacity:Number(field('opacity').value),tone:field('tone').value,seed_mode:field('seed_mode').value,seed:Number(field('seed').value)};
 }
 function fill(config){
  const value={...defaults,...config};
  if(value.model&&![...field('model').options].some(o=>o.value===value.model)){
   const missing=document.createElement('option');missing.value=value.model;missing.textContent='Modello del set non disponibile · scegli un altro';field('model').append(missing);
  }
  for(const [key,item] of Object.entries(value))if(field(key))field(key).value=key==='themes'?item.join('\n'):item??'';
  for(const input of form.querySelectorAll('[name=palette]'))input.checked=value.palettes.includes(input.value);
 }
 fill(defaults);
 function count(){const c=read();return Math.max(1,new Set(c.themes).size)*c.palettes.length*c.variants;}
 function validate(){
  const c=read(),n=count();let error='';
  if(!Number.isInteger(c.variants)||c.variants<1||c.variants>24)error='Sfondi per tema e palette: scegli un numero intero da 1 a 24, mantenendo il totale entro 24 sfondi.';
  else if(!form.checkValidity()||!c.name){
   const invalid=[...form.elements].find(e=>e.willValidate&&!e.validity.valid);
   error=invalid?(invalid.closest('label')?.childNodes[0]?.textContent.trim()||'Campo non valido')+': '+invalid.validationMessage:'Dai un nome al set di sfondi.';
  }
  else if(c.themes.length>8||c.themes.some(t=>t.length>300))error='Massimo 8 temi da 300 caratteri ciascuno.';
  else if(!c.palettes.length)error='Scegli almeno una palette.';
  else if(c.palettes.includes('custom')&&!c.custom_palette)error='Descrivi la palette personalizzata.';
  else if(n>24)error='Massimo 24 sfondi per batch: riduci temi, palette o varianti.';
  else if(c.model&&!getState()?.models.some(m=>m.id===c.model&&m.ready&&m.capabilities.includes('create')))error='Il modello del set non è più disponibile. Scegli esplicitamente un altro modello.';
  else if(!c.model&&getState()&&!labImageDefault(getState()))error='Scegli un modello immagini disponibile.';
  const node=dialog.querySelector('[data-error]');node.textContent=error;node.hidden=!error;
  dialog.querySelector('[data-batch-count]').textContent=`${n} sfondi = ${Math.max(1,new Set(c.themes).size)} temi × ${c.palettes.length} palette × ${c.variants} varianti. Massimo 24.`;
  dialog.querySelector('[data-total]').textContent=n+' sfondi';
  dialog.querySelector('[data-custom-palette]').hidden=!c.palettes.includes('custom');dialog.querySelector('[data-fixed-seed]').hidden=c.seed_mode!=='fixed';
  field('seed').disabled=c.seed_mode!=='fixed';
  dialog.querySelector('[data-use]').disabled=!!error;return !error;
 }
 function renderLibrary(){
  library.replaceChildren();
  if(!collections.length){library.textContent='Nessun set salvato. Gli sfondi completati appariranno qui anche se interrompi il batch.';return;}
  const toolbar=document.createElement('div'),all=document.createElement('input'),allLabel=document.createElement('label'),remove=document.createElement('button');toolbar.className='project-actions';all.type='checkbox';all.ariaLabel='Seleziona tutti i set di sfondi';allLabel.append(all,' Seleziona tutti');remove.type='button';toolbar.append(allLabel,remove);library.append(toolbar);
  for(const id of selectedSets)if(!collections.some(v=>v.id===id))selectedSets.delete(id);
  const count=()=>{remove.textContent='Elimina selezionati ('+selectedSets.size+')';remove.disabled=!selectedSets.size;all.checked=collections.every(v=>selectedSets.has(v.id));all.indeterminate=selectedSets.size>0&&!all.checked;};count();
  all.onchange=()=>{for(const v of collections)all.checked?selectedSets.add(v.id):selectedSets.delete(v.id);renderLibrary();};
  remove.onclick=async()=>{try{const result=await deleteCollections(api,[...selectedSets]);if(result){for(const id of result.removed)selectedSets.delete(id);await loadLibrary();notify(result.removed.length+' set rimossi · '+result.files_deleted+' file eliminati');}}catch(error){notify(error.message);}};
  for(const set of collections){
   const section=document.createElement('section'),heading=document.createElement('h3'),note=document.createElement('p'),reuse=document.createElement('button');
   heading.textContent=set.name;note.textContent=new Date(set.created*1000).toLocaleString('it-IT')+' · '+set.available+'/'+set.total+' disponibili · '+({done:'Completato',running:'In corso',failed:'Interrotto con errore',cancelled:'Annullato',interrupted:'Interrotto'}[set.status]||set.status);
   const label=document.createElement('label'),select=document.createElement('input');select.type='checkbox';select.ariaLabel='Seleziona set '+set.name;select.checked=selectedSets.has(set.id);select.onchange=()=>{select.checked?selectedSets.add(set.id):selectedSets.delete(set.id);count();};label.append(select,' Seleziona set');section.append(label);
   reuse.type='button';reuse.textContent='Riusa ricetta del set';reuse.onclick=()=>{renderModels();fill(set.options);onRecipe(set.prompt||'');active=true;render();form.dispatchEvent(new Event('change',{bubbles:true}));notify('Ricetta recuperata. Premi Invia soltanto se vuoi generare un nuovo set.');};
   section.append(heading,note,reuse);collectionExportButton(section,api,set.id,loadLibrary);appendBackgroundGrid(section,set.images.map(item=>item.media),{preview:dialog.querySelector('[data-preview]').checked});library.append(section);
  }
 }
 async function loadLibrary(){
  if(loading)return;loading=true;library.textContent='Caricamento raccolta…';
  try{collections=(await api('/slide-backgrounds')).items;libraryLoaded=true;renderLibrary();}
  catch(error){library.textContent=error.message;}
  finally{loading=false;}
 }
 function renderModels(){
  const state=getState();if(!state)return;
  const models=state.models.filter(m=>m.ready&&m.capabilities.includes('create'));
  const next=JSON.stringify(models.map(m=>[m.id,m.name]));if(next===signature)return;signature=next;
  const chosen=field('model').value,preferred=labImageDefault(state);
  field('model').innerHTML=`<option value="">Predefinito · ${esc(preferred?.name||'nessun modello disponibile')}</option>`+models.map(m=>`<option value="${esc(m.id)}">${esc(m.name)}</option>`).join('');
  if(chosen){
   if(!models.some(m=>m.id===chosen)){const option=document.createElement('option');option.value=chosen;option.textContent='Modello del set non disponibile · scegli un altro';field('model').append(option);}
   field('model').value=chosen;
  }
 }
 function render(){
  const row=document.querySelector('[data-mode-settings=slides-options]')?.parentElement;
  if(row&&!button.isConnected){row.querySelector('button').after(button);row.after(hint);}
  renderModels();validate();button.setAttribute('aria-pressed',String(active));
  button.disabled=!getState()?.slide_options?.background_batches;button.title=button.disabled?'Attiva la novità riavviando H3-Chat dopo la fine dei lavori.':'Genera e conserva solo sfondi, senza creare slide.';
  hint.hidden=!active||document.querySelector('#lab-tool')?.value!=='slides';
  hint.textContent=`Modalità sfondi attiva · Invio genera ${count()} sfondi, senza creare slide. Descrivi il tema nel prompt. Allegati e Assistant non vengono usati.`;
  const blocked=getState()?.execution?.mode==='cpu'||getState()?.settings?.execution_mode==='cpu';
  dialog.querySelector('[data-use]').disabled=blocked||dialog.querySelector('[data-use]').disabled;
 }
 button.onclick=()=>{render();dialog.showModal();if(dialog.querySelector('[data-background-library]').open)loadLibrary();};
 dialog.querySelector('header button').onclick=()=>dialog.close();
 dialog.querySelector('[data-slides]').onclick=()=>{active=false;render();dialog.close();};
 dialog.querySelector('[data-use]').onclick=()=>{if(!validate())return;active=true;render();dialog.close();notify('Sfondi selezionati: scrivi il tema nel prompt e premi Invia.');};
 form.addEventListener('input',render);form.addEventListener('change',render);form.onsubmit=e=>e.preventDefault();
 dialog.querySelector('[data-refresh-library]').onclick=loadLibrary;
 dialog.querySelector('[data-background-library]').ontoggle=e=>{if(e.target.open&&!libraryLoaded)loadLibrary();};
 dialog.querySelector('[data-preview]').onchange=renderLibrary;
 document.addEventListener('click',event=>{if(event.target.closest('[data-mode-settings="slides-options"]')&&active){active=false;render();}});
 return {render,preferences:{holder:dialog.querySelector('.prompt-options-body'),matches:event=>form.contains(event.target),read:()=>{if(!validate())throw Error(dialog.querySelector('[data-error]').textContent);return read();},apply:config=>{renderModels();fill(config);render();}},read:()=>active&&document.querySelector('#lab-tool')?.value==='slides'?(validate()?read():(()=>{throw Error('Controlla le opzioni nella finestra Crea sfondi.');})()):null};
}
