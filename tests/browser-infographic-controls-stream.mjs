import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,sep} from 'node:path';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{build}=require('esbuild'),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const root=resolve('.'),png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
const server=createServer(async(req,res)=>{try{
 if(req.url.startsWith('/media/')){await new Promise(r=>setTimeout(r,400));res.setHeader('Content-Type','image/png');res.end(png);return;}
 if(req.url==='/'){res.end('<!doctype html><link rel="stylesheet" href="/static/slides.css"><style>[hidden]{display:none!important}#controls{width:320px}#host{position:fixed;right:20px;top:20px;width:650px;height:500px;display:flex}#preview{min-width:0;max-height:100%;overflow:auto}</style><main id="controls"><select id="lab-tool"><option value="infographic">Infografica</option></select><section id="prompt-context"></section></main><section id="host"><div id="preview" class="canvas-preview"></div></section>');return;}
 const path=resolve(root,'.'+req.url);if(!req.url.startsWith('/static/')||!path.startsWith(root+sep)){res.writeHead(404);res.end();return;}res.end(await readFile(path));
}catch{res.writeHead(500);res.end();}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
try{
 const built=await build({stdin:{contents:`import {renderSlides} from './ui/slides.js';import {initInfographics} from './ui/infographics.js';window.renderSlides=renderSlides;const state={settings:{create_model:'qwen'},slide_options:{background_styles:true},models:[{id:'qwen',name:'Qwen',architecture:'qwen21',ready:true,capabilities:['create']},{id:'moss',name:'MOSS INT8',architecture:'moss',ready:true,capabilities:['create']}]};window.info=initInfographics({api:async()=>({items:[]}),getState:()=>state});info.render();`,resolveDir:root},bundle:true,write:false,format:'iife'});
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});const page=await browser.newPage({viewport:{width:1100,height:760}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:'+server.address().port);await page.addScriptTag({content:built.outputFiles[0].text});
 const model=page.locator('[data-info="image_model"]');assert.equal(await model.isVisible(),true);
 assert.equal(await model.evaluate(e=>e.closest('label').previousElementSibling.dataset.infographicField),'images');
 await model.selectOption('moss');
 for(const mode of ['sequence','decorative','normal']){await page.click(`[data-infographic-field="visual_mode"] [data-value="${mode}"]`);const chosen=await page.evaluate(()=>info.read());assert.equal(chosen.image_model,'moss');assert.equal(chosen.character_animation,'illustrated');}
 assert.equal(await page.locator('[data-infographic-field="character_animation"]').isVisible(),false);
 await page.click('[data-infographic-field="animation_engine"] [data-value="motion"]');assert.equal(await page.locator('[data-infographic-field="character_animation"]').isVisible(),true);
 await page.click('[data-infographic-field="animation_engine"] [data-value="classic"]');
 const reports=[];
 for(const mode of ['normal','decorative','sequence']){
  await page.evaluate(async mode=>{
   document.getElementById('controls').hidden=true;
   window.deck={version:1,engine:'llm',title:'Live '+mode,format:'16:9',references:[],active:0,pages:[{title:'Scena',status:'writing',html:'<style>body{margin:0;font:32px Manrope;background:#e0f1ea}</style><h1>Prima bozza</h1>',notes:'',sources:[]}],infographic:{version:1,durations:[4],transition:'fade',sfx:'none',options:{visual_mode:mode,layout:'full'}}};
   window.media=[{id:'a'.repeat(32),name:'Image',mime:'image/png',path:'outputs/slow.png'}];window.options={busy:true,editable:false,job:{stage:'Scrittura'}};
   window.value=()=>({id:'live-'+mode,content:'```h3-slides\n'+JSON.stringify(deck)+'\n```',media});window.draw=()=>renderSlides(document.getElementById('preview'),value(),options);
   await draw();window.originalFrame=document.querySelector('#preview iframe');window.originalDoc=originalFrame.contentDocument;
   window.measure=()=>{const v=document.querySelector('.slides-viewport'),r=v.getBoundingClientRect(),f=document.querySelector('#preview iframe');return {frames:document.querySelectorAll('#preview iframe').length,same:f===originalFrame,doc:f.contentDocument===originalDoc,width:r.width,height:r.height,frameWidth:f.getBoundingClientRect().width,title:f.contentDocument.querySelector('h1')?.textContent};};
  },mode);
  const initial=await page.evaluate(()=>measure());
  await page.evaluate(async()=>{for(let i=0;i<4;i++){options.job.stage='Scrittura '+i;await draw();}deck.pages[0].html='<style>body{background:white}</style>';await draw();});
  assert.equal((await page.evaluate(()=>measure())).title,'Prima bozza','A head-only repair cannot clear the last visible draft');
  await page.evaluate(()=>{window.samples=[];window.sampling=true;const sample=()=>{if(!sampling)return;samples.push(measure());requestAnimationFrame(sample);};requestAnimationFrame(sample);deck.pages[0].html='<style>body{margin:0;font:32px Manrope;background:#e0f1ea}</style><h1>Nuova bozza</h1><img data-asset-id="'+('a'.repeat(32))+'"><script>parent.__unsafe=true</script>';window.pending=draw();});
  await page.waitForTimeout(80);assert.equal((await page.evaluate(()=>measure())).title,'Prima bozza');
  await page.evaluate(async()=>{await pending;sampling=false;});
  const proof=await page.evaluate(()=>({final:measure(),samples,injected:window.__unsafe}));
  assert.equal(proof.final.title,'Nuova bozza');assert.equal(proof.final.same,true);assert.equal(proof.final.doc,true);assert.equal(proof.injected,undefined);
  for(const r of proof.samples){assert.equal(r.frames,1);assert.equal(r.same,true);assert.equal(r.doc,true);assert.ok(Math.abs(r.width-initial.width)<1);assert.ok(Math.abs(r.height-initial.height)<1);assert.ok(Math.abs(r.frameWidth-r.width)<1);}
  await page.evaluate(async()=>{deck.pages[0].status='ready';options={busy:false,editable:true,onChange:async()=>{}};await draw();window.readyFrame=document.querySelector('#preview iframe');await draw();});
  assert.equal(await page.evaluate(()=>readyFrame===document.querySelector('#preview iframe')),true,'A ready scene must survive unchanged polls');
  assert.equal(await page.locator('[data-play]').count(),1);reports.push({mode,samples:proof.samples.length,stable_iframe:true,stable_geometry:true,streamed_content_visible:true,ready_player_preserved:true});
 }
 assert.deepEqual(errors,[]);await mkdir('work/infographic-controls-stream-qa',{recursive:true});await writeFile('work/infographic-controls-stream-qa/verification.json',JSON.stringify({model_selector_visible:true,model_preserved_across_modes:true,characters_optional:true,reports},null,2));console.log(JSON.stringify({model_selector_visible:true,model_preserved_across_modes:true,characters_optional:true,reports}));
}finally{await browser?.close();await new Promise(r=>server.close(r));}
