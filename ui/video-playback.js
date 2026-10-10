export function addVideoAudioControl(figure){
 const video=figure.querySelector('video'),caption=figure.querySelector('figcaption');
 const button=document.createElement('button');button.type='button';button.className='text-button no-export';button.textContent='🔊 Riproduci con audio';
 button.onclick=async()=>{
  caption.querySelector('.video-playback-error')?.remove();video.muted=false;video.volume=1;
  try{await video.play();}catch(error){const notice=document.createElement('span');notice.className='video-playback-error render-error';notice.setAttribute('role','alert');notice.textContent='Riproduzione non riuscita: '+error.message;caption.append(notice);}
 };caption.prepend(button);button.style.marginRight='12px';
}
