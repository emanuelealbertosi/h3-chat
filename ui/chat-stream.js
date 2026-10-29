// Smooth only text already received. No invented tokens or long final replay.
export function createChatStream({read,render,onProgress=()=>{},now=()=>performance.now(),frame=requestAnimationFrame,cancelFrame=cancelAnimationFrame,timer=setTimeout,cancelTimer=clearTimeout,reducedMotion=()=>matchMedia('(prefers-reduced-motion: reduce)').matches}){
 const entries=new Map();
 function stop(key){const e=entries.get(key);if(!e)return;e.closed=true;cancelFrame(e.frame);cancelTimer(e.timer);entries.delete(key);}
 function paint(e){if(e.closed||!e.container?.isConnected||e.busy)return;e.busy=true;const container=e.container,text=e.shown,version=e.version;
  Promise.resolve(render(container,text,e.options)).catch(()=>{}).finally(()=>{e.busy=false;if(!e.closed){onProgress();if(e.container!==container||e.shown!==text||e.version!==version)paint(e);}});
 }
 function schedule(e){if(e.frame||e.closed||e.shown===e.target)return;e.frame=frame(stamp=>{e.frame=0;if(e.closed)return;const elapsed=Math.max(1,Math.min(50,stamp-e.lastFrame||16));e.lastFrame=stamp;
   const backlog=e.target.length-e.shown.length;let count=reducedMotion()?backlog:Math.max(1,Math.ceil(Math.max(e.rate,backlog/0.28)*elapsed/1000));count=Math.min(backlog,count);
   let end=e.shown.length+count;
   // Never split a UTF-16 surrogate pair while revealing emoji/non-BMP text.
   if(end<e.target.length&&end>0&&/[\uD800-\uDBFF]/.test(e.target[end-1]))end++;
   e.shown=e.target.slice(0,end);paint(e);schedule(e);
  });}
 function receive(e,text){if(e.closed||typeof text!=='string'||text===e.target)return;
  if(e.target.startsWith(text))return; // An older full-chat poll arrived late.
  const stamp=now(),delta=text.length-e.target.length,elapsed=Math.max(50,stamp-e.receivedAt);
  if(text.startsWith(e.target)){e.rate=Math.max(25,Math.min(1500,e.rate*.5+delta/(elapsed/1000)*.5));}
  else{e.shown='';e.rate=80;}
  e.target=text;e.receivedAt=stamp;schedule(e);
 }
 async function poll(e){if(e.closed||!e.live)return;
  try{const value=await read(e.chat,e.id);if(e.closed)return;receive(e,value.content);if(!['queued','running'].includes(value.status)){e.shown=e.target;paint(e);e.live=false;return;}}
  catch{e.live=false;return;} // Ordinary refresh remains the fallback.
  if(!e.closed)e.timer=timer(()=>poll(e),140);
 }
 return {bind({chat,id,container,text,options={},live=true}){const key=chat+':'+id;let e=entries.get(key);
   if(!e){e={chat,id,container,options,target:text||'',shown:text||'',rate:80,lastFrame:now(),receivedAt:now(),frame:0,timer:0,closed:false,busy:false,live,version:0};entries.set(key,e);paint(e);if(live)poll(e);}
   else{e.container=container;e.options=options;e.version++;receive(e,text||'');paint(e);schedule(e);}
   return key;
  },retain(keys){for(const key of entries.keys())if(!keys.has(key))stop(key);},clear(){for(const key of [...entries.keys()])stop(key);}};
}
