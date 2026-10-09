import {initComposerSettings} from './composer-settings.js';
const $=selector=>document.querySelector(selector);
function button(text,id){const element=document.createElement('button');element.type='button';element.className='prompt-choice';element.textContent=text;if(id)element.id=id;return element;}
function field(title){const element=document.createElement('div');element.className='prompt-field';const heading=document.createElement('span');heading.className='prompt-field-label';heading.textContent=title;element.append(heading);return element;}

export function initComposerPanel({getState,visualControls,getAttachments,notify}){
 const composer=$('#composer'),lab=$('#lab-tool'),image=$('#image-model'),slides=$('#slides-options');
 const modes=document.createElement('div');modes.id='prompt-modes';modes.className='prompt-modes';modes.setAttribute('role','group');modes.ariaLabel='Cosa vuoi creare';
 const context=document.createElement('div');context.id='prompt-context';context.className='prompt-context';context.hidden=true;
 const sources=document.createElement('div');sources.id='prompt-sources';sources.className='prompt-sources';
 const footer=document.createElement('div');footer.className='prompt-footer';const technical=button('⚙ Opzioni tecniche','prompt-options-open'),summary=document.createElement('p');summary.id='prompt-technical-summary';summary.className='prompt-technical-summary';
 const llm=$('#chat-model').closest('label');llm.classList.add('prompt-llm');
 $('#prompt').after(modes,context,sources,footer);footer.append(llm,technical,summary);
 const dialog=document.createElement('dialog');dialog.id='prompt-options';dialog.className='prompt-options-dialog';dialog.innerHTML='<header><div><span class="eyebrow">DAL PROSSIMO MESSAGGIO</span><h2>Opzioni del prompt</h2></div><button type="button" class="icon-button" aria-label="Chiudi opzioni del prompt">×</button></header><div class="prompt-options-body"></div><footer><button type="button" class="btn primary">Fatto</button></footer>';document.body.append(dialog);
 const technicalBody=dialog.querySelector('.prompt-options-body');dialog.querySelector('header button').onclick=dialog.querySelector('footer button').onclick=()=>dialog.close();
 const open=view=>{dialog.dataset.view=view;dialog.querySelector('h2').textContent=view==='models'?'Modello della chat':'Opzioni del prompt';render();dialog.showModal();};technical.onclick=()=>open('technical');
 const mirrors=[];
 function pills(select,title,modelList=false){
  const original=select.closest('label'),host=field(title),group=document.createElement('div');group.className='prompt-choices'+(modelList?' prompt-model-list':'');group.setAttribute('role','group');group.ariaLabel=title;
  if(original.id)host.id=original.id;original.before(host);host.append(select,group);select.hidden=true;original.remove();let signature='';
  const update=()=>{const options=[...select.options].filter(o=>!modelList||!o.disabled||o.value===select.value),next=JSON.stringify(options.map(o=>[o.value,o.textContent,o.disabled]));if(next!==signature){signature=next;group.replaceChildren();for(const option of options){const item=button(option.textContent.trim());item.dataset.value=option.value;item.onclick=()=>{select.value=option.value;select.dispatchEvent(new Event('change',{bubbles:true}));render();};group.append(item);}}
   for(const item of group.children){const option=[...select.options].find(o=>o.value===item.dataset.value);item.disabled=select.disabled||!!option?.disabled;item.setAttribute('aria-pressed',String(select.value===item.dataset.value));}
  };mirrors.push(update);update();return host;
 }
 function toggle(input,label,where){
  const original=input.closest('label'),item=button(label);input.hidden=true;original.hidden=true;where.append(item);item.onclick=()=>{input.checked=!input.checked;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));render();};
  mirrors.push(()=>{item.disabled=input.disabled;item.setAttribute('aria-pressed',String(input.checked));});return item;
 }
 // Keep existing controls and their request semantics; only their presentation changes.
 const auto=button('✦ Automatico','prompt-auto'),images=button('▧ Immagini','prompt-images');modes.append(auto,images);
 for(const id of ['music-toggle','video-toggle','voice-toggle']){const item=$('#'+id);item.className='prompt-choice';modes.append(item);}
 const tools=new Map([['slides',button('▥ Slide','prompt-slides')],['infographic',button('✧ Infografica','prompt-infographic')],['manim',button('⌁ Manim','prompt-manim')],['calculate',button('∑ Calcolo','prompt-calculate')]]);
 for(const item of tools.values())modes.append(item);
 const transcribe=$('#transcribe-toggle');transcribe.className='prompt-choice';modes.append(transcribe);
 const reset=()=>visualControls.set({...visualControls.read(),image_model:'',music:false,video:false,voice:false,transcribe:false});
 const setLab=value=>{lab.value=value;lab.dispatchEvent(new Event('change',{bubbles:true}));};
 auto.onclick=()=>{setLab('auto');reset();render();};
 images.onclick=()=>{const state=getState();if(!state)return;const attached=getAttachments().some(m=>m.mime.startsWith('image/')),cap=attached?'edit':'create';const model=state.models.find(m=>m.id===(attached?state.settings.edit_model:state.settings.create_model)&&m.ready&&m.capabilities.includes(cap))||state.models.find(m=>m.ready&&m.capabilities.includes(cap));
  if(!model){notify('Collega prima un modello immagini nelle Impostazioni.',true);return;}
  setLab('auto');reset();visualControls.set({...visualControls.read(),image_model:model.id});render();};
 for(const [value,item] of tools)item.onclick=()=>{const voice=value==='manim'&&visualControls.read().voice;const next=lab.value===value?'auto':value;reset();setLab(next);if(voice&&next==='manim')visualControls.set({...visualControls.read(),voice:true});render();};
 for(const id of ['music-toggle','video-toggle','voice-toggle','transcribe-toggle']){const item=$('#'+id),previous=item.onclick;item.onclick=event=>{if(id!=='voice-toggle'||lab.value!=='manim')setLab('auto');previous?.(event);render();};}
 lab.closest('label').hidden=true;
 const imagePanel=field('Modello immagini');imagePanel.id='prompt-image-panel';context.append(imagePanel);imagePanel.append(image.closest('label'));pills(image,'Scegli il modello',true);
 for(const id of ['slides-options','music-inputs','voice-inputs','video-hint'])context.append($('#'+id));
 slides.classList.add('prompt-slide-options');
 const count=$('#slides-count'),countLabel=count.closest('label');countLabel.classList.add('prompt-count');const minus=button('−'),plus=button('＋');minus.ariaLabel='Meno slide';plus.ariaLabel='Più slide';count.before(minus);count.after(plus);for(const [item,delta] of [[minus,-1],[plus,1]])item.onclick=()=>{count.value=Math.max(1,Math.min(30,(Number(count.value)||8)+delta));count.dispatchEvent(new Event('change',{bubbles:true}));render();};
 const slideTechnical=field('Presentazioni · opzioni tecniche');slides.append(slideTechnical);
 for(const id of ['slides-engine','slides-vision'])slideTechnical.append($('#'+id).closest('label'));
 for(const [id,title] of [['slides-format','Formato'],['slides-design','Stile'],['slides-detail','Contenuto'],['slides-background','Sfondo'],['slides-palette','Palette']])pills($('#'+id),title);
 for(const id of ['slides-engine','slides-vision'])pills($('#'+id),id==='slides-engine'?'Motore slide':'Analisi delle figure');
 const imageToggle=toggle($('#slides-generate-images'),'Illustrazioni AI · tutte insieme',slides);imageToggle.classList.add('prompt-slide-images');
 const imageModels=$('#slides-image-model'),generatedModels=pills(imageModels,'Modello per le illustrazioni',true);
 generatedModels.before(imageToggle);
 for(const select of $('#voice-inputs').querySelectorAll('select'))pills(select,select.closest('label').querySelector('span')?.textContent||'Voce');
 const voiceMode=$('#voice-inputs [data-voice-field="mode"]').parentElement;
 // Voice controls use closest(label) to hide the read/compose selector for Manim.
 voiceMode.classList.add('voice-mode-choice');
 const voiceOriginal=$('#voice-inputs [data-voice-field="mode"]');const label=document.createElement('label');label.hidden=true;voiceOriginal.before(label);label.append(voiceOriginal);
 for(const [input,title] of [[$('#vision-enabled'),'Vision attiva'],[$('#chat-advanced'),'Mostra dettagli delle risposte']])toggle(input,title,technicalBody);
 for(const [select,title] of [[$('#think-level'),'Thinking'],[$('#chat-vision-device'),'Dispositivo Vision']]){technicalBody.append(select.closest('label'));pills(select,title);}
 technicalBody.append($('#chat-vision-max-refs').closest('label'),$('#chat-vision-refs-note'));
 technicalBody.append($('#vision-badge'),$('#think-note'),$('#chat-vision-device-note'),$('#generation-settings'));
 $('#generation-settings').addEventListener('click',()=>dialog.close(),{capture:true});
 const assistant=toggle($('#image-assistant'),'Assistant',sources);sources.append($('#project-chat-label'));toggle($('#rag-enabled'),'RAG',sources);const web=$('#web-toggle');web.className='prompt-choice';sources.append(web);
 toggle($('#music-inputs [data-music-field="instrumental"]'),'Strumentale',$('#music-inputs .settings-grid'));
 $('#project-chat-label').classList.add('prompt-project');
 for(const row of composer.querySelectorAll('.chat-controls')){row.classList.add('prompt-legacy-row');row.hidden=true;}
 const warning=$('#vision-warning');footer.append(warning);
 const llmPicker=pills($('#chat-model'),'Modello LLM',true);llmPicker.classList.add('prompt-llm-picker');technicalBody.append(llmPicker);const modelButton=button('Scegli LLM','prompt-llm-open');footer.prepend(modelButton);modelButton.onclick=()=>open('models');
 const identity=button('File e percorso del modello');identity.className='text-button';identity.onclick=()=>{dialog.close();$('#model-name').click();};llmPicker.append(identity);
 const update=()=>render();composer.addEventListener('change',update);composer.addEventListener('input',event=>{if(event.target!==$('#prompt'))render();});
 const modeSettings=initComposerSettings({context,getState,onChange:render});
 function render(){
  const state=getState();if(!state)return;
  const value=visualControls.read(),mode=lab.value;
  auto.setAttribute('aria-pressed',String(mode==='auto'&&!value.image_model&&!value.music&&!value.video&&!value.voice&&!value.transcribe));images.setAttribute('aria-pressed',String(!!value.image_model));
  for(const [name,item] of tools)item.setAttribute('aria-pressed',String(mode===name));
  imagePanel.hidden=!value.image_model;slides.hidden=mode!=='slides';slideTechnical.hidden=mode!=='slides';generatedModels.hidden=!$('#slides-generate-images').checked;
  voiceMode.hidden=!!value.voice&&mode==='manim';context.hidden=!(mode==='slides'||mode==='manim'||mode==='infographic'||value.image_model||value.voice||value.music||value.video);
  const infographic=document.querySelector('#infographic-options');if(infographic)infographic.hidden=mode!=='infographic';
  const manim=document.querySelector('#manim-presentation-options');if(manim)manim.hidden=mode!=='manim';
  assistant.textContent='Assistant '+(value.assistant?'On':'Off');assistant.title='Prepara le istruzioni con il LLM della chat';
  for(const update of mirrors)update();
  const model=state.models.find(m=>m.id===state.settings.chat_model),vision=!state.settings.vision_enabled?'Vision Off':model?.vision?.enabled?'Vision '+(model.api?'API':state.settings.vision_device.toUpperCase()):'Non vision';
  const refs=model?.api?Math.min(state.settings.vision_max_refs??4,model.max_refs??model.vision?.max_refs??4):state.settings.vision_max_refs??4;
  summary.textContent=[vision+(model?.vision?.enabled&&state.settings.vision_enabled?' · max '+refs+' immagini':''),'Think '+(model?.thinking?.supported?state.settings.think_level:'Off'),Number(state.settings.context).toLocaleString('it-IT')+' contesto',state.settings.max_tokens+' max token',model?.mtp?.supported?(state.settings.mtp_enabled?'MTP On':'MTP Off'):'MTP N/D'].join(' · ');
  technical.title=summary.textContent;
  modelButton.textContent='LLM · '+($('#chat-model').selectedOptions[0]?.textContent||'Scegli un modello');modelButton.title=$('#chat-model').title;modelButton.disabled=$('#chat-model').disabled;
  $('.side-bottom>small').textContent='H3 CHAT · '+state.version;
  modeSettings.render();
 }
 return {render};
}
