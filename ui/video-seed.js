import {escape as esc} from './render.js';

// A request seed is a policy (-1) or a fixed integer, never a preset mutation.
export function videoSeed(host,{label='Seed video',initial,preset=-1,original=false,onChange,referenceSeed}={}){
 const section=document.createElement('section');section.className='video-seed-options';
 section.innerHTML=`<span class="prompt-field-label">${esc(label)}</span><div class="prompt-choices" role="group" aria-label="${esc(label)}"><button type="button" class="prompt-choice" data-seed-mode="default">${original?'Conserva originali':'Preset del modello'}</button><button type="button" class="prompt-choice" data-seed-mode="random">Casuale · nuova variante</button><button type="button" class="prompt-choice" data-seed-mode="fixed">Fisso</button></div><label class="field" data-seed-fixed hidden><span>Numero del seed</span><input name="seed" type="number" min="0" max="2147483647" step="1" aria-label="${esc(label)} fisso"></label><p class="small-note" data-seed-note></p>`;
 host.append(section);const input=section.querySelector('input'),note=section.querySelector('[data-seed-note]');
 let mode='default',disabled=false,external=Symbol('initial'),disabledNote='';
 const valid=n=>Number.isInteger(n)&&n>=0&&n<=2147483647;
 const reference=document.createElement('button');reference.type='button';reference.className='btn small';reference.dataset.firstClipSeed='';reference.textContent='Usa seed della prima clip';
 reference.hidden=!valid(referenceSeed?.());section.querySelector('.prompt-choices').after(reference);
 reference.onclick=()=>{const number=referenceSeed?.();if(!disabled&&valid(number)){mode='fixed';input.value=String(number);emit();}};
 input.value=String(valid(preset)?preset:0);
 function read(){
  if(mode==='default')return undefined;if(mode==='random')return -1;
  const number=Number(input.value);if(input.value.trim()===''||!valid(number))throw Error('Seed: scegli un intero da 0 a 2147483647.');
  return number;
 }
 function render(){
  for(const button of section.querySelectorAll('[data-seed-mode]')){button.disabled=disabled;button.setAttribute('aria-pressed',String(button.dataset.seedMode===mode));}
  reference.disabled=disabled;reference.hidden=!valid(referenceSeed?.());
  section.querySelector('[data-seed-fixed]').hidden=mode!=='fixed';input.disabled=disabled||mode!=='fixed';input.required=mode==='fixed'&&!disabled;
  let error='';try{read();}catch(e){error=e.message;}
  input.setCustomValidity(error);input.setAttribute('aria-invalid',String(!!error));
  section.querySelector('[data-seed-mode="default"]').textContent=original?'Conserva originali':valid(preset)?'Preset · seed '+preset:'Preset · casuale';
  note.textContent=disabled?disabledNote:error||(mode==='random'?'Ogni clip riceve un nuovo seed a ogni lancio. Prompt, riferimenti e impostazioni restano quelli scelti.':mode==='fixed'?'Tutte le clip selezionate usano questo seed. Non garantisce la stessa identità o lo stesso stile su scene diverse.':original?'Ogni clip mantiene il suo seed originale.':'Usa il seed configurato per il modello.');
 }
 function emit(){render();try{const value=read();external=value;onChange?.(value);}catch{}}
 for(const button of section.querySelectorAll('[data-seed-mode]'))button.onclick=()=>{mode=button.dataset.seedMode;emit();};
 input.oninput=emit;
 const api={element:section,read,validate(){if(!disabled)read();},set(value,nextPreset=preset,blocked=false,message=''){
  preset=nextPreset;disabled=blocked;disabledNote=message;
  if(value!==external){external=value;mode=value==null?'default':value===-1?'random':'fixed';if(mode==='fixed')input.value=String(value);}
  render();
 },setPreset(value){preset=value;render();}};
 api.set(initial);return api;
}
