import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,sep} from 'node:path';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{build}=require('esbuild'),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const root=resolve('.'),png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
const server=createServer(async(req,res)=>{
 try{
  if(req.url.startsWith('/media/')){if(req.url.includes('slow'))await new Promise(r=>setTimeout(r,500));res.writeHead(200,{'Content-Type':'image/png'});res.end(png);return;}
  if(req.url==='/'){res.end('<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/static/style.css"><link rel="stylesheet" href="/static/slides.css"><style>html,body{margin:0;height:100%;overflow:hidden}#host{position:absolute;inset:20px;width:650px;height:500px;display:flex}#preview{min-width:0}</style><section id="host"><div id="preview" class="canvas-preview"></div></section>');return;}
  const path=resolve(root,'.'+req.url);if(!path.startsWith(root+sep)||!req.url.startsWith('/static/')){res.writeHead(404);res.end();return;}
  res.end(await readFile(path));
 }catch{res.writeHead(500);res.end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
try{
 const built=await build({stdin:{contents:"import {renderSlides} from './ui/slides.js';window.renderSlides=renderSlides;",resolveDir:root},bundle:true,write:false,format:'iife',loader:{'.woff':'dataurl','.woff2':'dataurl','.ttf':'dataurl'}});
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});const page=await browser.newPage({viewport:{width:1100,height:760}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:'+server.address().port);await page.addScriptTag({content:built.outputFiles[0].text});
 await page.evaluate(async()=>{
  window.deck={version:1,engine:'llm',format:'16:9',title:'Streaming',references:[],active:0,pages:[{title:'Prima',status:'writing',html:'<style>body{margin:0;background:#e0f1ea;font:32px Manrope}#moving{width:80px;height:80px;background:#087f8c;animation:move 10s linear infinite}@keyframes move{to{transform:translateX(500px)}}</style><h1>Bozza iniziale</h1><div id="moving"></div>',sources:[],notes:'Nota originale'}]};
  window.media=[{id:'a'.repeat(32),mime:'image/png',path:'outputs/slow.png',name:'Lenta'}];window.options={busy:true,editable:false,job:{stage:'HTML · 100 caratteri'},onResume:async()=>{}};
  window.value=()=>({id:'stream-fixture',content:'```h3-slides\n'+JSON.stringify(deck)+'\n```',media});
  await renderSlides(document.getElementById('preview'),value(),options);
  window.originalFrame=document.querySelector('#preview iframe');window.originalDoc=originalFrame.contentDocument;
  window.measure=()=>{const viewport=document.querySelector('.slides-viewport'),frame=document.querySelector('#preview iframe'),r=viewport.getBoundingClientRect();return {frames:document.querySelectorAll('#preview iframe').length,width:r.width,height:r.height,scroll:document.getElementById('preview').scrollWidth,client:document.getElementById('preview').clientWidth,frameWidth:frame.getBoundingClientRect().width,iframeSame:frame===originalFrame,documentSame:frame.contentDocument===originalDoc,title:frame.contentDocument.querySelector('h1')?.textContent};};
 });
 const initial=await page.evaluate(()=>measure());assert.equal(initial.iframeSame,true);assert.ok(initial.scroll<=initial.client+1,JSON.stringify(initial));assert.ok(Math.abs(initial.frameWidth-initial.width)<1,JSON.stringify(initial));
 const motion=await page.evaluate(()=>originalDoc.getAnimations()[0].currentTime);
 for(let i=0;i<4;i++)await page.evaluate(async i=>{options.job.stage='HTML · '+i+' caratteri';await renderSlides(document.getElementById('preview'),value(),options);},i);
 await page.waitForTimeout(150);const afterPoll=await page.evaluate(()=>({measure:measure(),time:originalDoc.getAnimations()[0].currentTime}));assert.equal(afterPoll.measure.documentSame,true);assert.ok(afterPoll.time>motion,'Progress-only polls must not restart CSS motion');
 await page.evaluate(()=>{
  window.samples=[];window.sampling=true;const sample=()=>{if(!sampling)return;samples.push(measure());requestAnimationFrame(sample);};requestAnimationFrame(sample);
  deck.pages[0].html='<style>body{margin:0;background:#e0f1ea;font:32px Manrope;overflow:auto!important}#large{position:absolute;width:1900px;height:1400px}</style><h1>Contenuto aggiornato</h1><img data-asset-id="'+('a'.repeat(32))+'"><div id="large"></div><script>parent.__h3UnsafeStreamProbe=true</script>';
  window.pending=renderSlides(document.getElementById('preview'),value(),options);
 });
 await page.waitForTimeout(100);assert.equal(await page.evaluate(()=>measure().title),'Bozza iniziale','Keep the previous draft visible while assets are prepared');
 await page.evaluate(async()=>{await pending;sampling=false;});
 const result=await page.evaluate(()=>({measure:measure(),samples,rootOverflow:getComputedStyle(originalDoc.documentElement).overflow,bodyOverflow:getComputedStyle(originalDoc.body).overflow,injected:window.__h3UnsafeStreamProbe,sandbox:originalFrame.getAttribute('sandbox')}));
 assert.equal(result.measure.title,'Contenuto aggiornato');assert.equal(result.measure.iframeSame,true);assert.equal(result.measure.documentSame,true);assert.equal(result.rootOverflow,'hidden');assert.equal(result.bodyOverflow,'hidden');assert.equal(result.injected,undefined);assert.equal(result.sandbox,'allow-same-origin');
 assert.ok(result.samples.length>=5);for(const s of result.samples){assert.equal(s.frames,1);assert.equal(s.iframeSame,true);assert.equal(s.documentSame,true);assert.ok(s.scroll<=s.client+1,JSON.stringify(s));assert.ok(Math.abs(s.width-initial.width)<1,JSON.stringify(s));assert.ok(Math.abs(s.height-initial.height)<1,JSON.stringify(s));}
 await page.evaluate(async()=>{
  deck.pages[0].html='<h1>Bozza lenta superata</h1><img data-asset-id="'+('a'.repeat(32))+'">';
  const old=renderSlides(document.getElementById('preview'),value(),options);
  await new Promise(r=>setTimeout(r,50));deck.pages[0].html='<h1>Ultima bozza disponibile</h1>';
  await renderSlides(document.getElementById('preview'),value(),options);await old;
 });
 assert.equal(await page.evaluate(()=>measure().title),'Ultima bozza disponibile','A slower obsolete render must not replace the newest draft');
 // A newly completed page must still enable editing; metadata polls must not freeze controls.
 await page.evaluate(async()=>{deck.pages[0].status='ready';options={...options,busy:false,editable:true,job:null,onChange:async()=>{}};await renderSlides(document.getElementById('preview'),value(),options);});assert.equal(await page.locator('#slide-edit').isDisabled(),false);
 await mkdir('work/canvas-stream-stability-2026-10-24',{recursive:true});await page.screenshot({path:'work/canvas-stream-stability-2026-10-24/stable.png'});
 assert.deepEqual(errors,[]);const report={status:'passed',samples:result.samples.length,initial_geometry:initial,final_geometry:result.measure,progress_poll_keeps_animation:true,streamed_content_visible:true,obsolete_render_discarded:true,root_scrollbars_hidden:true,sandbox_preserved:true,real_generation_started:false};
 await writeFile('work/canvas-stream-stability-2026-10-24/verification.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}finally{await browser?.close();await new Promise(r=>server.close(r));}
