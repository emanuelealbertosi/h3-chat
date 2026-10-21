import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const bundle=await build({stdin:{contents:"import {videoModalOptions} from './ui/video-modal-options.js';window.options=videoModalOptions;",resolveDir:process.cwd()},bundle:true,write:false,format:'iife',platform:'browser',target:'es2022'});
const server=createServer((req,res)=>{res.setHeader('Content-Type',req.url==='/fixture.js'?'application/javascript':'text/html');res.end(req.url==='/fixture.js'?bundle.outputFiles[0].text:'<!doctype html><meta charset="utf-8"><form><input name="steps" value="12"></form><script src="/fixture.js"></script>');});
server.listen(0,'127.0.0.1');await once(server,'listening');
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
try{
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const open=async ready=>{await page.goto('http://127.0.0.1:'+server.address().port);await page.evaluate(ready=>{window.recipe=window.options(document.querySelector('form'),{longtake_experimental:ready,model_id:'h3',models:[{id:'h3',name:'H3',parameters:{}}],loras:[]});},ready);};
 await open(false);assert.equal(await page.locator('[name="longtake_enabled"]').isDisabled(),true);
 assert.equal('longtake_enabled' in (await page.evaluate(()=>recipe.read())).parameters,false);
 await open(true);const field=page.locator('[name="longtake_enabled"]');await field.locator('xpath=ancestor::details').evaluate(el=>el.open=true);
 assert.equal(await field.isChecked(),false);await field.check();
 assert.equal((await page.evaluate(()=>recipe.read())).parameters.longtake_enabled,true);
 await page.locator('[name="pdd_enabled"]').locator('xpath=ancestor::details').evaluate(el=>el.open=true);
 await page.locator('[name="pdd_enabled"]').check();assert.equal(await field.isChecked(),false);
 await field.check();assert.equal(await page.locator('[name="pdd_enabled"]').isChecked(),false);
 assert.deepEqual(errors,[]);console.log('PASS LongTake experimental opt-in, request-local serialization, old-server gating, PDD exclusion.');
}finally{await browser.close();server.close();}
