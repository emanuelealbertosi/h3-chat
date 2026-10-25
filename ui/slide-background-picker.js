import {appendBackgroundGrid} from './background-grid.js';

export function initSlideBackgroundPicker({api,getState,holder=document.querySelector('#slides-options'),prefix='slides'}){
 const section=document.createElement('fieldset');section.className='slide-background-controls';
 section.innerHTML='<legend>Composizione dello sfondo</legend><label>Base <select id="slides-background-base" aria-label="Base dello sfondo slide"><option value="auto">Automatico · comportamento attuale</option><option value="plain">Plain · tinta unita</option><option value="gradient">Gradient · sfumatura</option><option value="collection">Raccolta · sfondi salvati</option></select></label><label><input id="slides-background-decorations" type="checkbox"> Decoration · bordi e accenti HTML/SVG</label><div data-library-choice hidden><button type="button" data-choose>Scegli sfondi dalla raccolta</button><p data-selection role="status"></p><label>Intensità (%) <input id="slides-background-opacity" type="number" min="5" max="45" value="20"></label><label>Velatura per la lettura <select id="slides-background-veil"><option value="auto">Automatica · dal set</option><option value="light">Chiara</option><option value="dark">Scura</option></select></label></div><p class="small-note">Decoration si combina con Plain, Gradient o Raccolta. Gli sfondi selezionati ruotano nell’ordine scelto; una slide ricreata conserva il suo sfondo.</p>';
 holder.append(section);
 if(prefix!=='slides')for(const item of section.querySelectorAll('[id]'))item.id=item.id.replace(/^slides-/,prefix+'-');
 const base=section.querySelector('select'),decoration=section.querySelector('input[type=checkbox]'),intensity=section.querySelector('#'+prefix+'-background-opacity'),veil=section.querySelector('#'+prefix+'-background-veil');
 let selected={set_id:'',asset_ids:[]},setName='',collections=[],draft={set_id:'',asset_ids:[]};
 const dialog=document.createElement('dialog');dialog.className='prompt-options-dialog background-dialog';dialog.id='slide-background-picker';dialog.setAttribute('aria-label','Scegli sfondi per le slide');
 dialog.innerHTML='<header><h2>Scegli sfondi per le slide</h2><button type="button" class="icon-button" data-close aria-label="Chiudi selezione sfondi">×</button></header><div class="prompt-options-body"><label>Batch salvato <select data-batch aria-label="Batch di sfondi"></select></label><p data-details></p><div class="background-picker-actions"><button type="button" data-all>Seleziona tutti</button><button type="button" data-none>Deseleziona tutti</button><button type="button" data-refresh>Aggiorna raccolta</button></div><p class="small-note">Spunta gli sfondi da usare. Le frecce cambiano l’ordine di rotazione; clic sull’immagine apre lo zoom. Le cornici vengono mostrate intere, con contenuti nell’area interna.</p><p data-order role="status"></p><div data-grid></div><p class="message-error" data-error hidden></p></div><footer><button type="button" data-cancel>Annulla</button><button type="button" class="btn primary" data-use>Usa sfondi selezionati</button></footer>';
 document.body.append(dialog);
 if(prefix!=='slides'){dialog.id=prefix+'-background-picker';dialog.querySelector('h2').textContent='Scegli sfondi per l’infografica';section.querySelector('.small-note').textContent+=' Lo sfondo statico sostituisce il video allegato come fondale.';}
 const batch=dialog.querySelector('[data-batch]'),gridHost=dialog.querySelector('[data-grid]'),error=dialog.querySelector('[data-error]');
 function state(){
  section.querySelector('[data-library-choice]').hidden=base.value!=='collection';
  section.querySelector('[data-selection]').textContent=selected.asset_ids.length?`${setName} · ${selected.asset_ids.length} sfondi · rotazione salvata`:'Scegli un batch e almeno uno sfondo.';
  base.disabled=decoration.disabled=!getState()?.slide_options?.background_styles;
  section.title=base.disabled?'Riavvia H3-Chat a lavori terminati per attivare la scelta degli sfondi.':'';
 }
 function draw(){
  gridHost.replaceChildren();error.hidden=true;const set=collections.find(s=>s.id===draft.set_id),images=set?.images||[];
  const valid=new Set(images.map(i=>i.media.id));draft.asset_ids=draft.asset_ids.filter(id=>valid.has(id));
  dialog.querySelector('[data-details]').textContent=set?`${set.name} · ${set.available}/${set.total} disponibili · formato ${set.options.format}`:'Nessun set disponibile. Crea prima un batch con «Crea sfondi».';
  dialog.querySelector('[data-order]').textContent=draft.asset_ids.length?`${draft.asset_ids.length} sfondi selezionati. Dopo l’ultimo, la rotazione riparte dal primo.`:'Nessuno sfondo selezionato.';
  dialog.querySelector('[data-use]').disabled=!draft.asset_ids.length;
  const cards=appendBackgroundGrid(gridHost,images.map(i=>i.media));
  [...cards.children].forEach((figure,index)=>{
   const id=images[index].media.id,label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=draft.asset_ids.includes(id);check.setAttribute('aria-label','Usa sfondo '+(index+1));
   check.onchange=()=>{draft.asset_ids=check.checked?[...draft.asset_ids,id]:draft.asset_ids.filter(x=>x!==id);draw();};
   label.append(check,document.createTextNode(' Usa questo sfondo'));figure.prepend(label);
   const order=draft.asset_ids.indexOf(id);
   if(order>=0){
    const controls=document.createElement('div');controls.className='background-picker-actions';const position=document.createElement('span');position.textContent='Ordine '+(order+1);controls.append(position);
    for(const [delta,symbol,caption] of [[-1,'↑','Sposta prima'],[1,'↓','Sposta dopo']]){
     const move=document.createElement('button');move.type='button';move.textContent=symbol;move.setAttribute('aria-label',caption+' sfondo '+(index+1));move.disabled=order+delta<0||order+delta>=draft.asset_ids.length;
     move.onclick=()=>{[draft.asset_ids[order],draft.asset_ids[order+delta]]=[draft.asset_ids[order+delta],draft.asset_ids[order]];draw();};controls.append(move);
    }figure.append(controls);
   }
  });
 }
 async function load(){
  try{
   collections=(await api('/slide-backgrounds')).items;batch.replaceChildren();
   for(const set of collections){const option=document.createElement('option');option.value=set.id;option.textContent=set.name+' · '+set.available+'/'+set.total+' · '+new Date(set.created*1000).toLocaleDateString('it-IT');batch.append(option);}
   if(collections.some(s=>s.id===draft.set_id))batch.value=draft.set_id;
   else if(!draft.set_id&&collections.length){draft={set_id:collections[0].id,asset_ids:collections[0].images.map(i=>i.media.id)};batch.value=draft.set_id;}
   else if(draft.set_id){batch.value='';gridHost.textContent='Il set selezionato non è disponibile. Scegli esplicitamente un altro batch.';dialog.querySelector('[data-use]').disabled=true;return;}
   draw();
  }catch(e){error.textContent=e.message;error.hidden=false;dialog.querySelector('[data-use]').disabled=true;}
 }
 function open(){draft=structuredClone(selected);dialog.showModal();load();}
 section.querySelector('[data-choose]').onclick=open;
 base.onchange=()=>{if(base.value==='collection'){decoration.checked=false;open();}state();};
 decoration.onchange=()=>{if(decoration.checked&&base.value==='auto')base.value='plain';state();};
 batch.onchange=()=>{const set=collections.find(s=>s.id===batch.value);draft={set_id:set?.id||'',asset_ids:(set?.images||[]).map(i=>i.media.id)};draw();};
 dialog.querySelector('[data-all]').onclick=()=>{draft.asset_ids=(collections.find(s=>s.id===draft.set_id)?.images||[]).map(i=>i.media.id);draw();};
 dialog.querySelector('[data-none]').onclick=()=>{draft.asset_ids=[];draw();};dialog.querySelector('[data-refresh]').onclick=load;
 dialog.querySelector('[data-close]').onclick=dialog.querySelector('[data-cancel]').onclick=()=>dialog.close();
 dialog.querySelector('[data-use]').onclick=()=>{if(!draft.asset_ids.length)return;selected=structuredClone(draft);const set=collections.find(s=>s.id===selected.set_id);setName=set.name;intensity.value=set.options.opacity||20;base.value='collection';state();dialog.close();};
 return {render:state,read(){
  if(base.value==='auto')return {};
  if(base.value==='collection'&&!selected.asset_ids.length)throw Error('Scegli almeno uno sfondo dalla raccolta nelle Impostazioni Slide.');
  if(!intensity.checkValidity())throw Error('Intensità sfondo: scegli da 5 a 45%.');
  return {background_style:{base:base.value,decorations:decoration.checked,...selected,opacity:Number(intensity.value),veil:veil.value}};
 }};
}
