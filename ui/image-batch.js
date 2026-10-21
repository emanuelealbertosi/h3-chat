import {openImageZoom} from './image-zoom.js';

const selections=new Map();
const viewers=new Set();
function select(key,index){
  selections.set(key,index);
  for(const view of viewers){if(!view.host.isConnected)viewers.delete(view);else if(view.key===key)view.show(index);}
}

export function appendImageBatch(target,media){
  if(!media?.length||!media.every(m=>m.batch_id&&m.mime?.startsWith('image/'))||new Set(media.map(m=>m.batch_id)).size!==1)return false;
  const images=[...media].sort((a,b)=>a.batch_index-b.batch_index),key=images[0].batch_id;
  const host=document.createElement('figure');host.className='image-batch image-output';host.dataset.batchId=key;
  const main=document.createElement('button');main.type='button';main.className='image-zoom-trigger';
  const image=document.createElement('img');image.loading='lazy';main.append(image);
  const caption=document.createElement('figcaption'),name=document.createElement('span'),download=document.createElement('a'),details=document.createElement('small');
  download.textContent='Scarica originale';download.download='';details.className='image-batch-details';caption.append(name,download,details);
  const strip=document.createElement('div');strip.className='image-batch-thumbnails';strip.setAttribute('role','group');strip.setAttribute('aria-label','Immagini del lotto');
  const thumbs=images.map(m=>{
    const button=document.createElement('button');button.type='button';button.className='image-batch-thumbnail';
    button.setAttribute('aria-label','Mostra immagine '+m.batch_index);button.title=m.name;
    const thumbnail=document.createElement('img');thumbnail.src='/media/'+m.path;thumbnail.alt='';thumbnail.loading='lazy';
    const label=document.createElement('span');label.textContent=String(m.batch_index);button.append(thumbnail,label);
    button.onclick=()=>select(key,m.batch_index);strip.append(button);return button;
  });
  function show(index){
    const chosen=images.find(m=>m.batch_index===index)||images[0];selections.set(key,chosen.batch_index);
    image.src='/media/'+chosen.path;image.alt=chosen.name;main.setAttribute('aria-label','Ingrandisci '+chosen.name);
    main.onclick=()=>openImageZoom('/media/'+chosen.path,chosen.name,main);
    name.textContent=chosen.batch_index+'/'+chosen.batch_total+' · '+chosen.name+' ';download.href='/media/'+chosen.path;
    const p=chosen.generation||{};details.textContent=[p.width&&p.height?p.width+' × '+p.height:null,p.seed!==undefined?'Seed '+p.seed:null,p.steps?'Passi '+p.steps:null].filter(Boolean).join(' · ');
    thumbs.forEach((b,i)=>b.setAttribute('aria-pressed',String(images[i]===chosen)));
  }
  host.append(main,caption,strip);target.append(host);
  for(const view of viewers)if(!view.host.isConnected)viewers.delete(view);
  viewers.add({host,key,show});show(selections.get(key));return true;
}
