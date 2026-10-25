import {openImageZoom} from './image-zoom.js';

// Background batches have their own contact sheet; ordinary image batches keep their viewer.
export function appendBackgroundGrid(target,media,{preview=false}={}){
 const grid=document.createElement('div');grid.className='background-grid';grid.setAttribute('aria-label','Sfondi creati');
 for(const item of media){
  const figure=document.createElement('figure'),button=document.createElement('button'),image=document.createElement('img'),caption=document.createElement('figcaption'),download=document.createElement('a');
  button.type='button';button.className='background-thumbnail';button.setAttribute('aria-label','Ingrandisci '+item.name);
  image.src='/media/'+item.path;image.alt=item.name;image.loading='lazy';button.append(image);
  const opts=item.slide_background||{};button.style.aspectRatio=(opts.format||'16:9').replace(':',' / ');
  if(preview){
   const veil=document.createElement('span'),sample=document.createElement('span');veil.className='background-veil';veil.style.background=opts.tone==='dark'?'#111827':'#ffffff';veil.style.opacity=String(1-(opts.opacity||20)/100);
   sample.className='background-safe-area';sample.style.inset=(opts.margin||12)+'%';sample.style.color=opts.tone==='dark'?'#ffffff':'#17212b';sample.textContent='Titolo e contenuti';button.append(veil,sample);
  }
  button.onclick=()=>openImageZoom('/media/'+item.path,item.name,button);
  const name=document.createElement('span');name.textContent=item.name;download.href='/media/'+item.path;download.download='';download.textContent='Scarica';
  const details=document.createElement('small'),g=item.generation||{};details.textContent=[g.seed!==undefined?'Seed '+g.seed:'',g.width&&g.height?g.width+' × '+g.height:''].filter(Boolean).join(' · ');
  caption.append(name,details,download);figure.append(button,caption);grid.append(figure);
 }
 target.append(grid);return grid;
}
