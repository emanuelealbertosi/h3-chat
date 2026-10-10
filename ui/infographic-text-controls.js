// Shared by the prompt modal and the canvas: one set of saved text options.
export const textChoices={
 text_motion:[['auto','Automatico'],['fade','Dissolvenza'],['slide','Scorrimento'],['bump','Bump · rimbalzo'],['typewriter','Carattere per carattere'],['drop','Lettere in caduta · 3D'],['wave','Onda di lettere'],['flip','Rotazione · 3D']],
 text_direction:[['auto','Automatica'],['left','Da sinistra'],['right','Da destra'],['up','Dall’alto'],['down','Dal basso']],
 text_speed:[['auto','Dal modello'],['slow','Lenta'],['normal','Normale'],['fast','Veloce']],
 text_look:[['auto','Dal modello'],['plain','Pulito'],['neon','Neon'],['outline','Contorno']],
 text_color:[['auto','Dal modello'],['custom','Colore scelto'],['cycle','Cambia colore']],
 text_scope:[['headings','Titoli e parole chiave'],['all','Tutti i testi']]
};
const labels={text_motion:'Comparsa delle scritte',text_direction:'Direzione dello scorrimento',text_speed:'Velocità di comparsa',text_look:'Aspetto',text_color:'Colore',text_scope:'Applica a'};
export const effectLabels={fade:'Dissolvenza',slide:'Scorrimento',zoom:'Zoom',pan:'Panoramica',blur:'Sfocatura',wipe:'Tendina',strobe:'Strobo',typewriter:'Carattere per carattere',appear:'Comparsa',bump:'Bump · rimbalzo',drop:'Lettere in caduta · 3D',wave:'Onda di lettere',flip:'Rotazione · 3D'};
export function textControls(parent,value={},disabled=false){
 const section=document.createElement('section');section.className='infographic-advanced';section.dataset.textControls='';
 section.innerHTML='<h3 class="prompt-settings-heading">Scritte ed effetti</h3><p class="small-note">Automatico lascia la regia al modello e al prompt. Una scelta esplicita applica lo stesso effetto ai testi selezionati, conservando i tempi di ingresso e uscita. La velocità riguarda le scritte, non la voce.</p>';
 const selected={};
 for(const [key,items] of Object.entries(textChoices)){
  selected[key]=value[key]||items[0][0];const field=document.createElement('div');field.className='prompt-field';field.dataset.infographicField=key;
  const label=document.createElement('span');label.className='prompt-field-label';label.textContent=labels[key];
  const group=document.createElement('div');group.className='prompt-choices';group.setAttribute('aria-label',labels[key]);
  for(const [id,text] of items){const b=document.createElement('button');b.type='button';b.className='prompt-choice';b.textContent=text;b.dataset.value=id;b.disabled=disabled;b.setAttribute('aria-pressed',String(id===selected[key]));b.onclick=()=>{selected[key]=id;for(const other of group.children)other.setAttribute('aria-pressed',String(other===b));refresh();};group.append(b);}
  field.append(label,group);section.append(field);
 }
 const colors=document.createElement('div');colors.className='settings-grid';
 for(const [key,label,fallback] of [['text_primary','Colore del testo','#ffffff'],['text_accent','Secondo colore / luce neon','#00e5ff']]){
  const field=document.createElement('label');field.className='field';const title=document.createElement('span');title.textContent=label;const input=document.createElement('input');input.type='color';input.dataset.info=key;input.value=value[key]||fallback;input.setAttribute('aria-label',label);field.append(title,input);colors.append(field);
 }
 section.append(colors);parent.append(section);
 function refresh(){section.querySelector('[data-infographic-field="text_direction"]').hidden=selected.text_motion!=='slide';colors.querySelector('[data-info="text_primary"]').disabled=disabled||selected.text_color==='auto';colors.querySelector('[data-info="text_accent"]').disabled=disabled||(selected.text_color!=='cycle'&&!['neon','outline'].includes(selected.text_look));}
 refresh();
 return {section,read:()=>({...selected,...Object.fromEntries([...colors.querySelectorAll('input')].map(e=>[e.dataset.info,e.value]))})};
}
