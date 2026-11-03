import {imageRequestValues} from './image-request.js';
let loading;
function load(){
 if(!loading)loading=(async()=>{
  const css=document.createElement('link');css.rel='stylesheet';css.href='/static/vendor/moss-layout/le-editor.css';document.head.append(css);
  for(const name of ['le-model','le-formats','le-validate','le-editor'])await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='/static/vendor/moss-layout/'+name+'.js';script.onload=resolve;script.onerror=()=>reject(Error('Impossibile aprire i componenti locali dell’editor.'));document.head.append(script);});
 })().catch(e=>{loading=null;throw e;});return loading;
}
export function validateLayout(value){
 if(!value||typeof value!=='object'||!Number.isInteger(value.width)||!Number.isInteger(value.height)||[value.width,value.height].some(n=>n<256||n>4096||n%16)||value.width*value.height<250000||value.width*value.height>4000000)throw Error('Tela: lati da 256 a 4096 pixel, multipli di 16 e da 0,25 a 4 MP.');
 if(value.bbox_coord_space!=='abs'||value.bbox_format!=='xyxy'||!value.summary?.caption?.trim())throw Error('Scrivi la descrizione generale dell’immagine.');
 if(!Array.isArray(value.items)||!value.items.length||value.items.length>64)throw Error('Aggiungi da 1 a 64 riquadri; preferisci non più di 12 elementi principali.');
 for(const [index,item] of value.items.entries()){
  if(!['object','character','text'].includes(item.label)||typeof item.caption!=='string'||!item.caption.trim())throw Error(`Riquadro ${index+1}: scrivi il sottoprompt descrittivo.`);
  if(item.label==='text'&&(typeof item.text!=='string'||!item.text.trim()))throw Error(`Riquadro ${index+1}: manca il testo da disegnare.`);
  const b=item.bbox;if(!Array.isArray(b)||b.length!==4||b.some(n=>typeof n!=='number'||!Number.isFinite(n))||!(0<=b[0]&&b[0]<b[2]&&b[2]<=value.width&&0<=b[1]&&b[1]<b[3]&&b[3]<=value.height))throw Error(`Riquadro ${index+1}: coordinate invertite o fuori dalla tela.`);
 }
 if(JSON.stringify(value).length>24000)throw Error('Il layout supera 24.000 caratteri: accorcia i sottoprompt.');return value;
}
export function toDraft(prompt,width,height){
 const value=JSON.parse(prompt);
 if(value.bbox_coord_space==='abs'&&value.bbox_format==='xyxy')return validateLayout(value);
 if(value.bbox_coord_space!=='abs_centralized'||value.bbox_format!=='yxyx')throw Error('Importa un layout MOSS in formato abs/xyxy oppure abs_centralized/yxyx.');
 return validateLayout({width,height,summary:value.summary,items:value.items.map(i=>({...i,bbox:[i.bbox[1]+width/2,i.bbox[0]+height/2,i.bbox[3]+width/2,i.bbox[2]+height/2]})),bbox_coord_space:'abs',bbox_format:'xyxy'});
}
export function initMossLayoutEditor({getState,visualControls,notify}){
 let dialog,editor,openedModel;
 async function open(){
  const state=getState(),value=visualControls.read(),model=state.models.find(m=>m.id===value.image_model);
  if(model?.architecture!=='moss')throw Error('Seleziona un modello MOSS nelle immagini per usare il layout.');
  await load();openedModel=model.id;
  if(!dialog){
   dialog=document.createElement('dialog');dialog.id='moss-layout-dialog';dialog.setAttribute('aria-labelledby','moss-layout-title');dialog.className='h3-moss-layout';
   dialog.innerHTML='<header><h2 id="moss-layout-title">Layout immagine · MOSS</h2><button type="button" aria-label="Chiudi editor layout">×</button></header><p>Disegna e sposta i riquadri; selezionali per inserire il sottoprompt e, per i testi, le parole esatte. O / T scelgono oggetti o testi; trascina i bordi per ridimensionare. Le posizioni guidano il modello, senza garantire precisione al pixel.</p><div class="h3-layout-core"></div><p class="h3-layout-message" role="status"></p><footer><span>La bozza resta in questa chat. Applica prepara il prompt; Invia avvia la generazione.</span><button type="button" data-layout-apply>Applica alla chat</button><button type="button" data-layout-close>Chiudi</button></footer>';
   const style=document.createElement('style');style.textContent='.h3-moss-layout{width:96vw;max-width:1800px;height:94dvh;max-height:96dvh;padding:14px;box-sizing:border-box;border:1px solid var(--line);border-radius:14px}.h3-moss-layout[open]{display:flex;flex-direction:column;gap:8px}.h3-moss-layout header,.h3-moss-layout footer{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.h3-moss-layout h2{margin:0;flex:1}.h3-moss-layout p{margin:0;font-size:12px}.h3-layout-core{flex:1;min-height:0;--background:var(--paper,#f5f5f1);--background-panel:var(--white,#fff);--background-soft:#e9eee9;--text:#183d36;--text-soft:#536b64;--light-border:#bacbc3;--emphasis:#276b60;--button-background:#edf3ef;--button-text:#183d36}.h3-moss-layout footer span{flex:1;font-size:12px}.h3-layout-message{color:#a34028}.h3-moss-layout::backdrop{background:#10251fcc}@media(max-width:650px){.h3-moss-layout{width:99vw;height:96dvh;padding:6px}.h3-layout-core{overflow:auto}.h3-layout-core .le-root{min-width:600px}}';document.head.append(style);document.body.append(dialog);
   const message=dialog.querySelector('[role=status]');
   const apply=()=>{try{
    if(visualControls.read().image_model!==openedModel)throw Error('Il modello è cambiato: riapri il layout con MOSS selezionato.');
    const m=editor.getModel(),draft=toDraft(editor.getPrompt(),m.width,m.height),prompt=JSON.stringify(draft,null,2);if(prompt.length>24000)throw Error('Il layout supera il limite di 24.000 caratteri.');
    const current=visualControls.read();visualControls.set({...current,image_layout_draft:JSON.parse(JSON.stringify(m)),image_presets:{...current.image_presets,[openedModel]:{...current.image_presets?.[openedModel],width:m.width,height:m.height,megapixels:m.width*m.height/1e6,aspect:'auto'}}});
    const input=document.querySelector('#prompt');input.value=prompt;input.dispatchEvent(new Event('input',{bubbles:true}));dialog.close();notify('Layout applicato. Premi Invia per generare l’immagine.');
   }catch(e){message.textContent=e.message;}};
   editor=new window.LayoutEditor.Editor(dialog.querySelector('.h3-layout-core'),{mode:'h3',canGenerate:false,applyLabel:'Applica alla chat',isActive:()=>dialog.open,onApply:apply});
   const labels={'Caption':'Sottoprompt','Caption (how the text looks)':'Sottoprompt · aspetto del testo','Text to render':'Testo esatto da disegnare','Type':'Tipo','Inspector':'Proprietà del riquadro','Layers':'Riquadri','Scene caption':'Descrizione generale','+ Add':'+ Aggiungi','Undo':'Annulla','Redo':'Ripeti'};
   new MutationObserver(()=>{for(const e of dialog.querySelectorAll('.le-label,.le-panel-title,.le-toolbar button')){const translated=labels[e.textContent];if(translated)e.textContent=translated;}}).observe(dialog.querySelector('.h3-layout-core'),{subtree:true,childList:true,characterData:true});
   dialog.querySelector('[data-layout-apply]').onclick=apply;
   dialog.querySelector('header button').onclick=dialog.querySelector('[data-layout-close]').onclick=()=>dialog.close();
   dialog.addEventListener('close',()=>{visualControls.set({...visualControls.read(),image_layout_draft:JSON.parse(JSON.stringify(editor.getModel()))});});
  }
  dialog.querySelector('[role=status]').textContent='';
  const dimensions=imageRequestValues(state,value),raw=document.querySelector('#prompt').value.trim();
  editor.model=window.LayoutEditor.normalizeModel(value.image_layout_draft||window.LayoutEditor.newModel('moss'));
  if(!value.image_layout_draft)editor.setSize(dimensions.width,dimensions.height,false);
  if(raw.startsWith('{')){
   const parsed=JSON.parse(raw);const draft=toDraft(raw,parsed.width||editor.model.width,parsed.height||editor.model.height);editor.setSize(draft.width,draft.height,false);if(!editor.importPrompt(JSON.stringify(draft),true))throw Error('Layout MOSS non riconosciuto.');
  }else if(raw)editor.model.scene.caption=raw;
  editor.selectedId=null;editor.history=[JSON.stringify(editor.model)];editor.historyIndex=0;dialog.showModal();editor.renderAll();
 }
 return{open:()=>open().catch(e=>notify(e.message,true))};
}
