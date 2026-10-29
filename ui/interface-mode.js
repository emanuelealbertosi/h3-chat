// Presentation only: never changes engine settings, grants or running work.
export function initInterfaceMode({onBasic=()=>{}}={}){
 const key='h3-interface-mode';let mode='advanced';
 try{if(localStorage.getItem(key)==='basic')mode='basic';}catch{}
 const holder=document.querySelector('.top-actions');if(!holder)return;
 const group=document.createElement('div');group.id='interface-mode';group.className='segmented interface-mode';group.setAttribute('role','group');group.ariaLabel='Interfaccia Basic o Advanced';
 for(const [value,label] of [['basic','Basic'],['advanced','Advanced']]){
  const button=document.createElement('button');button.type='button';button.textContent=label;button.dataset.interfaceMode=value;
  button.title=value==='basic'?'Solo gli strumenti essenziali. Le impostazioni salvate restano valide.':'Mostra Agente, modelli e impostazioni tecniche';
  button.onclick=()=>{if(mode===value)return;mode=value;try{localStorage.setItem(key,mode);}catch{}if(mode==='basic')onBasic();render();};group.append(button);
 }
 holder.prepend(group);
 function render(){document.body.dataset.interfaceMode=mode;for(const button of group.children)button.setAttribute('aria-pressed',String(button.dataset.interfaceMode===mode));}
 if(mode==='basic')onBasic();render();
 return {getMode:()=>mode};
}
