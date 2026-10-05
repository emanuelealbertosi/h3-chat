import {themes,typography,designs,encodeDeck,applyOverride,validateDesign} from './slide-design.js';
import {parseColor,colorHex} from './color-contrast.js';
import {effectiveBackground} from './slide-contrast.js';
import {imagePicker} from './slide-image-picker.js';
export function mountEditor(target,deck,index,frames,onChange,session={},options={},media=[]){
  const page=deck.pages[index];session.undo||=[];session.redo||=[];
  const panel=document.createElement('section');panel.className='slide-editor no-export';panel.ariaLabel='Modifica grafica delle slide';
  panel.innerHTML='<div class="slide-editor-top"><label>Tema <select id="slide-theme"></select></label><label>Caratteri <select id="slide-typography"></select></label><button id="slide-add-text">+ Testo</button><button id="slide-undo">Annulla</button><button id="slide-redo">Ripeti</button></div><p class="slide-editor-help">Seleziona un elemento. Usa ↕ per spostarlo e ↘ per ridimensionarlo. Le modifiche vengono salvate nel canvas.</p><form id="slide-properties" hidden><label>Elemento <select id="slide-element"></select></label><label class="slide-editor-text">Testo / codice / didascalia<textarea id="slide-text" rows="3" maxlength="16000"></textarea></label><label>Dimensione carattere<input id="slide-font-size" type="number" min="16" max="88" step="1"></label><label>Carattere<select id="slide-font"><option>Manrope</option><option>Cormorant</option><option>Consolas</option></select></label><label>Testo<input id="slide-color" type="color"></label><label>Sfondo<input id="slide-background" type="color"></label><label>Allineamento<select id="slide-align"><option value="left">Sinistra</option><option value="center">Centro</option><option value="right">Destra</option></select></label><label>Larghezza<input id="slide-width" type="number" min="40" max="1164"></label><label>Altezza minima<input id="slide-height" type="number" min="20" max="1164"></label><div class="slide-editor-actions"><button type="submit">Applica</button><button type="button" id="slide-reset">Ripristina stile</button><button type="button" id="slide-duplicate">Duplica</button><button type="button" id="slide-delete">Elimina</button></div></form><p id="slide-editor-error" role="alert" hidden></p>';
  target.querySelector('.slides-navigation').after(panel);
  const q=id=>panel.querySelector('#'+id),error=e=>{q('slide-editor-error').hidden=!e;q('slide-editor-error').textContent=e?.message||'';};
  const designLabel=document.createElement('label');designLabel.textContent='Stile ';const designSelect=document.createElement('select');designSelect.id='slide-design';designLabel.append(designSelect);panel.querySelector('.slide-editor-top').prepend(designLabel);
  panel.querySelector('.slide-editor-help').append(' Il contrasto viene corretto automaticamente quando il colore scelto è poco leggibile.');
  const maxHeight=Math.min(1164,parseFloat(frames[0].style.getPropertyValue('--slide-height'))-220);q('slide-height').max=String(maxHeight);
  const comicFont=document.createElement('option');comicFont.textContent='Comic Sans MS';q('slide-font').append(comicFont);
  for(const [id,items,selected] of [['slide-theme',themes,deck.theme||'lagoon'],['slide-typography',typography,deck.typography||'modern'],['slide-design',designs,deck.design||'professional']]){
    for(const [value,label] of Object.entries(items)){const option=document.createElement('option');option.value=value;option.textContent=label;q(id).append(option);}q(id).value=selected;
  }
  const commit=async(change,before=JSON.stringify(deck),record=true)=>{
    if(target.inert)return;target.inert=true;error(null);
    try{change();validateDesign(deck);await onChange(encodeDeck(deck));if(record){session.undo.push(before);if(session.undo.length>30)session.undo.shift();session.redo=[];}target.querySelector('#slide-undo')?.toggleAttribute('disabled',!session.undo.length);target.querySelector('#slide-redo')?.toggleAttribute('disabled',!session.redo.length);}
    catch(e){Object.assign(deck,JSON.parse(before));error(e);}
    finally{target.inert=false;}
  };
  q('slide-theme').onchange=()=>commit(()=>deck.theme=q('slide-theme').value);
  q('slide-typography').onchange=()=>commit(()=>deck.typography=q('slide-typography').value);
  q('slide-design').onchange=()=>commit(()=>deck.design=q('slide-design').value);
  q('slide-undo').disabled=!session.undo.length;q('slide-redo').disabled=!session.redo.length;
  q('slide-undo').onclick=()=>{if(!session.undo.length)return;const prior=session.undo.pop();session.redo.push(JSON.stringify(deck));commit(()=>Object.assign(deck,JSON.parse(prior)),JSON.stringify(deck),false);};
  q('slide-redo').onclick=()=>{if(!session.redo.length)return;const later=session.redo.pop();session.undo.push(JSON.stringify(deck));commit(()=>Object.assign(deck,JSON.parse(later)),JSON.stringify(deck),false);};
  const ids=new Set(page.nodes.map(n=>n.id));let number=1;const newId=()=>{while(ids.has('edit'+number))number++;const id='edit'+number++;ids.add(id);return id;};
  q('slide-add-text').onclick=()=>commit(()=>{if(page.nodes.length>=40)throw Error('La pagina può contenere al massimo 40 elementi.');const id=newId();page.nodes.push({id,parent:'root',kind:'text',text:'Nuovo testo',asset_id:'',language:'text',style:{flow:'stack',columns:[1,1],surface:'soft',gap:16}});session.selected=id;});
  for(const node of page.nodes){const option=document.createElement('option');option.value=node.id;option.textContent=node.kind+' · '+(node.text.slice(0,55)||node.id);q('slide-element').append(option);}
  let selected=null;
  if(options.api)imagePicker(target,{api:options.api,chatId:options.chatId,media,onSelect:async asset=>{
    if(!media.some(m=>m.id===asset.id)){if(media.length>=64)throw Error('Massimo 64 immagini per presentazione.');media.push(asset);}
    let node=selected?.kind==='image'?selected:null;
    if(!node){if(page.nodes.length>=40)throw Error('La pagina contiene già 40 elementi.');node={id:newId(),parent:'root',kind:'image',text:asset.name,asset_id:'',language:'text',style:{flow:'stack',columns:[1,1],surface:'plain',gap:16}};page.nodes.push(node);}
    node.asset_id=asset.id;session.selected=node.id;await onChange(encodeDeck(deck),media);
  }});
  const select=id=>{
    selected=page.nodes.find(n=>n.id===id);if(!selected)return;session.selected=id;
    target.querySelectorAll('[data-node-id]').forEach(el=>el.classList.toggle('slide-selected',el.dataset.nodeId===id));
    q('slide-properties').hidden=false;q('slide-element').value=id;q('slide-text').value=selected.text;
    const el=target.querySelector(`[data-node-id="${id}"]`),style=el?getComputedStyle(selected.kind==='code'?el.querySelector('pre')||el:el):null,value=page.overrides?.[id]||{};
    q('slide-font-size').value=value.font_size||Math.round(parseFloat(style?.fontSize||27)/(Number(frames[0].style.getPropertyValue('--slide-fit'))||1));
    const inheritedFont=['Comic Sans MS','Cormorant','Consolas'].find(font=>style?.fontFamily.includes(font))||'Manrope';
    q('slide-font').value=value.font||(selected.kind==='code'?'Consolas':inheritedFont);q('slide-color').value=colorHex(parseColor(style?.color)||[22,62,72,1]);q('slide-background').value=el?colorHex(effectiveBackground(el,el.closest('.h3-slide-page'))):'#ffffff';q('slide-align').value=value.align||'left';
    delete q('slide-color').dataset.changed;delete q('slide-background').dataset.changed;
    q('slide-width').value=value.width||'';q('slide-height').value=value.height||'';
    q('slide-text').disabled=selected.kind==='group';
  };
  q('slide-element').onchange=()=>select(q('slide-element').value);
  for(const frame of frames){frame.classList.add('slide-editing');
    for(const element of frame.querySelectorAll('[data-node-id]')){
      const id=element.dataset.nodeId;element.onclick=e=>{if(e.target.closest('.slide-drag,.slide-resize'))return;e.preventDefault();e.stopPropagation();select(id);};
      for(const mode of ['drag','resize']){const handle=document.createElement('button');handle.type='button';handle.className='slide-'+mode+' no-export';handle.textContent=mode==='drag'?'↕':'↘';handle.ariaLabel=(mode==='drag'?'Sposta ':'Ridimensiona ')+id;element.append(handle);
        handle.onpointerdown=e=>{
          e.preventDefault();e.stopPropagation();select(id);handle.setPointerCapture(e.pointerId);
          const before=JSON.stringify(deck),initial=page.overrides?.[id]||{},initialStyle=element.getAttribute('style'),rect=element.getBoundingClientRect(),outer=frame.getBoundingClientRect(),scale=outer.width/1280;
          const start={x:initial.x||0,y:initial.y||0,width:initial.width||rect.width/scale,height:initial.height||rect.height/scale},origin={x:e.clientX,y:e.clientY};let value={...initial};
          const move=event=>{
            const dx=(event.clientX-origin.x)/scale,dy=(event.clientY-origin.y)/scale;
            if(mode==='drag'){
              const bounds={x:[40-(rect.left-outer.left)/scale+start.x,1240-(rect.right-outer.left)/scale+start.x],y:[40-(rect.top-outer.top)/scale+start.y,parseFloat(frame.style.getPropertyValue('--slide-height'))-56-(rect.bottom-outer.top)/scale+start.y]};
              value={...initial,x:Math.round(Math.max(bounds.x[0],Math.min(bounds.x[1],start.x+dx))),y:Math.round(Math.max(bounds.y[0],Math.min(bounds.y[1],start.y+dy)))};
            }else value={...initial,width:Math.round(Math.max(40,Math.min(1164,start.width+dx))),height:Math.round(Math.max(20,Math.min(maxHeight,start.height+dy)))};
            applyOverride(element,value);
          };
          handle.onpointermove=move;handle.onpointerup=()=>{handle.onpointermove=null;handle.onpointerup=null;commit(()=>{page.overrides||={};page.overrides[id]=value;},before);};
          handle.onpointercancel=()=>{handle.onpointermove=null;handle.onpointerup=null;if(initialStyle===null)element.removeAttribute('style');else element.setAttribute('style',initialStyle);};
        };
      }
    }
  }
  q('slide-properties').onsubmit=e=>{e.preventDefault();if(!selected)return;commit(()=>{
    selected.text=q('slide-text').value;const value={...(page.overrides?.[selected.id]||{}),font_size:Number(q('slide-font-size').value),font:q('slide-font').value,align:q('slide-align').value};
    for(const [key,input] of [['width','slide-width'],['height','slide-height']]){if(q(input).value)value[key]=Number(q(input).value);else delete value[key];}
    for(const [key,input] of [['color','slide-color'],['background','slide-background']])if(q(input).dataset.changed)value[key]=q(input).value;
    page.overrides||={};page.overrides[selected.id]=value;
    if(selected.kind==='heading'&&selected.parent==='root'){page.title=selected.text.replace(/^#+\s*/,'').slice(0,150);}
  });};
  for(const id of ['slide-color','slide-background'])q(id).oninput=()=>q(id).dataset.changed='true';
  q('slide-reset').onclick=()=>commit(()=>{if(selected&&page.overrides)delete page.overrides[selected.id];});
  const descendants=id=>{const found=new Set([id]);let changed=true;while(changed){changed=false;for(const n of page.nodes)if(found.has(n.parent)&&!found.has(n.id)){found.add(n.id);changed=true;}}return found;};
  q('slide-delete').onclick=()=>commit(()=>{if(!selected)return;const found=descendants(selected.id);if(found.size===page.nodes.length)throw Error('La pagina deve conservare almeno un elemento.');page.nodes=page.nodes.filter(n=>!found.has(n.id));for(const id of found)if(page.overrides)delete page.overrides[id];session.selected=null;});
  q('slide-duplicate').onclick=()=>commit(()=>{if(!selected)return;const found=descendants(selected.id),copies=page.nodes.filter(n=>found.has(n.id)).map(n=>structuredClone(n));if(page.nodes.length+copies.length>40)throw Error('Troppi elementi nella pagina.');const mapping=new Map(copies.map(n=>[n.id,newId()]));for(const n of copies){const old=n.id;n.id=mapping.get(old);n.parent=mapping.get(n.parent)||n.parent;if(page.overrides?.[old]){page.overrides[n.id]=structuredClone(page.overrides[old]);}}page.nodes.push(...copies);session.selected=mapping.get(selected.id);});
  if(session.selected&&ids.has(session.selected))select(session.selected);
}
