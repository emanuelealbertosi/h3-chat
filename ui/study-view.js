import {studyVoices} from './voice-profiles.js';
import {saveBlob} from './render.js';
import {sourceOriginButton} from './source-origin.js';
import {studyStyles} from './study-style.js';
import {exportStudy} from './study-export.js';
import {studyText} from './study-text.js';

const prefix='```h3-study\n';
const names={flashcards:'Flashcard',summary:'Sintesi e briefing',faq:'Domande frequenti',guide:'Guida allo studio',timeline:'Cronologia',dialogue:'Dialogo a due voci'};
const views=new Map(),sessions=new WeakMap(),epochs=new WeakMap();
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
const button=(label,action)=>{const b=node('button',label,'btn small no-export');b.type='button';b.onclick=action;return b;};
function modal(title){const d=node('dialog',null,'study-modal');d.ariaLabel=title;d.append(node('h2',title),button('Chiudi',()=>d.close()));d.addEventListener('close',()=>d.remove());document.body.append(d);return d;}
function csv(deck){const quote=v=>'"'+String(v).replaceAll('"','""')+'"';return '\ufeff'+[['Fronte','Retro','Fonti'],...deck.items.map(i=>[i.question,i.answer,i.citations.map(c=>{const s=deck.sources.find(s=>s.id===c.source);return `${s?.name} · ${s?.location}: ${c.quote}`;}).join('; ')])].map(row=>row.map(quote).join(',')).join('\r\n');}

