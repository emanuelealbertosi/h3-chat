import {createRequire} from 'node:module';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']}),page=await browser.newPage({viewport:{width:1280,height:720}});
const code=await readFile('static/infographic-motion.js','utf8');
try{
 for(const [layout,count,marker] of [['columns3',3,''],['grid3x2',6,'data-overlay="global"'],['columns3',3,'data-overlay="global" data-overlay-background="opaque"']]){
  const html='<style>html,body{margin:0;width:1280px;height:720px;background:black}.stage{position:relative;width:100%;height:100%;overflow:hidden}.final{width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:radial-gradient(#111,#000);color:white;font:900 100px Arial}</style><div class="stage">'+Array.from({length:count},(_,i)=>`<section data-panel="${i+1}" style="background:#246"><span data-motion="fade" data-start="0" data-out="15">TITLE ${i+1}</span></section>`).join('')+`<div class="final" ${marker} data-motion="zoom" data-start="15" data-duration="2"><b data-motion="zoom" data-start="15" data-duration="2">POWER</b></div></div>`;
  await page.setContent(html);await page.evaluate(code);await page.evaluate(layout=>H3Motion.screen(document,{layout,panel_appearance:'sequence',panel_order:'auto',panel_interval:1},20),layout);
  const state=t=>page.evaluate(t=>{H3Motion.apply(document,t,20);const e=document.querySelector('.final'),r=e.getBoundingClientRect(),child=e.querySelector('b');return {parent:e.parentElement.tagName,display:getComputedStyle(e).display,opacity:Number(getComputedStyle(e).opacity),childOpacity:Number(getComputedStyle(child).opacity),background:getComputedStyle(e).backgroundColor,backgroundImage:getComputedStyle(e).backgroundImage,rect:[r.x,r.y,r.width,r.height],top:document.elementFromPoint(640,360)?.closest('.final')===e,starts:[e.dataset.start,child.dataset.start],titles:[...document.querySelectorAll('section span')].map(e=>Number(getComputedStyle(e).opacity))};},t);
  const before=await state(14.9);assert.equal(before.opacity,0);assert.equal(before.parent,'BODY');assert.notEqual(before.display,'none');assert.deepEqual(before.starts,['15','15']);
  const after=await state(18);assert.equal(after.opacity,1);assert.equal(after.childOpacity,1);assert.deepEqual(after.rect,[0,0,1280,720]);assert.equal(after.top,true);assert.ok(after.titles.every(v=>v===0));if(marker.includes('opaque'))assert.match(after.backgroundImage,/radial-gradient/);else{assert.equal(after.background,'rgba(0, 0, 0, 0)');assert.equal(after.backgroundImage,'none');}
  await page.evaluate(layout=>H3Motion.screen(document,{layout,panel_appearance:'sequence',panel_order:'auto',panel_interval:1},20),layout);assert.equal((await state(18)).top,true);
 }
 console.log('PASS: legacy and explicit global overlays span three/six panels, retain their 15-second entrance, use transparent backgrounds unless an opaque card is explicit, fade earlier labels and survive repeated preparation.');
}finally{await browser.close();}
