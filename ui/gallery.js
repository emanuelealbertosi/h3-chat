import {escape as esc} from './render.js';

export function openGallery({api,onSelect,kind='all',multiple=true}){
 const dialog=document.createElement('dialog');dialog.className='gallery-dialog';dialog.ariaLabel='Galleria';
 dialog.innerHTML=`<header><div><span class="eyebrow">I TUOI FILE</span><h2>Galleria</h2></div><button type="button" class="icon-button" data-close aria-label="Chiudi galleria">×</button></header><div class="gallery-filters"><input data-query type="search" placeholder="Cerca per nome…" aria-label="Cerca nella galleria"><select data-kind aria-label="Tipo di file">${[['all','Tutti'],['image','Immagini'],['audio','Audio'],['video','Video'],['document','Documenti'],['other','Altri file']].map(([v,t])=>`<option value="${v}">${t}</option>`).join('')}</select><select data-origin aria-label="Origine"><option value="all">Caricati e generati</option><option value="uploaded">Caricati</option><option value="generated">Generati</option></select></div><p data-status role="status"></p><div class="gallery-grid"></div><footer><button class="btn" data-more hidden>Altri file</button><span data-count></span><button class="btn primary" data-select disabled>Usa i file selezionati</button></footer>`;
 document.body.append(dialog);const q=s=>dialog.querySelector(s);q('[data-kind]').value=kind;let offset=0,revision=0,selected=new Map(),timer;
 q('[data-close]').onclick=()=>dialog.close();dialog.onclose=()=>{clearTimeout(timer);revision++;dialog.remove();};
 const status=t=>q('[data-status]').textContent=t;
 const selection=()=>{q('[data-select]').disabled=!selected.size;q('[data-count]').textContent=selected.size?selected.size+' selezionati':'';};
 async function load(append=false){
  const request=++revision;if(!append){offset=0;q('.gallery-grid').replaceChildren();}status('Caricamento…');
  try{const params=new URLSearchParams({q:q('[data-query]').value,kind:q('[data-kind]').value,origin:q('[data-origin]').value,offset:String(offset)}),result=await api('/gallery?'+params);
   if(request!==revision||!dialog.open)return;offset=result.offset;q('[data-more]').hidden=!result.more;status(result.total?result.total+' file nella tua galleria':'La galleria è vuota. Carica un file o crea un contenuto nella chat.');
   for(const item of result.items){const card=document.createElement('article');card.className='gallery-card';
    const pick=document.createElement('button');pick.type='button';pick.className='gallery-pick';pick.ariaLabel='Seleziona '+item.name;pick.setAttribute('aria-pressed',String(selected.has(item.id)));
    const media=item.mime.startsWith('image/')?`<img loading="lazy" src="${esc(item.url)}" alt="">`:`<span class="gallery-symbol">${item.mime.startsWith('audio/')?'♫':item.mime.startsWith('video/')?'▷':'▤'}</span>`;
    pick.innerHTML=media+`<strong>${esc(item.name)}</strong><small>${item.origin==='generated'?'Generato':'Caricato'} · ${(item.size/1024/1024).toLocaleString('it-IT',{maximumFractionDigits:1})} MB</small>`;
    pick.onclick=()=>{if(selected.has(item.id))selected.delete(item.id);else{if(!multiple){selected.clear();for(const b of dialog.querySelectorAll('.gallery-pick'))b.setAttribute('aria-pressed','false');}selected.set(item.id,item);}pick.setAttribute('aria-pressed',String(selected.has(item.id)));selection();};card.append(pick);
    const preview=document.createElement('a');preview.className='text-button';preview.textContent='Apri / scarica';preview.href=item.url;preview.target='_blank';preview.rel='noopener';card.append(preview);
    if(item.mime.startsWith('audio/')){const audio=document.createElement('audio');audio.controls=true;audio.preload='none';audio.src=item.url;card.append(audio);}
    q('.gallery-grid').append(card);
   }
  }catch(e){if(request===revision)status(e.message);}
 }
 q('[data-query]').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>load(),250);};q('[data-kind]').onchange=q('[data-origin]').onchange=()=>load();q('[data-more]').onclick=()=>load(true);
 q('[data-select]').onclick=async()=>{q('[data-select]').disabled=true;try{const items=await api('/gallery/select',{ids:[...selected.keys()]});await onSelect(items);dialog.close();}catch(e){status(e.message);selection();}};
 dialog.showModal();load();return dialog;
}

export function initGallery({api,getAttachments,setAttachments,notify}){
 document.addEventListener('h3-export',async event=>{try{const {blob,name}=event.detail;if(blob.size>64*1024**2)throw Error('Il download supera 64 MB: il file è scaricato, ma non archiviato in galleria.');const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(blob);});await api('/gallery/import',{name,data});}catch(e){notify(e.message,true);}});
 const button=document.createElement('button');button.type='button';button.id='gallery-open';button.className='btn small';button.textContent='▧ Galleria';button.title='Riutilizza file caricati e generati in ogni modalità';document.querySelector('#attach').after(button);
 button.onclick=()=>openGallery({api,onSelect:items=>{const existing=getAttachments(),ids=new Set(existing.map(m=>m.id)),next=[...existing,...items.filter(m=>!ids.has(m.id))];if(next.length>12)throw Error('Seleziona al massimo 12 allegati.');setAttachments(next);notify('File aggiunti al prompt.');}});
}
