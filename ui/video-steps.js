export function videoStepButtons(value,{preset=false,disabled=false}={}){
 const values=preset?['',12,16,20]:[12,16,20];
 return `<div class="prompt-choices" role="group" aria-label="Passi">${values.map(n=>`<button type="button" class="prompt-choice" data-video-step="${n}" aria-pressed="${String(value??'')===String(n)}" ${disabled?'disabled':''}>${n===''?'Preset del modello':n}</button>`).join('')}</div>`;
}

export function bindVideoSteps(host,input){
 const buttons=[...host.querySelectorAll('[data-video-step]')];
 const sync=()=>{for(const button of buttons)button.setAttribute('aria-pressed',String(button.dataset.videoStep===input.value));};
 for(const button of buttons)button.onclick=()=>{input.value=button.dataset.videoStep;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));sync();};
 input.addEventListener('input',sync);sync();
}
