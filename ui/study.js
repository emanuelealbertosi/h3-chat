import {saveBlob} from './render.js';
import {sourceOriginButton} from './source-origin.js';
export const studyPrefix='```h3-study\n';
const defaults={kind:'flashcards',count:10,level:'standard',source_text:''};
const names={flashcards:'Flashcard',summary:'Sintesi e briefing',faq:'Domande frequenti',guide:'Guida allo studio',timeline:'Cronologia',dialogue:'Dialogo a due voci · script'};
const views=new Map();
function node(tag,text,cls){const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;}
function button(title,action){const b=node('button',title,'btn small no-export');b.type='button';b.onclick=action;return b;}
function styles(){if(document.querySelector('#study-style'))return;const e=node('style');e.id='study-style';e.textContent='.study-view{padding:20px;max-width:100%;box-sizing:border-box}.study-toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}.study-card{border:1px solid var(--line,#ddd);border-radius:14px;background:var(--white,#fffefa);padding:24px;min-height:220px;overflow-wrap:anywhere}.study-card h2{font-size:clamp(20px,3vw,32px);line-height:1.35}.study-answer{font-size:17px;white-space:pre-wrap;line-height:1.7}.study-citations{display:flex;gap:6px;flex-wrap:wrap;margin:16px 0}.study-note{color:var(--muted,#61766b);font-size:12px;line-height:1.6}.study-modal{max-width:min(850px,90vw);max-height:85vh;overflow:auto;border:1px solid #ccc;border-radius:12px;padding:24px}.study-modal pre{white-space:pre-wrap;overflow-wrap:anywhere}.study-edit{display:grid;gap:12px}.study-edit textarea{width:100%;min-height:120px;box-sizing:border-box}.study-explanation{margin-top:20px;border-top:1px solid #ddd;padding-top:16px;white-space:pre-wrap}.study-view [hidden]{display:none!important}@media(max-width:600px){.study-view{padding:8px}.study-card{padding:16px}}';document.head.append(e);}
export function initStudy({getState,getAttachments=()=>[],onImport=async()=>{throw Error('Importazione non disponibile.');}}){
 styles();const panel=node('div');panel.id='study-options';panel.hidden=true;panel.className='prompt-slide-options';
 const field=(label,key,input)=>{const holder=node('label',label);input.dataset.study=key;holder.append(input);panel.append(holder);return input;};
 const kind=field('Documento','kind',node('select'));for(const [v,title] of Object.entries(names))kind.append(new Option(title,v));
 const count=field('Numero di schede / sezioni','count',node('input'));count.type='number';count.min=1;count.max=50;
 const level=field('Livello','level',node('select'));for(const [v,title] of [['simple','Semplice'],['standard','Standard'],['advanced','Avanzato']])level.append(new Option(title,v));
 const source=field('Testo fonte facoltativo','source_text',node('textarea'));source.rows=5;source.maxLength=60000;source.placeholder='Incolla un testo da studiare, oppure usa gli allegati e le fonti RAG del progetto.';
 panel.append(node('p','Usa soltanto le fonti selezionate. Il recupero RAG può fornire estratti, non tutto il libro. Le citazioni aprono il passaggio originale. Il dialogo produce uno script; l’audio è un passaggio separato.','small-note'));
 panel.append(button('Importa una fonte nel progetto',()=>{
  const d=modal('Importa fonte Studio'),form=node('div',null,'study-edit'),type=node('select'),name=node('input'),url=node('input'),media=node('select'),note=node('p','PDF, Word, TXT e Markdown si caricano già dal pannello Fonti del progetto. Qui puoi leggere un URL pubblico, i sottotitoli YouTube disponibili o trascrivere un audio/video allegato. La trascrizione locale segue le impostazioni Whisper ed è limitata a 30 minuti.','study-note');
  for(const [v,label] of [['web','Pagina web pubblica'],['youtube','YouTube · sottotitoli IT/EN'],['audio','Audio / video allegato · Whisper']])type.append(new Option(label,v));
  name.placeholder='Nome della fonte';name.maxLength=150;name.ariaLabel='Nome fonte';url.placeholder='https://…';url.maxLength=4096;url.ariaLabel='URL fonte';type.ariaLabel='Tipo fonte';media.ariaLabel='Audio o video allegato';
  for(const m of getAttachments().filter(m=>/^(audio|video)\//.test(m.mime)))media.append(new Option(m.name,m.id));
  const update=()=>{url.hidden=type.value==='audio';media.hidden=type.value!=='audio';};type.onchange=update;update();
  const error=node('p',null,'render-error'),start=button('Importa e indicizza',async()=>{start.disabled=true;error.textContent='';try{await onImport({kind:type.value,name:name.value||'Fonte Studio',url:url.value,asset_id:media.value});d.close();}catch(e){start.disabled=false;error.textContent=e.message;}});
  form.append(note,type,name,url,media,error,start);d.append(form);d.showModal();
 }));
 document.querySelector('#slides-options').after(panel);let saved={...defaults};try{saved={...saved,...JSON.parse(localStorage.getItem('h3-study-options')||'{}')};}catch{}
 function read(){return{kind:kind.value,count:Number(count.value),level:level.value,source_text:source.value};}
 function set(value){const v={...defaults,...value};kind.value=v.kind;count.value=v.count;level.value=v.level;source.value=v.source_text;}
 function render(){panel.hidden=document.querySelector('#lab-tool').value!=='study';}
 panel.addEventListener('change',()=>{const v=read();try{localStorage.setItem('h3-study-options',JSON.stringify({...v,source_text:''}));}catch{}});
 document.querySelector('#lab-tool').addEventListener('change',render);set(saved);render();return{read,set,render};
}

function modal(title){const d=node('dialog',null,'study-modal');d.append(node('h2',title));d.append(button('Chiudi',()=>d.close()));d.addEventListener('close',()=>d.remove());document.body.append(d);return d;}
function csv(deck){const quote=v=>'"'+String(v).replaceAll('"','""')+'"';return '\ufeff'+[['Fronte','Retro','Fonti'],...deck.items.map(i=>[i.question,i.answer,i.citations.map(c=>{const s=deck.sources.find(s=>s.id===c.source);return `${s?.name} · ${s?.location}: ${c.quote}`;}).join('; ')])].map(row=>row.map(quote).join(',')).join('\r\n');}
export async function renderStudy(target,artifact,{api,chatId,busy,onExplain,onResume,onAudio,onChange,notify=()=>{}}){
 styles();target.classList.remove('slides-preview');const deck=JSON.parse(artifact.content.slice(studyPrefix.length,-4));target.replaceChildren();
 const view=views.get(deck.id)||{index:0,shown:false,filter:'all'};views.set(deck.id,view);
 const root=node('section',null,'study-view'),head=node('div',null,'study-toolbar'),card=node('article',null,'study-card'),bottom=node('div',null,'study-toolbar');root.append(node('h1',deck.title),node('p',`${names[deck.kind]} · ${deck.items.length}/${deck.requested||deck.items.length} pronte · basate sugli estratti selezionati`,'study-note'),head,card,bottom);target.append(root);
 for(const m of artifact.media||[])if(m.mime?.startsWith('audio/')&&/^(uploads|outputs)\/[\w./-]+$/.test(m.path)&&!m.path.split('/').includes('..')){const audio=node('audio');audio.controls=true;audio.src='/media/'+m.path;root.append(audio);}
 let progress={};if(artifact.id)try{progress=(await api(`/canvas/${chatId}/study/${artifact.id}/progress`)).items;}catch(e){notify(e.message,true);}
 const choice=node('select');choice.ariaLabel='Filtro ripasso';for(const [v,title] of [['all','Tutte'],['review','Da ripassare'],['new','Non studiate'],['known','Ricordate']])choice.append(new Option(title,v));choice.value=view.filter;choice.onchange=()=>{view.filter=choice.value;view.index=0;view.shown=false;draw();};head.append(choice);
 head.append(button('Esporta CSV · Anki',()=>saveBlob(new Blob([csv(deck)],{type:'text/csv;charset=utf-8'}),deck.title+'.csv')),button('Esporta lotto JSON',()=>saveBlob(new Blob([JSON.stringify(deck,null,2)],{type:'application/json'}),deck.title+'.json')));
 if(deck.kind==='dialogue'){const audio=button('Crea audio a due voci',async()=>{audio.disabled=true;try{await onAudio();}catch(e){audio.disabled=false;notify(e.message,true);}});audio.disabled=!!busy||deck.status!=='ready';head.append(audio);}
 if(deck.items.length<deck.requested&&artifact.id){const resume=button('Completa schede mancanti',async()=>{resume.disabled=true;try{await onResume();}catch(e){resume.disabled=false;notify(e.message,true);}});resume.disabled=!!busy;head.append(resume);}
 const input=node('input');input.type='file';input.accept='.json,application/json';input.hidden=true;
 input.onchange=async()=>{try{const file=input.files[0];if(!file)return;if(file.size>1600000)throw Error('Lotto oltre 1,6 MB.');const next=JSON.parse(await file.text());next.id=crypto.randomUUID().replaceAll('-','');if(!Array.isArray(next.items))throw Error('Lotto Studio non valido.');for(const i of next.items)i.id=crypto.randomUUID().replaceAll('-','');await onChange(studyPrefix+JSON.stringify(next)+'\n```');}catch(e){notify(e.message,true);}};
 const load=button('Importa lotto JSON',()=>input.click());load.disabled=!!busy;head.append(load,input);
 const cite=(host,item)=>{const row=node('div',null,'study-citations');for(const c of item.citations){const s=deck.sources.find(s=>s.id===c.source);if(!s)continue;row.append(button(`[${s.id}] ${s.name} · ${s.location}`,()=>{const d=modal(s.name+' · '+s.location);d.append(node('p','Citazione: '+c.quote),node('pre',s.text));if(s.media_origin&&deck.project_id)d.append(sourceOriginButton(api,deck.project_id,s,notify));if(s.url&&/^https?:\/\//i.test(s.url)){const a=node('a','Apri fonte originale');a.href=s.url;a.target='_blank';a.rel='noopener noreferrer';d.append(a);}d.showModal();}));}host.append(row);};
 function selected(){return deck.items.filter(i=>view.filter==='all'||view.filter==='new'&&!progress[i.id]||view.filter==='review'&&progress[i.id]?.remembered===0||view.filter==='known'&&progress[i.id]?.remembered===1);}
 function draw(){
  card.replaceChildren();bottom.replaceChildren();const rows=selected();view.index=Math.min(view.index,Math.max(0,rows.length-1));const item=rows[view.index];
  if(!item){card.append(node('p',deck.status==='building'?'Sto creando le schede…':'Nessuna scheda con questo filtro.'));return;}
  card.append(node('p',`${view.index+1} / ${rows.length}`,'study-note'),node('h2',item.question));const shown=view.shown||deck.kind!=='flashcards';
  if(shown){card.append(node('div',item.answer,'study-answer'));cite(card,item);if(item.explanation){const more=node('section',null,'study-explanation');more.append(node('h3','Spiegazione'),node('div',item.explanation.answer));cite(more,item.explanation);card.append(more);}}
  else card.append(button('Mostra risposta',()=>{view.shown=true;draw();}));
  const move=delta=>{view.index=(view.index+delta+rows.length)%rows.length;view.shown=false;draw();};bottom.append(button('← Precedente',()=>move(-1)),button('Successiva →',()=>move(1)));
  if(shown&&artifact.id){for(const [value,label] of [[false,'Da ripassare'],[true,'Ricordata']])bottom.append(button(label,async()=>{try{progress=(await api(`/canvas/${chatId}/study/${artifact.id}/progress`,{card_id:item.id,remembered:value})).items;move(1);}catch(e){notify(e.message,true);}}));
   const explain=button('Spiega',async()=>{explain.disabled=true;try{await onExplain(item.id);}catch(e){explain.disabled=false;notify(e.message,true);}});explain.disabled=!!busy;bottom.append(explain);
  }
  if(!busy)bottom.append(button('Modifica scheda',()=>{const d=modal('Modifica scheda'),form=node('div',null,'study-edit'),q=node('textarea'),a=node('textarea');q.value=item.question;a.value=item.answer;q.maxLength=1200;a.maxLength=6000;q.ariaLabel='Domanda';a.ariaLabel='Risposta';form.append(node('label','Domanda / titolo'),q,node('label','Risposta'),a,node('p','La modifica manuale conserva le citazioni; controlla che sostengano il nuovo testo. Il ripasso di questa scheda ricomincia.','study-note'));const save=button('Salva',async()=>{try{const next=structuredClone(deck),edited=next.items.find(i=>i.id===item.id);edited.question=q.value;edited.answer=a.value;delete edited.explanation;await onChange(studyPrefix+JSON.stringify(next)+'\n```');d.close();}catch(e){notify(e.message,true);}});form.append(save);d.append(form);d.showModal();}));
  const done=progress[item.id];if(done)card.append(node('p',`${done.remembered?'Ricordata':'Da ripassare'} · ${done.attempts} prove`,'study-note'));
 }
 draw();
}