export async function renderStudy(target,artifact,options){
 studyStyles();const {api,chatId,busy,notify=()=>{}}=options;
 const epoch=(epochs.get(target)||0)+1;epochs.set(target,epoch);
 const deck=JSON.parse(artifact.content.slice(prefix.length,-4));
 const previous=sessions.get(target),signature=JSON.stringify([artifact.id,artifact.content,artifact.media,chatId,!!busy]);
 let progress={};
 if(artifact.id)try{progress=(await api(`/canvas/${chatId}/study/${artifact.id}/progress`)).items||{};}catch(e){if(epochs.get(target)===epoch)notify(e.message,true);}
 if(epochs.get(target)!==epoch)return;
 const progressSignature=JSON.stringify(progress);
 if(previous?.signature===signature&&previous.progressSignature===progressSignature&&previous.root.isConnected){Object.assign(previous.live,options);return;}
 const live={...options},view=views.get(deck.id)||{index:0,shown:false,filter:'all',mode:deck.kind==='flashcards'?'focus':'read',query:'',indexOpen:false};views.set(deck.id,view);
 const root=node('section',null,'study-view');root.tabIndex=0;root.ariaLabel='Studio · '+deck.title;
 const header=node('header',null,'study-header'),heading=node('div');heading.append(node('span',names[deck.kind],'study-eyebrow'),node('h1',deck.title));
 const ready=node('p',`${deck.items.length}/${deck.requested||deck.items.length} ${deck.kind==='flashcards'?'schede':'sezioni'} pronte · ${deck.sources.length} ${deck.sources.length===1?'estratto':'estratti'} fonte`,'study-note');ready.setAttribute('role','status');heading.append(ready);header.append(heading);root.append(header);
 const tools=node('details',null,'study-menu no-export');tools.append(node('summary','Strumenti'));const menu=node('div',null,'study-menu-body');tools.append(menu);header.append(tools);
 menu.append(button('Esporta CSV · Anki',()=>saveBlob(new Blob([csv(deck)],{type:'text/csv;charset=utf-8'}),deck.title+'.csv')),button('Esporta lotto JSON',()=>saveBlob(new Blob([JSON.stringify(deck,null,2)],{type:'application/json'}),deck.title+'.json')));
 for(const [kind,label] of [['pdf','PDF completo'],['docx','Word completo'],['html','HTML completo']]){const b=button(label,async()=>{b.disabled=true;try{await exportStudy(deck,kind,live.api);}catch(e){live.notify?.(e.message,true);}finally{b.disabled=false;}});menu.append(b);}
 const input=node('input');input.type='file';input.accept='.json,application/json';input.hidden=true;
 input.onchange=async()=>{try{const file=input.files[0];if(!file)return;if(file.size>1600000)throw Error('Lotto oltre 1,6 MB.');const next=JSON.parse(await file.text());next.id=crypto.randomUUID().replaceAll('-','');if(!Array.isArray(next.items))throw Error('Lotto Studio non valido.');for(const i of next.items)i.id=crypto.randomUUID().replaceAll('-','');await live.onChange(prefix+JSON.stringify(next)+'\n```');}catch(e){live.notify?.(e.message,true);}finally{input.value='';}};
 const load=button('Importa lotto JSON',()=>input.click());load.disabled=!!busy;menu.append(load,input);
 const library=button('Lotti del progetto',async()=>{const d=modal('Lotti Studio salvati'),status=node('p','Caricamento…','study-note');d.append(status);d.showModal();try{const result=await live.api('/chats/'+chatId+'/study-library');status.textContent=(result.scope==='project'?'Ultimi lotti del progetto':'Lotti di questa chat')+' · fino a '+result.limit+'. Viene mostrata l’ultima versione di ogni lotto; tutte le revisioni restano nella cronologia del canvas.';if(!result.items.length)d.append(node('p','Nessun lotto salvato.'));for(const item of result.items){const row=node('section',null,'study-source');row.append(node('h3',item.title),node('p',`${names[item.kind]||'Studio'} · ${item.count}/${item.requested} · ${item.chat_title} · ${new Date(item.updated*1000).toLocaleDateString('it-IT')}`,'study-note'));const open=button('Apri lotto',async()=>{open.disabled=true;try{await live.onOpenStudy(item);d.close();}catch(e){status.textContent=e.message;open.disabled=false;}});row.append(open);d.append(row);}}catch(e){status.textContent=e.message;}});if(options.onOpenStudy)menu.prepend(library);
 const sourceButton=button('Fonti · '+deck.sources.length,()=>{
  const d=modal('Fonti di questo Studio');d.append(node('p','Sono gli estratti conservati in questo lotto, non necessariamente tutti i documenti o tutto il libro.','study-note'));
  for(const source of deck.sources){const section=node('section',null,'study-source');section.append(node('h3',`[${source.id}] ${source.name}`),node('p',source.location||'Passaggio selezionato','study-note'));
   if(source.partial)section.append(node('p','Estratto abbreviato per il limite di contesto.','study-note'));
   const detail=node('details');detail.append(node('summary','Leggi il passaggio'),node('pre',source.text));section.append(detail);origin(section,source);d.append(section);
  }d.showModal();
 });
 const toolbar=node('div',null,'study-toolbar no-export');root.append(toolbar);
 const focus=button(deck.kind==='flashcards'?'Studia':'Ripassa',()=>{view.mode='focus';view.shown=false;draw();}),read=button('Leggi tutto',()=>{view.mode='read';draw();}),quiz=button('Prova a rispondere',()=>{view.mode='quiz';view.shown=false;draw();});toolbar.append(focus,read,quiz,sourceButton);
 const shuffle=button('Mescola',()=>{if(view.order){delete view.order;}else{view.order=deck.items.map(i=>i.id);for(let i=view.order.length-1;i>0;i--){const random=new Uint32Array(1);crypto.getRandomValues(random);const j=random[0]%(i+1);[view.order[i],view.order[j]]=[view.order[j],view.order[i]];}}view.index=0;view.shown=false;draw();});toolbar.append(shuffle);
 const choice=node('select');choice.ariaLabel='Filtro ripasso';for(const [v,title] of [['all','Tutte'],['due','Da fare ora'],['review','Da ripassare'],['new','Non studiate'],['known','Ricordate']])choice.append(new Option(title,v));choice.value=view.filter;choice.onchange=()=>{view.filter=choice.value;view.index=0;view.shown=false;draw();};toolbar.append(choice);
 const stats=node('p',null,'study-note');root.append(stats);
 if(deck.items.length<deck.requested&&artifact.id){const resume=button('Completa schede mancanti',async()=>{resume.disabled=true;try{await live.onResume();}catch(e){resume.disabled=!!live.busy;live.notify?.(e.message,true);}});resume.disabled=!!busy;toolbar.append(resume);}
 for(const m of artifact.media||[])if(m.mime?.startsWith('audio/')&&/^(uploads|outputs)\/[\w./-]+$/.test(m.path)&&!m.path.split('/').includes('..')){const audio=node('audio');audio.controls=true;audio.preload='metadata';audio.src='/media/'+m.path;audio.ariaLabel='Audio dello Studio';root.append(audio);}
 if(deck.kind==='dialogue'){
  const audioOptions=node('details',null,'study-audio-options no-export');audioOptions.append(node('summary','Audio a due voci'));const selectedVoices=studyVoices(audioOptions);
  const audio=button('Crea audio a due voci',async()=>{audio.disabled=true;try{await live.onAudio(selectedVoices.read());}catch(e){audio.disabled=!!live.busy;live.notify?.(e.message,true);}});audio.disabled=!!busy||deck.status!=='ready';audioOptions.append(audio,node('p','Genera l’audio dal dialogo salvato, con le voci scelte.','study-note'));root.append(audioOptions);
 }
 const index=node('details',null,'study-index no-export');index.open=view.indexOpen;index.ontoggle=()=>view.indexOpen=index.open;const indexTitle=node('summary','Indice');index.append(indexTitle);
 const search=node('input');search.type='search';search.className='study-search';search.ariaLabel='Cerca nello Studio';search.placeholder='Cerca una domanda, un concetto o una risposta';search.value=view.query;search.oninput=()=>{view.query=search.value;view.index=0;view.shown=false;draw();};
 const indexTools=node('div',null,'study-index-tools'),clear=button('Azzera',()=>{search.value='';view.query='';view.filter='all';choice.value='all';view.index=0;view.shown=false;draw();});indexTools.append(search,clear);index.append(indexTools);const list=node('ol',null,'study-index-list');index.append(list);root.append(index);
 const content=node('div',null,'study-content'),bottom=node('div',null,'study-footer no-export');root.append(content,bottom);
 const shortcuts=node('p','Frecce ← → per cambiare scheda · Spazio per mostrare la risposta, quando il riquadro Studio è selezionato.','study-note no-export');root.append(shortcuts);

 function origin(host,source){
  if(source.media_origin&&deck.project_id)host.append(sourceOriginButton(live.api,deck.project_id,source,live.notify||(()=>{})));
  if(source.url&&/^https?:\/\//i.test(source.url)){const link=node('a','Apri fonte originale');link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';host.append(link);}
 }
 function cite(host,item){const row=node('div',null,'study-citations');for(const c of item.citations){const s=deck.sources.find(s=>s.id===c.source);if(!s)continue;row.append(button(`[${s.id}] ${s.name} · ${s.location}`,()=>{const d=modal(s.name+' · '+s.location);d.append(node('p','Citazione: '+c.quote),node('pre',s.text));origin(d,s);d.showModal();}));}host.append(row);}
 function answer(host,item){const text=node('div',null,'study-answer');studyText(text,item.answer);host.append(text);cite(host,item);if(item.explanation){const more=node('section',null,'study-explanation'),answer=node('div',null,'study-answer');studyText(answer,item.explanation.answer);more.append(node('h3',item.explanation.followup?item.explanation.question:'Spiegazione'),answer);cite(more,item.explanation);host.append(more);}}
 function due(item){return !progress[item.id]?.next_review||progress[item.id].next_review<=Date.now()/1000;}
 function selected(){const query=view.query.trim().toLocaleLowerCase(),rows=deck.items.filter(i=>(view.filter==='all'||view.filter==='due'&&due(i)||view.filter==='new'&&!progress[i.id]||view.filter==='review'&&progress[i.id]?.remembered===0||view.filter==='known'&&progress[i.id]?.remembered===1)&&(!query||(i.question+' '+i.answer).toLocaleLowerCase().includes(query)));if(view.order&&view.mode!=='read'){const ranks=new Map(view.order.map((id,i)=>[id,i]));rows.sort((a,b)=>(ranks.get(a.id)??999)-(ranks.get(b.id)??999));}return rows;}
 function selectItem(id,mode=view.mode){const rows=selected();view.index=Math.max(0,rows.findIndex(i=>i.id===id));view.shown=false;view.mode=mode;draw();if(mode==='read')content.querySelector('[data-study-item="'+id+'"]')?.scrollIntoView({block:'nearest',behavior:'smooth'});}
 function move(delta){const rows=selected();if(!rows.length)return;view.index=(view.index+delta+rows.length)%rows.length;view.shown=false;draw();}
 function edit(item){const d=modal('Modifica scheda'),form=node('div',null,'study-edit'),q=node('textarea'),a=node('textarea');q.value=item.question;a.value=item.answer;q.maxLength=1200;a.maxLength=6000;q.ariaLabel='Domanda';a.ariaLabel='Risposta';form.append(node('label','Domanda / titolo'),q,node('label','Risposta'),a,node('p','La modifica manuale conserva le citazioni: controlla che sostengano il nuovo testo. Il ripasso di questa versione ricomincia.','study-note'));const save=button('Salva',async()=>{save.disabled=true;try{const next=structuredClone(deck),edited=next.items.find(i=>i.id===item.id);edited.question=q.value;edited.answer=a.value;delete edited.explanation;await live.onChange(prefix+JSON.stringify(next)+'\n```');d.close();}catch(e){save.disabled=false;live.notify?.(e.message,true);}});form.append(save);d.append(form);d.showModal();}
 function itemActions(host,item,review=false){
  if(review&&artifact.id)for(const [value,label] of [[false,'Da ripassare'],[true,'Ricordata']]){const b=button(label,async()=>{b.disabled=true;try{progress=(await live.api(`/canvas/${chatId}/study/${artifact.id}/progress`,{card_id:item.id,remembered:value})).items;if(!root.isConnected)return;const session=sessions.get(target);if(session?.root===root)session.progressSignature=JSON.stringify(progress);move(1);}catch(e){b.disabled=false;live.notify?.(e.message,true);}});if(value)b.classList.add('study-known');host.append(b);}
  if(artifact.id){const explain=button('Spiega',async()=>{explain.disabled=true;try{await live.onExplain(item.id);}catch(e){explain.disabled=!!live.busy;live.notify?.(e.message,true);}});explain.disabled=!!busy;host.append(explain);}
  if(artifact.id){const ask=button('Chiedi un chiarimento',()=>{const d=modal('Chiedi sulle fonti della scheda'),form=node('div',null,'study-edit'),question=node('textarea');question.ariaLabel='Domanda di approfondimento';question.maxLength=1200;question.placeholder='Es. Non ho capito questo passaggio: puoi spiegarlo in modo più semplice?';const error=node('p',null,'render-error'),send=button('Chiedi al tutor',async()=>{if(!question.value.trim()){question.focus();return;}send.disabled=true;try{await live.onExplain(item.id,question.value.trim());d.close();}catch(e){error.textContent=e.message;send.disabled=false;}});form.append(node('p','Il tutor usa le stesse fonti della scheda e il chiarimento precedente. La nuova risposta citata viene salvata nel lotto; le versioni precedenti restano nella cronologia del canvas.','study-note'),question,error,send);d.append(form);d.showModal();question.focus();});ask.disabled=!!busy;host.append(ask);}
  if(!busy)host.append(button('Modifica scheda',()=>edit(item)));
 }
 function readingItem(item,i){
  let article=node('article',null,'study-card'),body=article;
  if(deck.kind==='faq'){article=node('details',null,'study-card study-faq');article.open=i===view.index;article.append(node('summary',item.question));body=node('div',null,'study-faq-body');article.append(body);}
  else if(deck.kind==='dialogue'){article=node('article',null,'study-bubble'+(/\bB\s*:?[ \t]*$/i.test(item.question)?' study-speaker-b':''));body=article;article.append(node('h2',item.question));}
  else article.append(node('h2',item.question));
  article.dataset.studyItem=item.id;answer(body,item);
  const actions=node('div',null,'study-section-actions no-export');actions.append(button('Ripassa questa sezione',()=>selectItem(item.id,'focus')));itemActions(actions,item);body.append(actions);return article;
 }
 function draw(){
  const rows=selected();view.index=Math.max(0,Math.min(view.index,rows.length-1));const item=rows[view.index];
  focus.setAttribute('aria-pressed',String(view.mode==='focus'));read.setAttribute('aria-pressed',String(view.mode==='read'));quiz.setAttribute('aria-pressed',String(view.mode==='quiz'));shuffle.textContent=view.order?'Ordine originale':'Mescola';shuffle.hidden=view.mode==='read';shortcuts.hidden=view.mode!=='focus';
  const known=deck.items.filter(i=>progress[i.id]?.remembered===1).length,review=deck.items.filter(i=>progress[i.id]?.remembered===0).length;
  stats.textContent=`${known} ${known===1?'ricordata':'ricordate'} · ${review} da ripassare · ${deck.items.length-known-review} non studiate · ${deck.items.filter(due).length} da fare ora`;
  indexTitle.textContent=`Indice · ${rows.length}${rows.length!==deck.items.length?' / '+deck.items.length:''} ${deck.kind==='flashcards'?'schede':'sezioni'}`;
  list.replaceChildren();for(const [i,row] of rows.entries()){const li=node('li'),jump=button('',()=>selectItem(row.id));jump.append(node('small',String(i+1).padStart(2,'0')),node('span',row.question));jump.setAttribute('aria-current',String(i===view.index));if(progress[row.id])jump.title=progress[row.id].remembered?'Ricordata':'Da ripassare';li.append(jump);list.append(li);}
  content.replaceChildren();bottom.replaceChildren();
  if(!item){content.append(node('p',deck.status==='building'&&!deck.items.length?'Sto creando le schede…':'Nessuna scheda con questi filtri. Azzera la ricerca o cambia il filtro.','study-card study-empty'));return;}
  if(view.mode==='read'){
   const collection=node(deck.kind==='timeline'?'ol':'div',null,deck.kind==='timeline'?'study-timeline':deck.kind==='dialogue'?'study-dialogue':'study-sections');
   for(const [i,row] of rows.entries()){const rendered=readingItem(row,i);if(deck.kind==='timeline'){const li=node('li');li.append(rendered);collection.append(li);}else collection.append(rendered);}content.append(collection);return;
  }
  const card=node('article',null,'study-card'+(deck.kind==='flashcards'?' study-flashcard':''));card.dataset.studyItem=item.id;
  card.append(node('p',`${view.index+1} / ${rows.length}`,'study-counter'),node('h2',item.question));
  const shown=view.shown||view.mode!=='quiz'&&deck.kind!=='flashcards';
  if(view.mode==='quiz'){
   view.responses||={};const response=node('textarea');response.className='study-response';response.ariaLabel='La tua risposta';response.rows=4;response.maxLength=6000;response.placeholder='Scrivi la risposta prima di confrontarla con la fonte.';response.value=view.responses[item.id]||'';response.oninput=()=>view.responses[item.id]=response.value;card.append(response);
   if(shown)card.append(node('p','Confronta la tua risposta con quella qui sotto e con le fonti. La valutazione è tua: non è un voto automatico.','study-note'));
  }
  if(shown)answer(card,item);else{const reveal=button(view.mode==='quiz'?'Confronta con la fonte':'Mostra risposta',()=>{view.shown=true;draw();root.focus({preventScroll:true});});reveal.classList.add('study-reveal');card.append(reveal);}
  if(progress[item.id]){const p=progress[item.id];card.append(node('p',`${p.remembered?'Ricordata':'Da ripassare'} · ${p.attempts} ${p.attempts===1?'prova':'prove'}`+(p.next_review?' · Prossimo ripasso: '+new Date(p.next_review*1000).toLocaleString('it-IT',{dateStyle:'short',timeStyle:'short'}):''),'study-note'));}
  content.append(card);const meter=node('progress',null,'study-meter');meter.max=rows.length;meter.value=view.index+1;meter.ariaLabel='Posizione nel lotto';
  const navigation=node('div',null,'study-navigation');navigation.append(button('← Precedente',()=>move(-1)),node('span',`${view.index+1} / ${rows.length}`,'study-counter'),button('Successiva →',()=>move(1)));bottom.append(meter,navigation);
  const actions=node('div',null,'study-actions');if(shown)itemActions(actions,item,true);else if(!busy)actions.append(button('Modifica scheda',()=>edit(item)));bottom.append(actions);
 }
 root.onkeydown=e=>{if(e.target!==root)return;if(view.mode!=='focus')return;if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();move(e.key==='ArrowRight'?1:-1);}else if(e.key===' '&&deck.kind==='flashcards'){e.preventDefault();view.shown=!view.shown;draw();}};
 draw();target.classList.remove('slides-preview');target.replaceChildren(root);sessions.set(target,{signature,progressSignature,root,live});
}
