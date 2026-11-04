// Move existing controls so switching pages never resets an unsaved draft.
const remembered=new Map();
const controllers=new WeakMap();
export function settingsPages(host,pages,{key='preferences',intro='',titles=true}={}){
 pages=pages.filter(p=>p.nodes.length);if(!pages.length)return;
 const nav=document.createElement('nav');nav.className='settings-page-nav';nav.setAttribute('aria-label','Sezioni delle impostazioni');
 const content=document.createElement('div');content.className='settings-page-content';
 const layout=document.createElement('div');layout.className='settings-page-layout';layout.append(nav,content);
 const select=(id,focus=false)=>{remembered.set(key,id);for(const page of pages){const active=page.id===id;page.panel.hidden=!active;page.button.setAttribute('aria-pressed',String(active));}content.scrollTop=0;if(focus)pages.find(p=>p.id===id)?.button.focus();};
 for(const page of pages){
  const panel=document.createElement('section');panel.className='settings-page';panel.dataset.settingsPage=page.id;
  if(titles){const title=document.createElement('h3');title.className='settings-page-title';title.textContent=page.label;panel.append(title);}panel.append(...page.nodes);
  const button=document.createElement('button');button.type='button';button.className='settings-page-button';button.textContent=page.label;button.onclick=()=>select(page.id);page.panel=panel;page.button=button;nav.append(button);content.append(panel);
 }
 nav.onkeydown=e=>{const buttons=[...nav.querySelectorAll('button')],index=buttons.indexOf(document.activeElement);if(index<0)return;let next;if(['ArrowDown','ArrowRight'].includes(e.key))next=(index+1)%buttons.length;else if(['ArrowUp','ArrowLeft'].includes(e.key))next=(index+buttons.length-1)%buttons.length;else if(e.key==='Home')next=0;else if(e.key==='End')next=buttons.length-1;else return;e.preventDefault();select(pages[next].id,true);};
 host.replaceChildren();if(intro){const p=document.createElement('p');p.className='settings-page-intro';p.textContent=intro;host.append(p);}host.append(layout);host.classList.add('settings-paged');
 if(!host.dataset.validationNavigation){host.dataset.validationNavigation='true';host.addEventListener('invalid',e=>revealSettingsControl(e.target),true);}
 select(pages.some(p=>p.id===remembered.get(key))?remembered.get(key):pages[0].id);
 const controller={select,reveal:node=>{const page=pages.find(p=>p.panel.contains(node));if(page)select(page.id);}};controllers.set(host,controller);return controller;
}

export function compactBackgroundForm(form){
 if(form.classList.contains('settings-paged'))return;
 const definitions=[['general','Tema e formato'],['appearance','Palette e composizione'],['quality','Quantità e qualità']];
 const groups=new Map(definitions.map(([id,label])=>[id,{id,label,nodes:[]}]));
 const pinned=[];
 for(const node of [...form.children]){
  if(node.matches('[data-error],[data-batch-count]')){pinned.push(node);continue;}
  const keys=[...node.querySelectorAll('[name]')].map(e=>e.name).join(' ');
  const key=/palette|margin|opacity|tone/.test(keys)?'appearance':/variants|megapixels|seed/.test(keys)||node.matches('.background-batch-total')?'quality':'general';groups.get(key).nodes.push(node);
 }
 settingsPages(form,[...groups.values()],{key:'background-form'});form.append(...pinned);foldSettingsHelp(form);
}

export function revealSettingsControl(node){
 // Reveal every ancestor page, including nested groups inside a model card.
 for(let page=node.closest('.settings-page');page;page=page.parentElement.closest('.settings-page')){
  const host=page.parentElement.parentElement.parentElement;controllers.get(host)?.select(page.dataset.settingsPage);
 }
}

export function foldSettingsHelp(host){
 for(const p of host.querySelectorAll('p')){
  if(p.textContent.length<220||p.closest('details,.hardware-note,.api-only-setup')||p.querySelector('button,input,select')||p.matches('[role],.error,.message-error'))continue;
  const details=document.createElement('details'),summary=document.createElement('summary');details.className='settings-help';summary.textContent='Informazioni e limiti';p.before(details);details.append(summary,p);
 }
}

// Only top-level blocks are moved; inputs, IDs and event handlers survive.
export function compactForm(host,key){
 if(!host||host.querySelector(':scope > .settings-page-layout')||host.children.length<7)return;
 // Mode dialogs often consist of labels rather than headings. Group by purpose.
 if(['slides-options','infographic-options','posters-options'].includes(host.id)){
  const pinned=[...host.children].filter(e=>e.matches('[data-presentation-presets]'));for(const e of pinned)e.remove();
  const defs=[['general','Generale'],['style','Grafica e testi'],['images','Immagini e personaggi'],['background','Sfondi'],['audio','Voce e musica'],['motion','Animazioni e regia']];
  const groups=new Map(defs.map(([id,label])=>[id,{id,label,nodes:[]}]));
  for(const child of [...host.children]){const signature=[child.id,child.className,...[...child.querySelectorAll('[id],[data-infographic-field],[data-poster]')].map(n=>n.id||n.dataset.infographicField||n.dataset.poster)].join(' ');const key=/background|sfondi/i.test(signature)?'background':/voice|music|audio|sound/i.test(signature)?'audio':/motion|animat|camera|cinema|parallax|transition/i.test(signature)?'motion':/image|sprite|character|personagg|reuse/i.test(signature)?'images':/style|design|detail|palette|color|font|text-tone|composition|typograph/i.test(signature)?'style':'general';groups.get(key).nodes.push(child);}
  if([...groups.values()].filter(g=>g.nodes.length).length>1){settingsPages(host,[...groups.values()],{key:'form-'+key});host.prepend(...pinned);return;}
  host.prepend(...pinned);
 }
 const children=[...host.children],groups=[];let group;
 for(const child of children){if(!group||child.matches('h3,h4,fieldset')||child.querySelector(':scope > h3')){group={id:'part-'+groups.length,label:child.matches('h3,h4')?child.textContent:child.querySelector('h3,legend')?.textContent||'Generale',nodes:[]};groups.push(group);}group.nodes.push(child);}
 if(groups.length<2)return;settingsPages(host,groups,{key:'form-'+key,titles:false});
}
