import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {resolve,sep} from 'node:path';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{build}=require('esbuild'),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const root=resolve('.'),folder='work/studio-ui-2026-11-03';
const server=createServer(async(req,res)=>{try{
 if(req.url==='/'){res.end('<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/static/style.css"><style>html,body{margin:0}#host{width:560px;max-width:100%;padding:18px;margin:0 auto;background:#fffefa}</style><div id="host"></div>');return;}
 const path=resolve(root,'.'+req.url);if(!req.url.startsWith('/static/')||!path.startsWith(root+sep)){res.writeHead(404);res.end();return;}res.end(await readFile(path));
}catch{res.writeHead(500);res.end();}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
try{
 const bundle=await build({stdin:{contents:"import {renderStudy} from './ui/study-view.js';window.renderStudy=renderStudy;",resolveDir:root},bundle:true,write:false,format:'iife'});
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});const page=await browser.newPage({viewport:{width:1000,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:'+server.address().port);await page.addScriptTag({content:bundle.outputFiles[0].text});
 await page.evaluate(()=>{
  window.reviews={};window.calls=[];
  window.deck={version:1,id:'test-set',kind:'flashcards',status:'ready',title:'La rivoluzione francese',requested:4,sources:[{id:'S1',name:'Storia',location:'pag. 12',text:'La presa della Bastiglia avvenne il 14 luglio 1789.',partial:true}],items:Array.from({length:4},(_,i)=>({id:'item'+i,question:['Quale evento avvenne nel 1789?','Che cosa accadde il 14 luglio?','Quale edificio fu conquistato?','Qual è il contesto storico?'][i],answer:'La presa della Bastiglia avvenne il 14 luglio 1789.',citations:[{source:'S1',quote:'La presa della Bastiglia avvenne il 14 luglio 1789.'}]}))};
  window.options={chatId:'chat',busy:false,api:async(path,body)=>{if(body){reviews[body.card_id]={remembered:Number(body.remembered),attempts:1};calls.push(body);}return {items:reviews};},onExplain:async id=>calls.push({explain:id}),onAudio:async voices=>calls.push(voices),onChange:async content=>calls.push({content}),notify:(message)=>{throw Error(message);}};
  window.artifact=()=>({id:'artifact',content:'```h3-study\n'+JSON.stringify(deck)+'\n```',media:[]});window.draw=()=>renderStudy(document.querySelector('#host'),artifact(),options);
 });
 await page.evaluate(()=>draw());assert.equal(await page.locator('.study-card h2').count(),1);assert.equal(await page.locator('.study-answer').count(),0);
 assert.equal(await page.getByRole('button',{name:'Esporta CSV · Anki',exact:true}).isVisible(),false);
 await page.locator('.study-view').focus();await page.keyboard.press('Space');assert.equal(await page.locator('.study-answer').count(),1);
 await page.keyboard.press('ArrowRight');assert.match(await page.locator('.study-card h2').innerText(),/14 luglio/);assert.equal(await page.locator('.study-answer').count(),0);
 await page.locator('.study-index > summary').click();await page.getByRole('searchbox',{name:'Cerca nello Studio'}).fill('contesto');assert.match(await page.locator('.study-card h2').innerText(),/contesto/);assert.equal(await page.locator('.study-index-list button').count(),1);
 await page.getByRole('button',{name:'Azzera',exact:true}).click();await page.getByRole('button',{name:'Mostra risposta',exact:true}).click();await page.getByRole('button',{name:'Ricordata',exact:true}).click();assert.match(await page.locator('.study-view > .study-note').first().innerText(),/1 ricordata/);
 await page.getByRole('button',{name:'Fonti · 1',exact:true}).click();assert.match(await page.locator('.study-modal').innerText(),/non necessariamente tutti i documenti/);assert.match(await page.locator('.study-modal').innerText(),/abbreviato/);await page.getByRole('button',{name:'Chiudi',exact:true}).click();
 const stable=await page.evaluate(async()=>{const before=document.querySelector('.study-view');await draw();return before===document.querySelector('.study-view');});assert.equal(stable,true,'Unchanged progress polling must preserve the reading surface');
 const kinds=[];
 for(const kind of ['summary','guide','faq','timeline','dialogue']){
  await page.evaluate(async kind=>{deck={...deck,id:'test-'+kind,kind};if(kind==='dialogue')deck.items=deck.items.map((item,i)=>({...item,question:i%2?'Conduttore B':'Conduttore A'}));await draw();},kind);
  assert.equal(await page.locator('[data-study-item]').count(),4,kind+' must initially show the whole document');
  if(kind==='faq'){assert.equal(await page.locator('.study-faq').count(),4);assert.equal(await page.locator('.study-faq[open]').count(),1);await page.locator('.study-faq > summary').nth(2).click();assert.equal(await page.locator('.study-faq').nth(2).evaluate(e=>e.open),true);}
  if(kind==='timeline')assert.equal(await page.locator('.study-timeline > li').count(),4);
  if(kind==='dialogue'){assert.equal(await page.locator('.study-speaker-b').count(),2);await page.locator('.study-audio-options > summary').click();await page.getByLabel('Studio · Voce A',{exact:true}).selectOption('limpida');await page.getByLabel('Studio · Voce B',{exact:true}).selectOption('aurora');await page.getByRole('button',{name:'Crea audio a due voci',exact:true}).click();assert.deepEqual(await page.evaluate(()=>calls.at(-1)),{voice_a:'limpida',voice_b:'aurora'});}
  await page.getByRole('button',{name:'Ripassa',exact:true}).click();assert.equal(await page.locator('[data-study-item]').count(),1);assert.equal(await page.locator('.study-answer').count(),1);await page.getByRole('button',{name:'Leggi tutto',exact:true}).click();assert.equal(await page.locator('[data-study-item]').count(),4);kinds.push(kind);
 }
 await page.evaluate(async()=>{deck={...deck,id:'rich-text',kind:'guide'};deck.items[0].answer='**Concetto**\n\n| Simbolo | Valore |\n| --- | --- |\n| x | 2 |\n\n$$x_i^2 + 1$$\n\n<img src=x onerror="window.studyTextInjected=true"><script>window.studyTextInjected=true</script>\nH3STUDYMATHPLACEHOLDER0END';await draw();});
 assert.equal(await page.locator('.study-answer strong').first().innerText(),'Concetto');assert.equal(await page.locator('.study-answer table').count(),1);assert.equal(await page.locator('.study-answer .katex').count(),1);assert.equal(await page.locator('.study-answer script,.study-answer img').count(),0);assert.equal(await page.evaluate(()=>window.studyTextInjected),undefined);
 // Any old pending progress request must not replace a newer Studio selection.
 const latest=await page.evaluate(async()=>{let release;const original=options.api;options={...options,api:()=>new Promise(r=>release=r)};deck={...deck,id:'old',title:'Obsoleto'};const old=draw();options={...options,api:original};deck={...deck,id:'latest',title:'Ultimo Studio'};await draw();release({items:{}});await old;return document.querySelector('.study-header h1').textContent;});assert.equal(latest,'Ultimo Studio');
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:await (async()=>{await mkdir(folder,{recursive:true});return folder+'/mobile.png';})(),fullPage:true});
 const mobile=await page.evaluate(()=>({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));assert.ok(mobile.scroll<=mobile.width+1,JSON.stringify(mobile));
 await page.setViewportSize({width:1000,height:900});await page.screenshot({path:folder+'/dialogue.png',fullPage:true});
 await page.evaluate(async()=>{deck={...deck,kind:'flashcards',id:'screenshot-cards',title:'La rivoluzione francese'};deck.items=deck.items.map((item,i)=>({...item,question:'Domanda di storia '+(i+1)}));await draw();});await page.screenshot({path:folder+'/flashcards.png',fullPage:true});
 assert.deepEqual(errors,[]);const report={passed:true,kinds,keyboard:true,index_search:true,source_overview:true,manual_review:true,stable_polling:true,stale_fetch_ignored:true,voice_profiles:true,mobile_no_horizontal_overflow:true,production_jobs:0};await writeFile(folder+'/views.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await browser?.close();await new Promise(r=>server.close(r));}
