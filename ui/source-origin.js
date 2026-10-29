export function sourceOriginButton(api,project,source,notify=()=>{}){
 const b=document.createElement('button');b.type='button';b.className='btn small no-export';b.textContent='Apri media originale';
 b.onclick=async()=>{b.disabled=true;try{const result=await api(`/projects/${project}/sources/${source.source_id}/origin`);if(!result.media)throw Error('Il media originale non è più disponibile. La trascrizione resta consultabile.');
  const m=result.media;if(!/^(audio|video)\//.test(m.mime)||! /^(uploads|outputs)\/[\w./-]+$/.test(m.path)||m.path.split('/').includes('..'))throw Error('Riferimento media non valido.');
  const d=document.createElement('dialog');d.style.cssText='max-width:90vw;border:1px solid #ddd;border-radius:12px;padding:20px';const title=document.createElement('h3');title.textContent=m.name;const player=document.createElement(m.mime.startsWith('video/')?'video':'audio');player.controls=true;player.style.maxWidth='80vw';player.src='/media/'+m.path;
  const stamp=/\[(\d+(?:\.\d+)?)(?:[–-]|\s*s\])/.exec(source.text||'');if(stamp)player.addEventListener('loadedmetadata',()=>{player.currentTime=Number(stamp[1]);},{once:true});
  const close=document.createElement('button');close.type='button';close.className='btn';close.textContent='Chiudi';close.onclick=()=>d.close();d.append(title,player,close);d.addEventListener('close',()=>{player.pause();d.remove();});document.body.append(d);d.showModal();
 }catch(e){notify(e.message,true);}finally{b.disabled=false;}};return b;
}
