import {escape as esc} from './render.js';

// null means no request override; model presets may still specify a limit.
export function durationField(value,scope){
 return `<section class="prompt-field"><label class="mtp-toggle"><input type="checkbox" data-duration-enable="${scope}" ${value!=null?'checked':''}> ${scope==='chat'?'Imposta durata massima per questa richiesta':'Limita la durata per questo modello'}</label><label class="field"><span>Durata massima · secondi (max_duration)</span><input type="number" min="0.04" max="900" step="0.04" data-duration-seconds="${scope}" value="${esc(String(value??360))}" ${value==null?'disabled':''}></label><p class="small-note">Opzionale, da 0,04 a 900 secondi. È un limite di generazione: il brano può terminare prima. Non modifica Style Prompt o Lyrics. Senza limite restano i token audio impostati.</p></section>`;
}

export function bindDuration(container,scope,changed){
 const toggle=container.querySelector(`[data-duration-enable="${scope}"]`),input=container.querySelector(`[data-duration-seconds="${scope}"]`);
 toggle.onchange=()=>{input.disabled=!toggle.checked;changed(toggle.checked?Number(input.value):null);};
 input.oninput=()=>{if(toggle.checked)changed(Number(input.value));};
}

export function initMusicDuration({read,save,getState}){
 const holder=document.querySelector('#music-inputs'),section=document.createElement('div');
 section.innerHTML=durationField(read().music_max_duration,'chat')+'<p class="small-note" data-duration-inherit></p>';holder.prepend(section);
 bindDuration(section,'chat',value=>save({...read(),music_max_duration:value}));
 return {render(){
  const value=read().music_max_duration??null,input=section.querySelector('[data-duration-seconds]');
  section.querySelector('[data-duration-enable]').checked=value!=null;input.disabled=value==null;
  if(value!=null&&document.activeElement!==input)input.value=value;
  const settings=getState()?.settings||{},quality=read().music_quality||settings.music_quality;
  const model=settings.music_quality_profiles?.[quality]?.model||settings.music_model;
  const inherited=settings.music_overrides?.[model]?.max_duration;
  section.querySelector('[data-duration-inherit]').textContent=value==null&&inherited!=null?`Il preset del modello applica una durata massima di ${inherited} s.`:'';
 }};
}
