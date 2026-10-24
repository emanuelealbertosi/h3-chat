export const slideBackgrounds={auto:'Automatico',light:'Chiaro',dark:'Scuro',custom:'Personalizzato'};
export const slideTextTones={auto:'Automatici',light:'Chiari',dark:'Scuri'};
export const slidePalettes={auto:'Automatica',natural:'Naturale',pastel:'Pastello',vivid:'Vivace',neon:'Neon',monochrome:'Monocromatica'};

export function initSlideColors(){
 const holder=document.querySelector('#slides-options');
 const choices=items=>Object.entries(items).map(([value,label])=>`<option value="${value}">${label}</option>`).join('');
 holder.insertAdjacentHTML('beforeend',`<label>Sfondo <select id="slides-background" aria-label="Sfondo delle slide">${choices(slideBackgrounds)}</select></label> <label id="slides-background-color-label" hidden>Colore di sfondo <input id="slides-background-color" aria-label="Colore di sfondo delle slide" type="color" value="#f7f3e8"></label> <label>Testi <select id="slides-text-tone" aria-label="Colore dei testi delle slide">${choices(slideTextTones)}</select></label> <label>Palette <select id="slides-palette" aria-label="Palette delle slide">${choices(slidePalettes)}</select></label><p class="small-note" id="slides-colors-note">Automatico lascia scegliere i colori all’LLM. Puoi specificarli anche nel prompt.</p>`);
 const background=document.querySelector('#slides-background'),palette=document.querySelector('#slides-palette'),tone=document.querySelector('#slides-text-tone'),color=document.querySelector('#slides-background-color'),engine=document.querySelector('#slides-engine');
 const update=()=>{
  const enabled=engine.value==='llm';background.disabled=palette.disabled=color.disabled=tone.disabled=!enabled;
  document.querySelector('#slides-background-color-label').hidden=!enabled||background.value!=='custom';
  document.querySelector('#slides-colors-note').textContent=enabled?'Automatico lascia scegliere i colori all’LLM. Le indicazioni esplicite nel prompt hanno precedenza.':'Sfondo, testi e palette sono disponibili con il motore LLM · HTML libero. Il motore deterministico usa i suoi temi.';
 };
 engine.addEventListener('change',update);background.addEventListener('change',update);update();
 return {read:()=>engine.value==='llm'?{background:background.value,palette:palette.value,text_tone:tone.value,...(background.value==='custom'?{background_color:color.value}:{})}:{}};
}
