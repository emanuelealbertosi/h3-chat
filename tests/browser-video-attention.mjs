import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const bundle=await build({stdin:{contents:"import {initVideoRequest} from './ui/video-request.js';import {videoModalOptions} from './ui/video-modal-options.js';import {renderVideoSettings} from './ui/video-settings.js';window.initVideoRequest=initVideoRequest;window.videoModalOptions=videoModalOptions;window.renderVideoSettings=renderVideoSettings;",resolveDir:process.cwd()},bundle:true,write:false,format:'iife',platform:'browser',target:'es2022'});
const server=createServer((req,res)=>{res.setHeader('Content-Type',req.url==='/fixture.js'?'application/javascript':'text/html');res.end(req.url==='/fixture.js'?bundle.outputFiles[0].text:'<!doctype html><meta charset="utf-8"><div id="composer"></div><form><select name="attention"><option value="veda">VEDA</option></select></form><script src="/fixture.js"></script>');});
server.listen(0,'127.0.0.1');await once(server,'listening');
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
try{
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:'+server.address().port);
 await page.evaluate(()=>{
  window.state={models:[{id:'h3',name:'H3',ready:true,capabilities:['video']}],settings:{video_model:'h3',video_overrides:{h3:{attention:'veda',attention_chunks:8}}},video_options:{request_controls:true,attention_choices:true,defaults:{megapixels:.7}}};
  window.value={video_model:'',video_parameters:{},video_request_advanced:true};
  window.before=JSON.stringify(state.settings);
  window.controls=initVideoRequest({holder:document.querySelector('#composer'),read:()=>value,save:x=>{value=x;controls.render();},getState:()=>state});controls.render();
 });
 const select=page.locator('#video-request-attention');
 for(const [id,n] of [['veda8',8],['veda56',56]]){
  await select.selectOption(id);const p=await page.evaluate(()=>value.video_parameters);
  assert.deepEqual(p,{attention:'veda',attention_chunks:n,attention_chunks_mode:'manual'});
  assert.match(await page.locator('[data-video-request-ready]').textContent(),new RegExp('VEDA '+n));
 }
 await select.selectOption('pytorch');assert.equal((await page.evaluate(()=>value.video_parameters)).attention,'pytorch');
 await select.selectOption('comfy_kitchen');assert.deepEqual(await page.evaluate(()=>value.video_parameters),{attention:'comfy_kitchen',attention_chunks:0,attention_chunks_mode:'auto'});
 assert.match(await page.locator('[data-video-request-ready]').textContent(),/ComfyKitchen INT8/);
 await select.selectOption('veda');assert.equal((await page.evaluate(()=>value.video_parameters)).attention_chunks_mode,'auto');
 await select.selectOption('');assert.deepEqual(await page.evaluate(()=>value.video_parameters),{});
 assert.equal(await page.evaluate(()=>JSON.stringify(state.settings)===before),true);
 await page.evaluate(()=>{window.modal=videoModalOptions(document.querySelector('form'),{model_id:'h3',models:[{id:'h3',name:'H3',parameters:{}}],attention_choices:true},{parameters:{attention:'veda',attention_chunks:56,attention_chunks_mode:'manual'}});});
 assert.equal(await page.locator('form [name="attention"]').inputValue(),'veda56');
 assert.equal((await page.evaluate(()=>modal.read())).parameters.attention_chunks,56);
 await page.locator('form [name="attention"]').selectOption('veda8');
 assert.equal((await page.evaluate(()=>modal.read())).parameters.attention_chunks,8);
 await page.locator('form [name="attention"]').selectOption('comfy_kitchen');
 assert.equal((await page.evaluate(()=>modal.read())).parameters.attention,'comfy_kitchen');
 await page.evaluate(()=>{state.video_options.attention_choices=false;value.video_parameters={};controls.render();});
 assert.equal(await select.locator('[value="veda8"]').evaluate(el=>el.disabled),true);
 assert.equal(await select.locator('[value="comfy_kitchen"]').evaluate(el=>el.disabled),true);
 await select.selectOption('pytorch');assert.deepEqual(await page.evaluate(()=>value.video_parameters),{attention:'pytorch'});
 await page.evaluate(()=>{
  const holder=document.createElement('section');holder.id='preferences';document.body.append(holder);
  const preferenceState={...state,video_options:{...state.video_options,attention_choices:true,defaults:{steps:12,attention:'veda',attention_chunks:0},aspects:['16:9']},vision_runtime:{},downloads:[],access:{}};
  window.preferenceDraft={video_model:'h3',video_advanced:true,video_overrides:{}};
  renderVideoSettings(holder,{state:preferenceState,draft:preferenceDraft,changed(){}});
 });
 await page.locator('#preferences [data-video-setting="attention"]').selectOption('veda56');
 assert.equal((await page.evaluate(()=>preferenceDraft.video_overrides.h3)).attention_chunks_mode,'manual');
 assert.equal((await page.evaluate(()=>preferenceDraft.video_overrides.h3)).attention_chunks,56);
 await page.locator('#preferences [data-video-setting="attention"]').selectOption('comfy_kitchen');
 assert.equal((await page.evaluate(()=>preferenceDraft.video_overrides.h3)).attention,'comfy_kitchen');
 assert.equal((await page.evaluate(()=>preferenceDraft.video_overrides.h3)).attention_chunks_mode,'auto');
 assert.deepEqual(errors,[]);console.log('PASS explicit VEDA 8/56, automatic reset, PyTorch, unchanged presets, editor/recreate shared control, old-server compatibility.');
}finally{await browser.close();server.close();}
