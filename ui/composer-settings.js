const $=selector=>document.querySelector(selector);
const selected=selector=>$(selector)?.selectedOptions?.[0]?.textContent?.trim()||'';
const chosen=selector=>$(selector)?.querySelector('[aria-pressed="true"]')?.textContent?.trim()||'';

// Keep the original controls, values and handlers inside a dedicated dialog.
export function initComposerSettings({context,getState,onChange}){
 const dialog=document.createElement('dialog');dialog.id='prompt-mode-settings';dialog.className='prompt-options-dialog prompt-mode-dialog';dialog.setAttribute('aria-labelledby','prompt-mode-title');
 dialog.innerHTML='<header><div><span class="eyebrow">DAL PROSSIMO MESSAGGIO</span><h2 id="prompt-mode-title">Impostazioni</h2></div><button type="button" class="icon-button" aria-label="Chiudi impostazioni della modalità">×</button></header><nav class="prompt-mode-tabs" aria-label="Impostazioni delle modalità attive"></nav><div class="prompt-options-body"></div><footer><span class="small-note">Le scelte restano impostate anche chiudendo la finestra.</span><button type="button" class="btn primary">Fatto</button></footer>';
 document.body.append(dialog);
 const body=dialog.querySelector('.prompt-options-body'),tabs=dialog.querySelector('nav'),entries=[];
 let current=null,opener=null;
 const definitions=[
  ['prompt-image-panel','Immagini',()=>selected('#image-model')],
  ['slides-options','Slide',()=>[$('#slides-count')?.value+' slide',selected('#slides-format'),selected('#slides-design'),selected('#slides-detail'),$('#slides-generate-images')?.checked?'Illustrazioni AI':''].filter(Boolean).join(' · ')],
  ['music-inputs','Music',()=>[$('#music-inputs [data-music-field="instrumental"]')?.checked?'Strumentale':'Con voce',$('#music-inputs [data-music-field="title"]')?.value,$('#music-inputs [data-music-field="style"]')?.value?.slice(0,100)].filter(Boolean).join(' · ')],
  ['voice-inputs','Voice',()=>['gender','delivery','emotion','expressiveness'].map(key=>selected('#voice-inputs [data-voice-field="'+key+'"]').replace('Auto · segue l’interpretazione','Auto')).filter(Boolean).join(' · ')],
  ['video-hint','Video',()=>['Immagini e audio dal prompt',getState()?.models.find(m=>m.id===getState()?.settings.video_model)?.name].filter(Boolean).join(' · ')],
  ['infographic-options','Infografica',()=>['format','style','output','voice_style'].map(key=>chosen('[data-infographic-field="'+key+'"]')).filter(Boolean).join(' · ')],
  ['manim-presentation-options','Manim',()=>$('#manim-presentation-enable')?.getAttribute('aria-pressed')==='true'?[...$('#manim-presentation-options').querySelectorAll('[data-manim-source][aria-pressed="true"],[data-manim-mode][aria-pressed="true"]')].map(e=>e.textContent.trim()).join(' · '):'Python libero · '+(getState()?.settings.manim_duration||8)+' s dal preset']
 ];
 function register(){
  for(const [id,title,describe] of definitions){
   const panel=$('#'+id);if(!panel||entries.some(e=>e.id===id))continue;
   const wrapper=document.createElement('section');wrapper.className='prompt-mode-section';wrapper.hidden=true;body.append(wrapper);wrapper.append(panel);
   const row=document.createElement('div');row.className='prompt-settings-row';
   const button=document.createElement('button');button.type='button';button.className='prompt-choice';button.textContent='⚙ Impostazioni '+title;button.dataset.modeSettings=id;button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-controls',dialog.id);
   const text=document.createElement('span');text.className='prompt-settings-summary';row.append(button,text);context.append(row);
   const tab=document.createElement('button');tab.type='button';tab.className='prompt-choice';tab.textContent=title;tab.dataset.modeTab=id;tabs.append(tab);
   const entry={id,title,describe,panel,wrapper,row,button,text,tab};entries.push(entry);
   button.onclick=()=>{current=id;opener=button;render();dialog.showModal();};tab.onclick=()=>{current=id;render();};
  }
 }
 function render(){
  register();const active=entries.filter(e=>!e.panel.hidden);
  if(!active.some(e=>e.id===current))current=active[0]?.id||null;
  for(const entry of entries){
   const enabled=active.includes(entry);entry.row.hidden=!enabled;entry.tab.hidden=!enabled;entry.wrapper.hidden=!enabled||current!==entry.id;
   entry.tab.setAttribute('aria-pressed',String(current===entry.id));entry.text.textContent=entry.describe();entry.text.title=entry.text.textContent;
  }
  const entry=entries.find(e=>e.id===current);dialog.querySelector('h2').textContent='Impostazioni '+(entry?.title||'della modalità');tabs.hidden=active.length<2;
  if(!active.length&&dialog.open)dialog.close();
 }
 dialog.querySelector('header button').onclick=dialog.querySelector('footer button').onclick=()=>dialog.close();
 dialog.addEventListener('close',()=>{render();if(opener?.isConnected&&!opener.closest('[hidden]'))opener.focus();});
 dialog.addEventListener('click',event=>{if(event.target===dialog){const box=dialog.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)dialog.close();}else queueMicrotask(()=>{onChange();render();});});
 for(const type of ['input','change'])dialog.addEventListener(type,()=>{onChange();render();});
 return {render};
}
