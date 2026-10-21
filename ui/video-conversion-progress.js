export function videoConversionProgress(host,{api,path,label='Preparazione video…'}){
 const panel=document.createElement('div');panel.className='video-conversion-progress';panel.setAttribute('role','status');panel.setAttribute('aria-live','polite');panel.setAttribute('aria-busy','true');
 const title=document.createElement('strong'),bar=document.createElement('progress'),detail=document.createElement('span');
 title.textContent=label;bar.max=100;bar.setAttribute('aria-label','Avanzamento della fase di conversione');panel.append(title,bar,detail);host.append(panel);
 const started=Date.now(),clock=performance.now();let stopped=false,timer,phase=null;
 const render=()=>{
  if(stopped)return;
  title.textContent=phase?.stage||label;
  const percent=phase?.percent;
  if(Number.isFinite(percent)){bar.value=percent;}else bar.removeAttribute('value');
  const elapsed=Math.floor((performance.now()-clock)/1000);
  detail.textContent=(Number.isFinite(percent)?`${Math.round(percent)}% della fase · `:'')+'Tempo trascorso '+Math.floor(elapsed/60)+':'+String(elapsed%60).padStart(2,'0');
 };
 const poll=async()=>{
  try{const value=await api(path);if(!stopped&&value.updated_at*1000>=started){phase=value;render();}}catch{} // Older engines still show elapsed time and an indeterminate bar.
  if(!stopped)timer=setTimeout(poll,750);
 };
 render();poll();const ticker=setInterval(()=>{if(!panel.isConnected){stop();return;}render();},1000);
 function stop(){stopped=true;clearTimeout(timer);clearInterval(ticker);panel.remove();}
 return {stop};
}
