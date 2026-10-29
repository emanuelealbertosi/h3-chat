import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const code=await build({stdin:{contents:"import {renderVideoSettings} from './ui/video-settings.js'; window.renderVideoSettings=renderVideoSettings;",resolveDir:process.cwd()},bundle:true,write:false,format:'iife'});
const server=createServer((req,res)=>{res.setHeader('Content-Type',req.url==='/app.js'?'application/javascript':'text/html');res.end(req.url==='/app.js'?code.outputFiles[0].text:'<!doctype html><div id="host"></div><script src="/app.js"></script>');});
server.listen(0,'127.0.0.1');await once(server,'listening');
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
try{
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:'+server.address().port);
 await page.evaluate(()=>{
  const recipe={duration:12,megapixels:.98,aspect:'16:9',steps:8,cfg:1,sampler:'er_sde',scheduler:'sgm_uniform',seed:-1,shift_video:12,shift_audio:3,offload:true,attention:'vsa',attention_chunks:0,attention_chunks_mode:'auto',veda_predictor:'',veda_sparsity:90,veda_reference_sparsity:90,pdd_enabled:false,pdd_lora:'',experimental_resolution:false,loras:[],source_conditioning:'reference',variants:1,variants_mode:'clip'};
  window.draft={video_model:'beta5',video_advanced:true,video_auto:true,video_overrides:{beta5:{...recipe},beta7:{...recipe}}};
  const state={models:['beta5','beta7'].map(id=>({id,name:id,capabilities:['video'],external_config:{profile:'minimax-h3'}})),video_options:{defaults:recipe,aspects:['16:9','9:16','1:1'],attention_choices:true,batch_controls:true},vision_runtime:{ready:true},downloads:[],jobs:[]};
  window.renderVideoSettings(document.querySelector('#host'),{state,draft:window.draft,link(){},edit(){},pickFile(){},install(){},changed(){}});
 });
 for(const model of ['beta5','beta7']){
  await page.locator('[data-video-model]').selectOption(model);
  assert.equal(await page.locator('[data-video-setting="sampler"]').inputValue(),'er_sde');
  assert.equal(await page.locator('[data-video-setting="scheduler"]').inputValue(),'sgm_uniform');
  assert.equal(await page.locator('[data-video-setting="attention"]').inputValue(),'vsa');
  assert.equal(await page.locator('[data-video-setting="steps"]').inputValue(),'8');
 }
 assert.deepEqual(errors,[]);console.log('Passed: both Eros recipes display and retain Er_sde/SGM uniform/VSA/8 steps.');
}finally{await browser.close();server.close();}
