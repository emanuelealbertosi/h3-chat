export function memoryPatch(item,supported){
 return supported?{recover_memory:!!item.recover_memory&&item.clip>1&&item.mode==='reference'&&!item.range}:{};
}

export function endFramePatch(item,supported){
 return supported?{end_frame:item.mode==='reference'&&!item.range?(item.end_frame??'none'):'none'}:{};
}

export function mountEditEndFrame(card,item,clip,data){
 const host=document.createElement('section');host.className='video-edit-end-frame';
 host.innerHTML='<label class="field"><span>Fotogramma finale per il raccordo</span><select data-end-frame aria-label="Fotogramma finale per il raccordo"></select></label><p class="small-note" data-end-frame-info></p>';
 card.querySelector('.video-edit-memory').after(host);
 const select=host.querySelector('select'),note=host.querySelector('p');
 function refresh(){
  const options=[['none','Finale libero'],['original','Finale attuale della clip'],['next','Primo fotogramma della clip successiva'],...data.images.map(i=>[String(i.index),'Immagine '+i.index+' · '+i.name])];
  select.replaceChildren();for(const [value,label] of options){const option=document.createElement('option');option.value=value;option.textContent=label;option.disabled=value==='next'&&clip.clip===data.clips.at(-1)?.clip;select.append(option);}
  const reason=!data.end_frame_recovery?'Disponibile dopo l’aggiornamento del motore.':item.mode!=='reference'?'Disponibile in Rigenera · riferimenti. In Modifica video usa Fotogrammi guida.':item.range?'Seleziona Intera clip per usare questo raccordo finale.':'';
  select.disabled=!!reason;select.value=String(item.end_frame??'none');
  const capacityNote=(item.end_frame==='original'||item.end_frame==='next')&&item.images.size>=9?'Libera un posto immagine: il fotogramma finale richiede uno dei nove riferimenti. ':'';
  note.textContent=reason||capacityNote+'Puoi usarlo insieme alla memoria precedente. Il modello parte dal raccordo iniziale e cerca di arrivare a questa immagine: non è un blocco pixel per pixel. Il finale attuale conserva anche vestiti e dettagli presenti in quel fotogramma. Per usare un’altra immagine, caricala e selezionala qui.';
 }
 select.onchange=()=>{item.end_frame=/^\d+$/.test(select.value)?Number(select.value):select.value;refresh();};refresh();return refresh;
}

export function mountEditMemory(card,item,clip,supported){
 const host=document.createElement('section');host.className='video-edit-memory';
 host.innerHTML='<label class="check"><input type="checkbox" data-recover-memory> Recupera memoria dalle clip precedenti</label><p class="small-note" data-memory-info></p>';
 card.querySelector('[data-image-mode-info]').after(host);
 const input=host.querySelector('input'),note=host.querySelector('[data-memory-info]');
 function refresh(){
  const reason=!supported?'Disponibile dopo l’aggiornamento del motore.':item.clip===1?'La prima clip non ha clip precedenti.':item.mode!=='reference'?'Disponibile in Rigenera · riferimenti. Modifica video e I2V usano le proprie guide.':item.range?'Seleziona Intera clip. Per modificare soltanto un tratto usa i fotogrammi guida.':'';
  input.disabled=!!reason;input.checked=!reason&&!!item.recover_memory;
  note.textContent=reason||((clip.memory?.cut?'Questa clip iniziava con uno stacco: attiva solo se vuoi collegarla alla precedente. ':'')+'Recupera l’apertura della sequenza e le ultime due clip disponibili, nelle versioni scelte in timeline. L’inizio viene guidato dal finale precedente; il finale della nuova clip resta libero. Può influenzare anche pose e vestiti.');
 }
 input.onchange=()=>{item.recover_memory=input.checked;refresh();};refresh();return refresh;
}
