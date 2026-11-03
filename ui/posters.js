import {escape as esc} from './render.js';
import {labImageDefault} from './lab-image-model.js';
import fontFamilies from '../static/typography-fonts.json';
export const posterFormats=[['A3','A3 verticale · stampa'],['A4','A4 verticale · stampa'],['A3-landscape','A3 orizzontale'],['A4-landscape','A4 orizzontale'],['4:5','4:5 · social'],['9:16','9:16 · storia'],['1:1','Quadrato'],['16:9','16:9 · orizzontale']];
const defaults={format:'A3',style:'auto',count:1,images:'auto',image_model:'',safe_margin:5,composition:'html',reference_mode:'none',reference_asset_id:'',reference_page:1,reference_image:0,visual_megapixels:2,visual_strength:.9,lettering:'auto',text_effect:'auto',heading_font:'auto',body_font:'auto',typography_engine:'expressive',text_renderer:'html'};
export function initPosters({getState,getAttachments=()=>[]}){
 const key='h3-poster-preferences';let saved={};try{saved=JSON.parse(localStorage.getItem(key)||'{}');if(!localStorage.getItem('h3-poster-rich-html-v1')){saved.composition='html';localStorage.setItem(key,JSON.stringify(saved));localStorage.setItem('h3-poster-rich-html-v1','1');}}catch{}
 const panel=document.createElement('section');panel.id='posters-options';panel.hidden=true;
 const select=(name,title,values)=>`<label class="field"><span>${title}</span><select data-poster="${name}">${values.map(([v,t])=>`<option value="${esc(v)}">${esc(t)}</option>`).join('')}</select></label>`;
 panel.innerHTML='<p>Una locandina autonoma: titolo protagonista, immagini ampie e testi modificabili. Le istruzioni nel prompt prevalgono sulle scelte qui sotto.</p><div class="settings-grid">'+
  select('format','Formato',posterFormats)+select('style','Direzione artistica',[['auto','Automatico · dal prompt'],['editorial','Editoriale'],['event','Evento / spettacolo'],['cultural','Culturale'],['commercial','Promozionale'],['comic','Fumetto / illustrato'],['minimal','Essenziale']])+
  select('reference_mode','Da un riferimento grafico',[['none','Nuova locandina'],['reproduce','Riproduci il layout allegato'],['improve','Migliora il layout allegato']])+
  '<label class="field" data-poster-reference><span>Locandina da analizzare · distinta dalle foto</span><select data-poster="reference_asset_id"><option value="">Automatico · solo se un unico allegato</option></select></label><label class="field" data-poster-reference><span>Pagina del PDF · 1 per immagini</span><input data-poster="reference_page" type="number" min="1" max="1000" value="1"></label><p class="small-note" data-poster-reference>Allega un’immagine o un PDF e abilita Vision sul modello LLM. Vengono analizzati testi, colori e posizioni; foto e testi sono ricomposti separatamente. Scegli il formato di uscita desiderato: per conservarne le proporzioni usa quello del riferimento. Testi illeggibili e font mancanti vengono segnalati; non è una copia identica dei pixel.</p>'+
  '<label class="field"><span>Varianti complete</span><input data-poster="count" type="number" min="1" max="6" step="1" value="1"></label>'+
  select('typography_engine','Compositore delle scritte',[['expressive','Espressivo · HTML/SVG come nelle slide'],['preset','Stili predefiniti · senza nuovo LLM']])+
  select('lettering','Stile delle scritte',[['auto','Automatico · coordinato alla grafica'],['editorial','Editoriale / elegante'],['playful','Giocoso'],['cinematic','Cinematografico'],['handwritten','Manoscritto'],['comic','Fumetto'],['retro','Rétro'],['neon','Neon'],['minimal','Essenziale']])+
  select('text_effect','Effetti su titoli e testi brevi',[['auto','Automatico · segue lo stile'],['plain','Senza effetti'],['shadow','Ombra morbida'],['outline','Contorno'],['extruded','Rilievo / tridimensionale'],['neon','Bagliore neon'],['metallic','Metallico'],['letterpress','Stampa a rilievo']])+
  select('heading_font','Carattere titoli',[['auto','Automatico'],...fontFamilies.map(n=>[n,n])])+select('body_font','Carattere testi',[['auto','Automatico'],...fontFamilies.map(n=>[n,n])])+
  select('composition','Composizione',[['html','Grafica ricca HTML/CSS · come nelle slide'],['moss_layout','Avanzata · piano MOSS con aree riservate']])+
  '<div data-moss-poster>'+select('text_renderer','Chi disegna le scritte',[['html','Tutti i testi HTML/SVG · modificabili'],['moss_short','MOSS per brevi titoli · testo lungo HTML/SVG']])+'</div>'+
  select('images','Immagini',[['auto','Automatico · allegate o generate'],['attached','Usa le immagini allegate'],['existing','Solo immagini disponibili · nessuna generazione'],['generate','Genera illustrazioni IA'],['none','Solo tipografia e grafica']])+
  '<label class="field" data-advanced-only><span>Modello per le illustrazioni</span><select data-poster="image_model"></select></label><label class="field" data-advanced-only><span>Margine di sicurezza testi (%)</span><input data-poster="safe_margin" type="number" min="2" max="15" step="1" value="5"></label>'+
  '<label class="field" data-moss-poster><span>Immagine guida · 0 nessuna, 1 prima immagine allegata</span><input data-poster="reference_image" type="number" min="0" max="32" step="1" value="0"></label><label class="field" data-moss-poster><span>Megapixel della grafica completa</span><input data-poster="visual_megapixels" type="number" min="0.25" max="4" step="0.25" value="2"></label><label class="field" data-moss-poster data-advanced-only><span>Intensità di ricostruzione della guida</span><input data-poster="visual_strength" type="number" min="0.05" max="1" step="0.05" value="0.9"></label></div><p class="small-note" data-poster-note></p>';
 document.querySelector('#slides-options').after(panel);
 const fields=[...panel.querySelectorAll('[data-poster]')];let signature='';
 function referenceSelection(){
  const select=panel.querySelector('[data-poster="reference_asset_id"]'),refs=getAttachments().filter(m=>m.mime.startsWith('image/')||m.mime==='application/pdf');
  const previous=select.dataset.restoreValue??select.value;delete select.dataset.restoreValue;
  const valid=refs.some(m=>m.id===previous);
  const value=valid?previous:refs.length===1?refs[0].id:'';
  const signature=JSON.stringify(refs.map(m=>[m.id,m.name]));
  if(select.dataset.signature!==signature){select.dataset.signature=signature;select.replaceChildren(new Option('Automatico · solo se un unico allegato',''),...refs.map(m=>new Option(m.name,m.id)));}
  select.value=value;saved.reference_asset_id=value;
  if(previous&&previous!==value)panel.querySelector('[data-poster="reference_page"]').value='1';
 }
 function read(){referenceSelection();return Object.fromEntries(fields.map(f=>[f.dataset.poster,f.type==='number'?Number(f.value):f.value]));}
 function persist(){saved=read();try{localStorage.setItem(key,JSON.stringify(saved));}catch{}}
 function render(){
  panel.hidden=document.querySelector('#lab-tool').value!=='poster';
  const state=getState();if(!state)return;
  const refMode=panel.querySelector('[data-poster="reference_mode"]').value;
  for(const e of panel.querySelectorAll('[data-poster-reference]'))e.hidden=refMode==='none';
  referenceSelection();
  const hybrid=panel.querySelector('[data-poster="composition"]').value==='moss_layout';
  for(const e of panel.querySelectorAll('[data-moss-poster]'))e.hidden=!hybrid;
  panel.querySelector('[data-poster="typography_engine"]').closest('label').hidden=!hybrid;
  const models=state.models.filter(m=>m.ready&&m.capabilities.includes('create')&&(!hybrid||m.architecture==='moss')),next=JSON.stringify([hybrid,...models.map(m=>[m.id,m.name])]);
  const select=panel.querySelector('[data-poster="image_model"]');
  if(next!==signature){signature=next;const previous=select.value||saved.image_model||'';select.innerHTML=`<option value="">Predefinito · ${hybrid?'MOSS disponibile':esc(labImageDefault(state)?.name||'modello immagini')}</option>`+models.map(m=>`<option value="${esc(m.id)}">${esc(m.name)}</option>`).join('');if(previous&&!models.some(m=>m.id===previous)){const o=document.createElement('option');o.value=previous;o.textContent='Modello salvato non compatibile o non disponibile';select.append(o);}select.value=previous;}
  const cpu=state.execution?.mode==='cpu';panel.querySelector('[data-poster="images"] option[value="generate"]').disabled=cpu;
  panel.querySelector('[data-poster="composition"] option[value="moss_layout"]').disabled=cpu;
  panel.querySelector('[data-poster-note]').textContent=cpu?'Modalità CPU: puoi usare immagini allegate, tipografia, HTML e SVG. La generazione di nuove illustrazioni richiede GPU.':hybrid?'MOSS crea lo sfondo completo. Il compositore espressivo disegna testi HTML/SVG con colori, forme ed effetti coordinati; i riquadri del piano proteggono la leggibilità. Puoi affidare a MOSS solo brevi titoli: quelle scritte resteranno nei pixel. Una sola guida img2img. Scegli immagini Automatico o Genera.':'Composizione libera come nelle slide: HTML/CSS, SVG, decorazioni, titoli espressivi e livelli coordinati alle immagini. Testi modificabili e separati dalle illustrazioni; il prompt guida lo stile. Esportazioni PDF, PNG, HTML e PowerPoint. PowerPoint modificabile separa testi HTML, riquadri e immagini; PowerPoint fedele conserva la grafica come immagine unica. Abbondanze e conversione CMYK non sono incluse.';
 }
 function set(value,store=true){saved={...defaults,...value};for(const f of fields)if(f.dataset.poster!=='image_model'&&saved[f.dataset.poster]!==undefined)f.value=String(saved[f.dataset.poster]);panel.querySelector('[data-poster="reference_asset_id"]').dataset.restoreValue=saved.reference_asset_id||'';signature='';render();const m=fields.find(f=>f.dataset.poster==='image_model');if(saved.image_model&&[...m.options].some(o=>o.value===saved.image_model))m.value=saved.image_model;if(store)persist();}
 for(const f of fields)f.addEventListener('change',()=>{if(f.dataset.poster==='reference_mode'&&f.value!=='none')panel.querySelector('[data-poster="composition"]').value='html';persist();render();});
 document.querySelector('#lab-tool').addEventListener('change',render);set(saved,false);
 return {read,render,set};
}
