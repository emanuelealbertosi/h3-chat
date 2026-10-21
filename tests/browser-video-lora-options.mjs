import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const bundle=await build({stdin:{contents:"import {videoModalOptions} from './ui/video-modal-options.js'; window.videoModalOptions=videoModalOptions;",resolveDir:process.cwd()},bundle:true,write:false,format:'iife',platform:'browser',target:'es2022'});
const server=createServer((req,res)=>{res.setHeader('Content-Type',req.url==='/fixture.js'?'application/javascript':'text/html');res.end(req.url==='/fixture.js'?bundle.outputFiles[0].text:'<!doctype html><meta charset="utf-8"><form id="options"><input name="steps" value="12"><input name="cfg" value="1"><input name="sampler" value="res_multistep"><input name="megapixels" value="0.5"></form><script src="/fixture.js"></script>');});
server.listen(0,'127.0.0.1');await once(server,'listening');
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']});
const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:'+server.address().port);
 await page.evaluate(()=>{
  const cass={path:'F:/models/Aunt Cass BH6.safetensors',name:'Aunt Cass BH6',profile:'custom'},swap={path:'D:/models/character_swap.safetensors',name:'Character Swap',profile:'character_swap'};
  window.options=window.videoModalOptions(document.querySelector('form'),{model_id:'h3',models:[{id:'h3',name:'Ref2VA',parameters:{seed:1,pdd_lora:'D:/models/PDD.safetensors'}}],loras:[cass,swap]},
   {parameters:{attention:'veda',pdd_enabled:false,source_conditioning:'aligned',seed:1215790999,loras:[{path:cass.path,weight:1}]}});
 });
 const recipe=()=>page.evaluate(()=>window.options.read());
 assert.equal((await recipe()).parameters.loras.length,1);
 const tryPdd=()=>page.locator('[name="pdd_enabled"]').evaluate(el=>{el.checked=true;el.dispatchEvent(new Event('change',{bubbles:true}));});
 await tryPdd();
 let value=await recipe();
 assert.equal(value.parameters.pdd_enabled,false);
 assert.deepEqual(value.parameters.loras,[{path:'F:/models/Aunt Cass BH6.safetensors',weight:1}]);
 assert.equal(value.parameters.source_conditioning,'aligned');
 assert.equal(await page.locator('[name="steps"]').inputValue(),'12');
 assert.equal(await page.locator('[name="sampler"]').inputValue(),'res_multistep');
 assert.match(await page.locator('[role="status"]').textContent(),/Aunt Cass BH6.*restano selezionati/);
 // The supported editing combination must still enable PDD and its own steps.
 await page.locator('[data-video-lora="0"]').uncheck();
 await page.locator('[data-video-lora="1"]').check();
 await tryPdd();value=await recipe();
 assert.equal(value.parameters.pdd_enabled,true);
 assert.equal(value.parameters.loras.length,1);assert.match(value.parameters.loras[0].path,/character_swap/);
 assert.equal(value.parameters.steps,8);assert.equal(await page.locator('[name="steps"]').inputValue(),'8');
 assert.equal(await page.locator('[name="sampler"]').inputValue(),'euler');
 assert.deepEqual(errors,[]);
 console.log('PASS: enabling PDD preserves Aunt Cass and standard steps; supported Character Swap/PDD remains available.');
}finally{await browser.close();server.close();}
