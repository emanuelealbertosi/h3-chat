import {videoConversionProgress} from './video-conversion-progress.js';

export function addBrowserPreview(host,video,media,api){
 if(!api||!media?.id)return;
 const unsupported=/\.(mov|mkv|avi|mxf|wmv)(?:$|\?)/i.test(media.path||media.url||'');
 const button=document.createElement('button');button.type='button';button.className='text-button video-compatible-preview';button.textContent='Prepara anteprima compatibile';button.hidden=!unsupported;host.append(button);
 video.addEventListener('error',()=>{button.hidden=false;},{once:true});
 button.onclick=async()=>{button.disabled=true;button.textContent='Preparazione anteprima su CPU…';const progress=videoConversionProgress(host,{api,path:'/gallery/'+media.id+'/preview-progress',label:'Conversione anteprima compatibile…'});try{const time=video.currentTime||0,result=await api('/gallery/'+media.id+'/preview',{});video.src=result.url;video.dataset.previewSrc=result.url;video.addEventListener('loadedmetadata',()=>{video.currentTime=time;},{once:true});video.load();button.remove();}catch(e){button.textContent=e.message+' · Riprova';button.disabled=false;}finally{progress.stop();}};
}
