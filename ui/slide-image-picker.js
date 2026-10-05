export function imagePicker(target,{api,chatId,media,onSelect}){
  const panel=document.createElement('section');panel.className='no-export slide-image-picker';
  panel.innerHTML='<strong>Immagini della slide</strong> <button type="button" data-pc>Dal PC</button> <button type="button" data-existing>Allegati</button> <button type="button" data-rag>Dal RAG</button> <button type="button" data-web>Internet</button><label><input data-query placeholder="Cerca una figura o un documento"><button type="button" data-search>Cerca</button></label><input data-file type="file" accept="image/*" hidden><p data-status></p><div data-results style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px"></div><button data-more hidden>Altre immagini</button>';
  target.append(panel);const q=s=>panel.querySelector(s);let source='existing',offset=0,busy=false;
  const run=fn=>async()=>{if(busy)return;busy=true;q('[data-status]').textContent='Caricamento immagini…';try{await fn();q('[data-status]').textContent='';}catch(e){q('[data-status]').textContent=e.message;}finally{busy=false;}};
  const choose=async item=>{const selected=source==='existing'?item:await api('/slides/images/import',{chat_id:chatId,source,...item});await onSelect(selected);};
  function show(items,append=false){
    const results=q('[data-results]');if(!append)results.replaceChildren();
    for(const item of items){const b=document.createElement('button');b.type='button';b.style.cssText='display:flex;flex-direction:column;gap:6px;text-align:left;';
      const image=document.createElement('img');image.src=item.thumbnail||(item.path?'/media/'+item.path:'');image.style.cssText='width:100%;height:100px;object-fit:contain';const label=document.createElement('span');label.textContent=item.name;const credit=document.createElement('small');credit.textContent=[item.credit,item.license].filter(Boolean).join(' · ');b.append(image,label,credit);b.onclick=run(()=>choose(item));results.append(b);
    }
    if(!items.length&&!append)q('[data-status]').textContent=source==='rag'?'Nessuna figura indicizzata nel progetto della chat per questa ricerca.':'Nessuna immagine trovata.';
  }
  const search=async append=>{
    if(source==='existing'){show(media.filter(m=>m.mime.startsWith('image/')));return;}
    if(!append)offset=0;const data=await api('/slides/images/'+(source==='web'?'search':'rag'),{chat_id:chatId,query:q('[data-query]').value,offset});
    show(data.items,append);q('[data-more]').hidden=!data.more;offset+=24;
    if(source==='web')q('[data-status]').textContent='Risultati da Wikimedia Commons · autore e licenza conservati.';
  };
  q('[data-existing]').onclick=run(async()=>{source='existing';q('[data-more]').hidden=true;await search(false);});
  q('[data-rag]').onclick=run(async()=>{source='rag';await search(false);});
  q('[data-web]').onclick=()=>{source='web';q('[data-results]').replaceChildren();q('[data-more]').hidden=true;q('[data-status]').textContent='Scrivi cosa cercare su Wikimedia Commons e premi Cerca.';q('[data-query]').focus();};
  q('[data-search]').onclick=run(()=>search(false));q('[data-more]').onclick=run(()=>search(true));
  q('[data-query]').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();q('[data-search]').click();}};
  q('[data-pc]').onclick=()=>q('[data-file]').click();q('[data-file]').onchange=run(async()=>{
    const file=q('[data-file]').files[0];if(!file)return;if(file.size>12*1024**2)throw Error('Scegli un’immagine entro 12 MB.');
    const bitmap=await createImageBitmap(file),canvas=document.createElement('canvas'),scale=Math.min(1,4096/Math.max(bitmap.width,bitmap.height));canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();
    const data=canvas.toDataURL('image/png').split(',')[1],asset=await api('/uploads',{name:file.name,data});await onSelect(asset);
  });
}
