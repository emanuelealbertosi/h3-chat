// Media and rich content can grow after renderChat resolves. Follow their actual
// layout while opening a chat, until the reader deliberately scrolls away.
export function initChatScroll(scroll,content){
 let following=false,frame=0,touchY=null,lastTop=scroll.scrollTop;
 const nearBottom=()=>scroll.scrollHeight-scroll.scrollTop-scroll.clientHeight<8;
 const schedule=()=>{if(!following||frame)return;frame=requestAnimationFrame(()=>{frame=0;if(following)scroll.scrollTop=scroll.scrollHeight;});};
 const stop=()=>{following=false;lastTop=scroll.scrollTop;cancelAnimationFrame(frame);frame=0;};
 const resize=new ResizeObserver(schedule);resize.observe(content);resize.observe(scroll);
 const abort=new AbortController(),options={passive:true,signal:abort.signal};
 scroll.addEventListener('wheel',event=>{if(event.deltaY<0)stop();},options);
 scroll.addEventListener('touchstart',event=>{touchY=event.touches[0]?.clientY??null;},options);
 scroll.addEventListener('touchmove',event=>{const y=event.touches[0]?.clientY;if(touchY!==null&&y>touchY)stop();touchY=y??null;},options);
 scroll.addEventListener('pointerdown',event=>{if(event.target===scroll)stop();},options);
 scroll.addEventListener('keydown',event=>{if(['ArrowUp','PageUp','Home'].includes(event.key)||(event.key===' '&&event.shiftKey))stop();},{signal:abort.signal});
 scroll.addEventListener('scroll',()=>{const top=scroll.scrollTop;if(!following&&top>lastTop&&nearBottom())following=true;lastTop=top;},options);
 return {begin(){following=true;schedule();},update(){schedule();},
  dispose(){stop();resize.disconnect();abort.abort();}};
}
