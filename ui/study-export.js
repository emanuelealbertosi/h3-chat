import {saveBlob} from './render.js';
import {printableHtml,exportDocx} from './exports.js';
import {studyText} from './study-text.js';

const element=(tag,text)=>{const e=document.createElement(tag);e.textContent=text;return e;};
export function studyDocument(deck){
 const root=document.createElement('section');root.style.cssText='font:15px/1.7 Arial,sans-serif;color:#20383b;background:white;';
 root.append(element('h1',deck.title),element('p',`${deck.items.length} schede / sezioni · basate sugli estratti conservati nello Studio.`));
 for(const [index,item] of deck.items.entries()){
  const heading=element('h2',`${index+1}. ${item.question}`);heading.style.cssText='break-after:avoid;margin-top:28px;font-size:21px;';root.append(heading);
  const answer=document.createElement('div');studyText(answer,item.answer);root.append(...answer.childNodes);
  for(const citation of item.citations){const source=deck.sources.find(s=>s.id===citation.source);const quote=element('p',`[${citation.source}] ${source?.name||''} · ${source?.location||''}\n«${citation.quote}»`);quote.style.cssText='font-size:12px;color:#52655e;white-space:pre-wrap;';root.append(quote);}
  if(item.explanation){root.append(element('h3',item.explanation.followup?item.explanation.question:'Spiegazione'));const text=document.createElement('div');studyText(text,item.explanation.answer);root.append(...text.childNodes);for(const citation of item.explanation.citations)root.append(element('p',`[${citation.source}] «${citation.quote}»`));}
 }
 root.append(element('h2','Fonti utilizzate'),element('p','Il documento usa gli estratti selezionati, non necessariamente tutti i documenti o tutto il libro.'));
 for(const source of deck.sources){root.append(element('h3',`[${source.id}] ${source.name} · ${source.location}`));if(source.url)root.append(element('p',source.url));const text=element('p',source.text);text.style.whiteSpace='pre-wrap';root.append(text);}
 // Keep the standalone reading document independent of the app's decorative
 // heading fonts (some PDF ligatures otherwise copy as private-use glyphs).
 for(const text of root.querySelectorAll('h1,h2,h3,p,td,th,pre,li'))if(!text.closest('.katex')){text.style.fontFamily='Arial, sans-serif';text.style.fontVariantLigatures='none';}
 return root;
}
export async function exportStudy(deck,kind,api){
 const name=deck.title.replace(/[^\p{L}\p{N}\s_-]/gu,'').trim().slice(0,80)||'Studio';
 if(kind==='md'){let text='# '+deck.title+'\n\n';for(const [i,item] of deck.items.entries()){text+=`## ${i+1}. ${item.question}\n\n${item.answer}\n\n`;for(const c of item.citations)text+=`[${c.source}] «${c.quote}»\n\n`;if(item.explanation)text+='### Spiegazione\n\n'+item.explanation.answer+'\n\n';}text+='## Fonti utilizzate\n\n';for(const s of deck.sources)text+=`### [${s.id}] ${s.name} · ${s.location}\n\n${s.text}\n\n`;saveBlob(new Blob([text],{type:'text/markdown;charset=utf-8'}),name+'.md');return;}
 const root=studyDocument(deck),mount=document.createElement('div');mount.style.cssText='position:fixed;left:-20000px;top:0;width:760px;';mount.append(root);document.body.append(mount);
 try{
  if(kind==='docx')return await exportDocx(root,deck.title);
  const html=await printableHtml(root);
  if(kind==='pdf'){const result=await api('/export/pdf',{title:deck.title,html});const a=document.createElement('a');a.href=result.url;a.download=name+'.pdf';a.click();return;}
  if(kind!=='html')throw Error('Formato Studio non disponibile.');
  const doc=document.implementation.createHTMLDocument(deck.title);doc.documentElement.lang='it';const charset=doc.createElement('meta');charset.charset='utf-8';doc.head.prepend(charset);const style=doc.createElement('style');style.textContent='body{font:15px/1.8 Arial,sans-serif;color:#20383b;max-width:850px;margin:40px auto;padding:0 24px}h2,h3{break-after:avoid}@media print{body{margin:0;max-width:none}}';doc.head.append(style);doc.body.innerHTML=html;saveBlob(new Blob(['<!doctype html>\n'+doc.documentElement.outerHTML],{type:'text/html;charset=utf-8'}),name+'.html');
 }finally{mount.remove();}
}
