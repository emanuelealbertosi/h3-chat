import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{build}=require('esbuild');
const {chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const compiled=await build({stdin:{contents:`import {initPosters} from './ui/posters.js';let attachments=[];const state={models:[],settings:{},execution:{mode:'gpu'}};window.ui=initPosters({getState:()=>state,getAttachments:()=>attachments});window.attach=items=>{attachments=items;ui.render();};`,resolveDir:process.cwd()},write:false,bundle:true,format:'iife',platform:'browser'});
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
try{
 const page=await browser.newPage();await page.setContent('<select id="lab-tool"><option value="poster" selected>Poster</option></select><div id="slides-options"></div>');await page.addScriptTag({content:compiled.outputFiles[0].text});
 const a={id:'a'.repeat(32),name:'Old.png',mime:'image/png'},b={id:'b'.repeat(32),name:'New.jpg',mime:'image/jpeg'},c={id:'c'.repeat(32),name:'Other.pdf',mime:'application/pdf'};
 await page.evaluate(a=>{attach([a]);ui.set({reference_mode:'improve',reference_asset_id:a.id,reference_page:8,format:'A4'});},a);
 assert.equal((await page.evaluate(()=>ui.read())).reference_asset_id,a.id);
 await page.evaluate(b=>attach([b]),b);
 let current=await page.evaluate(()=>ui.read());assert.equal(current.reference_asset_id,b.id);assert.equal(current.reference_page,1);assert.equal(current.reference_mode,'improve');assert.equal(current.format,'A4');
 await page.evaluate(items=>attach(items),[b,c]);const select=page.locator('[data-poster="reference_asset_id"]');
 await select.selectOption('');assert.equal((await page.evaluate(()=>ui.read())).reference_asset_id,'');
 await select.selectOption(c.id);assert.equal((await page.evaluate(()=>ui.read())).reference_asset_id,c.id);
 await page.evaluate(()=>attach([]));assert.equal((await page.evaluate(()=>ui.read())).reference_asset_id,'');
 await page.evaluate(items=>attach(items),[a,b]);assert.equal((await page.evaluate(()=>ui.read())).reference_asset_id,'');
 assert.equal(await select.locator('option').count(),3);
 console.log('PASS: replacing source rebinds it, resets stale page, preserves style; ambiguous or removed sources stay unselected.');
}finally{await browser.close();}
