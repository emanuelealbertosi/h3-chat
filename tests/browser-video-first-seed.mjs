import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const bundle=await build({stdin:{contents:"import {videoModalOptions} from './ui/video-modal-options.js';window.videoModalOptions=videoModalOptions;",resolveDir:process.cwd()},bundle:true,write:false,format:'iife',platform:'browser',target:'es2022'});
const server=createServer((req,res)=>{res.setHeader('Content-Type',req.url==='/fixture.js'?'application/javascript':'text/html');res.end(req.url==='/fixture.js'?bundle.outputFiles[0].text:'<!doctype html><meta charset="utf-8"><form></form><script src="/fixture.js"></script>');});
server.listen(0,'127.0.0.1');await once(server,'listening');
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']}),page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:'+server.address().port);
 await page.evaluate(()=>{
  window.data={model_id:'h3',models:[{id:'h3',name:'H3',parameters:{seed:-1}}],clips:[{clip:1,selected_version:'original',versions:[{id:'original',seed:-1},{id:'first',seed:517890679},{id:'second',seed:0}]}]};
  window.options=window.videoModalOptions(document.querySelector('form'),window.data,{parameters:{seed:-1}});
 });
 const seed=()=>page.evaluate(()=>window.options.read().parameters.seed);
 assert.equal(await seed(),-1);
 await page.getByRole('button',{name:'Usa seed della prima clip',exact:true}).click();assert.equal(await seed(),517890679);
 assert.equal(await page.locator('input[name=seed]').inputValue(),'517890679');
 await page.evaluate(()=>window.data.clips[0].selected_version='second');
 await page.getByRole('button',{name:'Usa seed della prima clip',exact:true}).click();assert.equal(await seed(),0);
 await page.locator('[data-seed-mode=random]').click();assert.equal(await seed(),-1);
 await page.evaluate(()=>{window.data.clips[0].versions=[{id:'original',seed:-1}];window.options.set({model:'h3',parameters:{seed:-1}});});
 assert(await page.getByRole('button',{name:'Usa seed della prima clip',exact:true}).isHidden());
 assert.deepEqual(errors,[]);console.log('PASS: first generated seed, selected version seed, zero, random policy and absent seed; no generation submitted.');
}finally{await browser.close();server.close();}
