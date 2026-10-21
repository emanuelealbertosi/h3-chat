import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {readFile,mkdir} from 'node:fs/promises';
import {build} from 'esbuild';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const bundle=await build({stdin:{contents:`
 import {initImageRequest,imageRequestParameters} from './ui/image-request.js';
 import {renderImagePreferences,selectImagePreferencesModel} from './ui/image-settings.js';
 const defaults={width:1024,height:1024,steps:30,image_cfg:3,image_sampler:'euler',image_scheduler:'simple',seed:42,strength:1,negative_prompt:'',image_aspect:'auto',image_overrides:{},image_advanced:false};
 const models=['qwen21','qwen21-turbo','anima','krea2','moss'].map(id=>({id,name:id,architecture:id==='qwen21-turbo'?'qwen21':id,engine:'vision',capabilities:['create','edit'],width:1024,height:1024,steps:30,cfg:3,sampler:'euler',scheduler:'simple',strength:1}));
 const state={models,settings:defaults,image_options:{request_controls:true,vision_samplers:['euler'],vision_schedulers:['simple']}};
 let value=JSON.parse(localStorage.getItem('controls')||'null')||{image_model:'qwen21'},controls;
 const set=v=>{value=v;localStorage.setItem('controls',JSON.stringify(value));controls?.render();};
 controls=initImageRequest({holder:document.querySelector('#request'),getState:()=>state,visualControls:{read:()=>value,set},notify:message=>{throw Error(message);}});controls.render();
 const draft=structuredClone(defaults);
 window.fixture={select:id=>set({...value,image_model:id}),parameters:()=>imageRequestParameters(state,value),preferences:id=>{selectImagePreferencesModel(id);renderImagePreferences(document.querySelector('#preferences'),draft,state);},draft};
 `,resolveDir:process.cwd()},bundle:true,write:false,format:'iife',platform:'browser',target:'es2022'});
const css=await Promise.all(['static/style.css','static/composer.css'].map(path=>readFile(path,'utf8')));
const server=createServer((req,res)=>{res.setHeader('Content-Type',req.url==='/fixture.js'?'application/javascript':req.url==='/fixture.css'?'text/css':'text/html');res.end(req.url==='/fixture.js'?bundle.outputFiles[0].text:req.url==='/fixture.css'?css.join('\n'):'<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/fixture.css"><main style="max-width:620px;margin:auto;padding:12px"><div id="request" class="prompt-field"><div id="model-picker">Modello immagini</div></div><div id="preferences"></div></main><script src="/fixture.js"></script>');});
server.listen(0,'127.0.0.1');await once(server,'listening');
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']}),page=await browser.newPage({viewport:{width:900,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:'+server.address().port);
 const aspect=page.locator('[data-image-request="aspect"]');
 for(const [model,format] of [['qwen21','16:9'],['qwen21-turbo','9:16'],['anima','3:2'],['krea2','4:3'],['moss','1:1']]){
  await page.evaluate(id=>window.fixture.select(id),model);
  assert(await page.locator('#request').getByRole('heading',{name:'Formato immagine',exact:true}).isVisible());
  assert.equal(await aspect.locator('option').count(),8);
  assert(await aspect.evaluate(e=>!!(e.closest('section').compareDocumentPosition(document.querySelector('#model-picker'))&Node.DOCUMENT_POSITION_FOLLOWING)));
  await aspect.selectOption(format);assert.equal((await page.evaluate(()=>window.fixture.parameters())).aspect,format);
  await page.evaluate(id=>window.fixture.preferences(id),model);
  const saved=page.locator('[data-image-setting="aspect"]');assert(await saved.isVisible());
  assert.equal(await page.locator('#image-advanced').isChecked(),false);
  await saved.selectOption(format);assert.equal(await page.evaluate(id=>window.fixture.draft.image_overrides[id].aspect,model),format);
  assert.equal(await page.locator('#image-advanced').isChecked(),false);
 }
 await page.reload();await page.evaluate(()=>window.fixture.select('qwen21'));assert.equal(await aspect.inputValue(),'16:9');
 await page.evaluate(()=>window.fixture.select('qwen21-turbo'));assert.equal(await aspect.inputValue(),'9:16');
 await page.evaluate(()=>window.fixture.preferences('qwen21-turbo'));await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 await mkdir('work/image-formats-2026-10-20',{recursive:true});
 await page.screenshot({path:'work/image-formats-2026-10-20/qwen-mobile.png'});
 assert.deepEqual(errors,[]);
 console.log('PASS: visible top format for Qwen, Qwen Turbo, Anima, Krea and MOSS; per-model persistence, saved preferences outside Advanced, payload and mobile. No inference.');
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
