import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,sep} from 'node:path';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{build}=require('esbuild'),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const root=resolve('.'),png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
const server=createServer(async(req,res)=>{try{
 if(req.url.startsWith('/media/')){await new Promise(r=>setTimeout(r,180));res.setHeader('Content-Type','image/png');res.end(png);return;}
 if(req.url==='/'){res.end('<!doctype html><link rel="stylesheet" href="/static/style.css"><link rel="stylesheet" href="/static/slides.css"><link rel="stylesheet" href="/static/workspace.css"><style>html,body{margin:0;height:100%;overflow:hidden}.canvas-panel{position:fixed;inset:20px;width:620px;min-width:0;height:530px}.canvas-toolbar{flex:none}</style><aside id="canvas-panel" class="canvas-panel"><div class="canvas-toolbar"></div><div id="canvas-preview" class="rich canvas-preview"></div></aside>');return;}
 const path=resolve(root,'.'+req.url);if(!req.url.startsWith('/static/')||!path.startsWith(root+sep)){res.writeHead(404);res.end();return;}res.end(await readFile(path));
}catch{res.writeHead(500);res.end();}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
try{
 const built=await build({stdin:{contents:"import {renderSlides} from './ui/slides.js';import {initCanvasZoom} from './ui/canvas-zoom.js';window.renderSlides=renderSlides;window.zoom=initCanvasZoom();",resolveDir:root},bundle:true,write:false,format:'iife'});
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--disable-features=OverlayScrollbar']});const page=await browser.newPage({viewport:{width:1200,height:800}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:'+server.address().port);await page.addScriptTag({content:built.outputFiles[0].text});
 await page.evaluate(async()=>{
  window.target=document.querySelector('#canvas-preview');window.asset='a'.repeat(32);
  window.deck={version:1,engine:'llm',format:'16:9',title:'Live panels',references:[],active:0,pages:[{title:'Uno',status:'ready',html:'<style>body{margin:0;font:32px Manrope;background:#e0f1ea}.scene{width:1280px;height:720px;padding:80px 28px 28px;display:flex;gap:20px}</style><div class="scene"><section data-panel="1"><h1>Primo pannello</h1><img data-asset-id="'+asset+'"></section><section data-panel="2"><h1>Secondo pannello</h1></section><section data-panel="3"><h1>Terzo pannello</h1></section></div>',sources:[],notes:''},{title:'Due',status:'pending',html:'',sources:[],notes:''}],infographic:{version:1,durations:[8,8],options:{layout:'columns3',visual_mode:'decorative',panel_appearance:'sequence'}}};
  window.media=[{id:asset,mime:'image/png',path:'outputs/example.png',name:'Scene'}];window.options={busy:true,editable:false,job:{stage:'Scrittura scene'}};
  window.draw=()=>renderSlides(target,{id:'live-panels',content:'```h3-slides\n'+JSON.stringify(deck)+'\n```',media},options);
  await draw();window.original=target.querySelector('iframe');window.originalDoc=original.contentDocument;
  window.measure=()=>{const f=target.querySelector('iframe'),v=target.querySelector('.slides-viewport'),r=v?.getBoundingClientRect();return {frames:target.querySelectorAll('iframe').length,same:f===original,documentSame:f?.contentDocument===originalDoc,width:r?.width,height:r?.height,frameWidth:f?.getBoundingClientRect().width,ink:!!f?.contentDocument?.body?.innerText.trim(),outer:document.querySelector('.canvas-zoom-viewport').clientWidth};};
  window.samples=[];window.sampling=true;const sample=()=>{if(!sampling)return;samples.push(measure());requestAnimationFrame(sample);};requestAnimationFrame(sample);
 });
 await page.selectOption('select[aria-label="Zoom artefatto"]','150');await page.waitForTimeout(150);
 const baseline=await page.evaluate(()=>measure());
 await page.evaluate(()=>{samples=[];});
 for(let i=0;i<4;i++)await page.evaluate(async i=>{
  target.hidden=false;media.push({id:'audio-'+i,mime:'audio/wav',path:'outputs/voice-'+i+'.wav',name:'Voce'});
  deck.pages[1].notes='Scena successiva '+i;deck.infographic.durations[1]=8+i;options.job.stage='Voce '+i;
  await draw();await new Promise(r=>setTimeout(r,100));
 },i);
 await page.waitForTimeout(150);
 const metadata=await page.evaluate(()=>({current:measure(),samples}));
 assert.equal(metadata.current.same,true,'Audio or another scene changing must not recreate the visible iframe');
 assert.equal(metadata.current.documentSame,true);
 assert.ok(metadata.samples.every(x=>x.frames===1&&x.ink),'A polling update must not expose an empty or unprepared frame');
 assert.ok(metadata.samples.every(x=>Math.abs(x.width-baseline.width)<1&&Math.abs(x.height-baseline.height)<1),'Canvas geometry must remain stable with real zoom/scroll containers');
 // A genuinely changed referenced picture must still invalidate the page.
 await page.evaluate(async()=>{media[0]={...media[0],path:'outputs/replacement.png'};await draw();});
 assert.notEqual(await page.evaluate(()=>target.querySelector('iframe')===original),true,'A changed visible image must not be ignored');
 // Partial HTML must still update in real time without resetting the iframe.
 await page.evaluate(async()=>{deck.active=1;deck.pages[1].status='writing';deck.pages[1].html='<h1>Bozza nuova scena</h1>';await draw();window.original=target.querySelector('iframe');window.originalDoc=original.contentDocument;});
 await page.evaluate(async()=>{deck.pages[1].html='<h1>Bozza aggiornata</h1><p>Dettagli in arrivo</p>';await draw();});
 assert.equal(await page.evaluate(()=>measure().same),true);assert.equal(await page.evaluate(()=>originalDoc.querySelector('h1').textContent),'Bozza aggiornata');
 await page.evaluate(()=>{sampling=false;});assert.deepEqual(errors,[]);
 const report={status:'passed',metadata_updates_preserve_frame:true,live_drafts_update:true,zoom:1.5,samples:metadata.samples.length,real_generations:0};
 await mkdir('work/canvas-live-stability-2026-11-03',{recursive:true});await writeFile('work/canvas-live-stability-2026-11-03/browser.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await browser?.close();await new Promise(r=>server.close(r));}
