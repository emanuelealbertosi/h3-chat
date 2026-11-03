import {studyVoices} from './voice-profiles.js';
import {studyStyles as styles} from './study-style.js';
export {renderStudy} from './study-view.js';
export const studyPrefix='```h3-study\n';
const defaults={kind:'flashcards',count:10,level:'standard',source_text:''};
const names={flashcards:'Flashcard',summary:'Sintesi e briefing',faq:'Domande frequenti',guide:'Guida allo studio',timeline:'Cronologia',dialogue:'Dialogo a due voci · script'};
function node(tag,text,cls){const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;}
function button(title,action){const b=node('button',title,'btn small no-export');b.type='button';b.onclick=action;return b;}
export function initStudy({getState,getAttachments=()=>[],onImport=async()=>{throw Error('Importazione non disponibile.');}}){
 styles();const panel=node('div');panel.id='study-options';panel.hidden=true;panel.className='prompt-slide-options';
 const intro=node('section',null,'study-settings-intro');intro.append(node('h3','Prepara il tuo materiale di studio'),node('p','Scegli il formato e il livello. Studio usa il testo qui sotto, gli allegati e le fonti RAG selezionate nella chat.'));panel.append(intro);
 const grid=node('div',null,'study-settings-grid');panel.append(grid);
 const field=(label,key,input,parent=grid)=>{const holder=node('label',null,'field');holder.append(node('span',label));input.dataset.study=key;holder.append(input);parent.append(holder);return input;};
 const kind=field('Documento','kind',node('select'));for(const [v,title] of Object.entries(names))kind.append(new Option(title,v));
 const count=field('Numero di schede / sezioni','count',node('input'));count.type='number';count.min=1;count.max=50;
 const level=field('Livello','level',node('select'));for(const [v,title] of [['simple','Semplice'],['standard','Standard'],['advanced','Avanzato']])level.append(new Option(title,v));
 const source=field('Testo da studiare · facoltativo','source_text',node('textarea'),panel);source.parentElement.classList.add('study-settings-source');source.rows=7;source.maxLength=60000;source.placeholder='Incolla qui un testo, oppure lascia vuoto per usare gli allegati e le fonti RAG selezionate.';
 const voices=node('section',null,'study-settings-voices');voices.append(node('h3','Voci del dialogo'));studyVoices(voices);voices.append(node('p','Prima viene creato lo script con le citazioni. Potrai generare l’audio dal canvas.','small-note'));panel.append(voices);
 const renderKind=()=>{voices.hidden=kind.value!=='dialogue';count.previousElementSibling.textContent=kind.value==='flashcards'?'Numero di flashcard':kind.value==='dialogue'?'Numero di battute':'Numero di sezioni';};kind.addEventListener('change',renderKind);
 const help=node('section',null,'study-settings-help');help.append(node('p','Le risposte restano legate alle fonti e le citazioni aprono il passaggio originale. Il RAG può selezionare soltanto alcuni estratti: Studio non dichiara di aver letto tutto il libro.'));panel.append(help);
 const actions=node('div',null,'study-settings-actions');panel.append(actions);
 actions.append(button('Importa una fonte nel progetto',()=>{
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
 function set(value){const v={...defaults,...value};kind.value=v.kind;count.value=v.count;level.value=v.level;source.value=v.source_text;renderKind();}
 function render(){panel.hidden=document.querySelector('#lab-tool').value!=='study';}
 panel.addEventListener('change',()=>{const v=read();try{localStorage.setItem('h3-study-options',JSON.stringify({...v,source_text:''}));}catch{}});
 document.querySelector('#lab-tool').addEventListener('change',render);set(saved);render();return{read,set,render};
}

function modal(title){const d=node('dialog',null,'study-modal');d.append(node('h2',title));d.append(button('Chiudi',()=>d.close()));d.addEventListener('close',()=>d.remove());document.body.append(d);return d;}
