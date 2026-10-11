import {escape as esc} from './render.js';
import {openGallery} from './gallery.js';

export const clipClock=value=>{const seconds=Math.max(0,Number(value)||0);return Math.floor(seconds/60)+':'+String(Math.floor(seconds%60)).padStart(2,'0')+(seconds%1?'.'+String(Math.round(seconds%1*1000)).padStart(3,'0'):'');};

export async function openVideoEdit({api,chatId,source,busy,onQueued}){
 const data=await api('/chats/'+chatId+'/video-edit/'+source);
 const dialog=document.createElement('dialog');dialog.className='video-edit-dialog';dialog.ariaLabel='Modifica clip del video';
 dialog.innerHTML=`<header><div><span class="eyebrow">POST-PRODUZIONE</span><h2>Modifica clip</h2><p>Scegli i tratti e descrivi le modifiche. La nuova versione conserva canzone, durata e formato.</p></div><button type="button" class="icon-button" data-close aria-label="Chiudi">×</button></header><form><div class="video-edit-toolbar"><label class="check"><input type="checkbox" name="assistant" checked> Assistant On</label><button type="button" class="btn small" data-gallery>Riferimenti dalla galleria</button><button type="button" class="btn small" data-upload>Carica immagini</button><input type="file" accept="image/*" multiple data-files hidden></div><div class="video-edit-clips"></div><p class="settings-error" data-error role="alert" hidden></p><footer><span data-summary>Seleziona almeno un clip</span><button class="btn primary" type="submit" disabled>Crea nuova versione</button></footer></form>`;
 document.body.append(dialog);const q=s=>dialog.querySelector(s),draft=new Map(),extra=[];
 dialog.onclose=()=>{for(const v of dialog.querySelectorAll('video'))v.pause();dialog.remove();};q('[data-close]').onclick=()=>dialog.close();
 const error=text=>{q('[data-error]').textContent=text;q('[data-error]').hidden=!text;};
 const summary=()=>{const count=[...draft.values()].filter(x=>x.enabled).length;q('[data-summary]').textContent=count?count+' clip da rigenerare · '+(data.clips.length-count)+' riutilizzati · '+clipClock(data.duration)+' totali':'Seleziona almeno un clip';q('[type="submit"]').disabled=!count||!!busy?.();};
 function references(card,item){
  const host=card.querySelector('[data-references]');host.replaceChildren();
  for(const image of data.images){const button=document.createElement('button');button.type='button';button.className='video-edit-reference';button.setAttribute('aria-pressed',String(item.images.has(image.index)));button.innerHTML=`<img src="${esc(image.url)}" alt="" loading="lazy"><span>Picture ${image.index} · ${esc(image.name)}</span>`;
   button.onclick=()=>{if(item.images.has(image.index))item.images.delete(image.index);else{if(item.images.size>=9){error('Scegli fino a nove riferimenti per clip.');return;}item.images.add(image.index);}button.setAttribute('aria-pressed',String(item.images.has(image.index)));error('');};host.append(button);
  }
 }
 for(const clip of data.clips){
  const item={enabled:false,clip:clip.clip,prompt:'',images:new Set(clip.images),lip_sync:clip.lip_sync};draft.set(clip.clip,item);
  const card=document.createElement('article');card.className='video-edit-clip';card.innerHTML=`<div class="video-edit-clip-head"><label class="check"><input type="checkbox" data-enabled> Clip ${clip.clip} · ${clipClock(clip.start)}–${clipClock(clip.end)}</label><video controls playsinline preload="none" src="${esc(clip.url)}" aria-label="Anteprima clip ${clip.clip}"></video></div><div data-fields hidden><label class="field"><span>Cosa vuoi cambiare in questo clip?</span><textarea maxlength="6000" rows="3" placeholder="Ad esempio: primo piano del cantante, bocca sempre visibile, movimento lento della camera…" data-prompt></textarea></label><label class="check"><input type="checkbox" data-lipsync ${item.lip_sync?'checked':''}> Lip-sync sulle voci originali</label><details><summary>Riferimenti del clip · seleziona fino a 9 immagini</summary><div class="video-edit-references" data-references></div></details><details><summary>Regia precedente</summary><pre>${esc(clip.prompt)}</pre></details></div>`;
  q('.video-edit-clips').append(card);references(card,item);
  card.querySelector('[data-enabled]').onchange=e=>{item.enabled=e.target.checked;card.querySelector('[data-fields]').hidden=!item.enabled;card.classList.toggle('selected',item.enabled);summary();};
  card.querySelector('[data-prompt]').oninput=e=>{item.prompt=e.target.value;};card.querySelector('[data-lipsync]').onchange=e=>{item.lip_sync=e.target.checked;};
 }
 function addImages(items){for(const image of items){if(!image.mime?.startsWith('image/'))throw Error('Scegli immagini come nuovi riferimenti.');if(data.images.some(x=>x.id===image.id))continue;if(extra.length>=9)throw Error('Puoi aggiungere fino a nove nuove immagini.');extra.push(image);data.images.push({index:data.images.length+1,id:image.id,name:image.name,url:image.url||'/media/'+image.path});}for(const card of q('.video-edit-clips').children){const number=Number(card.querySelector('video').getAttribute('aria-label').match(/\d+$/)[0]);references(card,draft.get(number));}}
 q('[data-gallery]').onclick=()=>openGallery({api,kind:'image',onSelect:async items=>{try{addImages(items);error('');}catch(e){error(e.message);throw e;}}});
 q('[data-upload]').onclick=()=>q('[data-files]').click();
 q('[data-files]').onchange=async e=>{try{for(const file of e.target.files){if(file.size>25*1024*1024)throw Error('Ogni immagine può occupare al massimo 25 MB.');const dataUrl=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});const media=await api('/uploads',{name:file.name,data:String(dataUrl).split(',')[1]});addImages([media]);}error('');}catch(e){error(e.message);}finally{e.target.value='';}};
 dialog.querySelector('form').onsubmit=async event=>{event.preventDefault();const submit=q('[type="submit"]');submit.disabled=true;error('');try{if(busy?.())throw Error('Attendi o interrompi la tua richiesta in corso.');const patches=[...draft.values()].filter(x=>x.enabled).map(x=>({clip:x.clip,prompt:x.prompt,images:[...x.images],lip_sync:x.lip_sync}));if(!patches.length||patches.some(x=>!x.prompt.trim()))throw Error('Descrivi le modifiche di ogni clip selezionato.');const result=await api('/chats/'+chatId+'/video-edit',{source,patches,assistant:dialog.querySelector('[name="assistant"]').checked,media:extra.map(x=>({id:x.id}))});dialog.close();await onQueued?.(result);}catch(e){error(e.message);summary();}};
 dialog.showModal();summary();return dialog;
}
