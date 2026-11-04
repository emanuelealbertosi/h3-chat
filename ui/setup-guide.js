import {settingsPages,compactForm,foldSettingsHelp} from './settings-navigation.js';
export function hardwareDefaults(hardware,platform={}){
 const gpus=hardware.gpu||[],nvidia=gpus.find(g=>g.vendor==='NVIDIA'&&g.total_mb>512),apple=gpus.find(g=>g.vendor==='Apple');
 if(platform.system==='darwin'&&apple)return {profile:apple.total_mb>=12288?'balanced':'low',backend:'metal',llm_device:'inherit',gpu_layers:20};
 if(nvidia)return {profile:nvidia.total_mb>=12288?'balanced':'low',backend:'cuda',llm_device:'inherit',gpu_layers:20};
 if(gpus.some(g=>g.total_mb>512))return {profile:'low',backend:'vulkan',llm_device:'inherit',gpu_layers:20};
 return {profile:'cpu',backend:'cpu',llm_device:'cpu',gpu_layers:0};
}
export function setupGuide(body,{state,request,apply,installations,providers}){
 const welcome=body.querySelector('.api-only-setup'),hardware=body.querySelector('#hardware-info'),grid=body.querySelector(':scope > .settings-grid'),cards=grid?[...grid.children]:[],memory=body.querySelector('.memory-settings'),visual=body.querySelector('.visual-setup'),assessment=body.querySelector('#memory-assessment');
 if(!welcome||cards.length<2)return;
 const choice=document.createElement('section');choice.className='card setup-choice';choice.innerHTML='<h3>Come vuoi usare H3-Chat?</h3><p>Scegli un punto di partenza. Puoi cambiare tutto in seguito e combinare modelli locali e servizi esterni.</p><div class="setup-paths"><button type="button" class="btn" data-setup-path="local">Su questo computer</button><button type="button" class="btn" data-setup-path="api">Con API esterne</button><button type="button" class="btn" data-setup-path="mixed">Configurazione mista</button></div><p data-setup-path-note role="status"></p>';
 const detection=document.createElement('section');detection.className='card';detection.innerHTML='<h3>Hardware rilevato</h3><p data-setup-hardware role="status">Rilevamento di CPU, RAM e GPU…</p><button type="button" class="btn small" data-setup-hardware-apply disabled>Usa configurazione consigliata</button><p class="small-note">Il suggerimento imposta il motore di calcolo. La memoria richiesta dipende anche dal modello e dai suoi parametri. Nessun download parte automaticamente.</p>';
 const downloads=document.createElement('section');downloads.className='card';downloads.innerHTML='<h3>Completa la configurazione</h3><p>Apri Installazioni per scegliere modelli, motori e componenti. Dimensioni, stato e avanzamento sono nello stesso posto. Se hai già i pesi, collegali senza copiarli.</p><button type="button" class="btn" data-setup-installs>Apri Installazioni</button> <button type="button" class="text-button" data-setup-providers>Collega API esterne</button><p class="small-note">Quando hai scelto i modelli salva le impostazioni. Puoi tornare qui in qualsiasi momento.</p>';
 // Remove obsolete stand-alone explanatory notes, retaining all actual controls.
 hardware.hidden=true;cards[0].prepend(detection);detection.className='setup-hardware-summary';
 if(visual)compactForm(visual,'setup-visual');
 const pages=[{id:'start',label:'1 · Da dove iniziare',nodes:[choice,welcome]},{id:'hardware',label:'2 · Il tuo computer',nodes:[hardware,cards[0]].filter(Boolean)},{id:'models',label:'3 · Scegli i modelli',nodes:[cards[1],visual].filter(Boolean)},{id:'finish',label:'4 · Memoria e installazioni',nodes:[downloads,memory,assessment].filter(Boolean)}];
 const controller=settingsPages(body,pages,{key:'setup'});grid.remove();
 const footer=document.createElement('div');footer.className='setup-step-actions';footer.innerHTML='<button type="button" class="btn small" data-setup-previous>Indietro</button><span data-setup-step></span><button type="button" class="btn small" data-setup-next>Avanti</button>';body.append(footer);
 const current=()=>pages.findIndex(p=>!p.panel.hidden),sync=()=>{const i=current();footer.querySelector('[data-setup-previous]').disabled=i===0;footer.querySelector('[data-setup-next]').disabled=i===pages.length-1;footer.querySelector('span').textContent=`Passo ${i+1} di ${pages.length}`;};
 body.querySelector('.settings-page-nav').addEventListener('click',sync);body.querySelector('.settings-page-nav').addEventListener('keydown',sync);
 for(const [key,delta] of [['previous',-1],['next',1]])footer.querySelector('[data-setup-'+key+']').onclick=()=>{controller.select(pages[Math.max(0,Math.min(pages.length-1,current()+delta))].id);sync();};sync();
 choice.querySelector('[data-setup-path="api"]').onclick=()=>welcome.querySelector('#setup-api-only').click();
 for(const mode of ['local','mixed'])choice.querySelector('[data-setup-path="'+mode+'"]').onclick=()=>{choice.querySelector('[data-setup-path-note]').textContent=mode==='local'?'Scegli il motore adatto al computer, poi i modelli locali.':'Puoi assegnare API alla chat e usare altri modelli in locale, o viceversa.';controller.select('hardware');sync();};
 downloads.querySelector('[data-setup-installs]').onclick=installations;downloads.querySelector('[data-setup-providers]').onclick=providers;
 request('/hardware').then(h=>{if(!detection.isConnected)return;const ram=h.ram?.total_mb?Math.round(h.ram.total_mb/1024)+' GiB':'non disponibile';detection.querySelector('[data-setup-hardware]').textContent=`${h.cpu_name} · ${h.cpu_threads} thread · RAM ${ram} · ${(h.gpu||[]).map(g=>g.name).join(', ')||'Nessuna GPU rilevata'}`;const button=detection.querySelector('button');button.disabled=false;button.onclick=()=>apply(hardwareDefaults(h,state.platform));}).catch(error=>{if(detection.isConnected)detection.querySelector('[data-setup-hardware]').textContent='Rilevamento non disponibile: '+error.message+'. Puoi scegliere il profilo manualmente.';});
 foldSettingsHelp(body);return controller;
}
