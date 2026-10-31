import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const folder=process.env.H3_MOTION_PROOF||'work/motion-graphics-p0';
const deck=JSON.parse(await readFile(folder+'/deck.json','utf8')),bundle=await readFile('static/vendor/infographic-renderer.js','utf8');
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
try{
 const context=await browser.newContext({viewport:{width:1280,height:720},deviceScaleFactor:1.5,offline:true});
 const page=await context.newPage();await page.goto(pathToFileURL(folder+'/infographic-render.html').href);await page.evaluate(bundle);
 await page.evaluate(async motion=>{for(const [i,frame] of [...document.querySelectorAll('iframe')].entries())await H3Infographic.prepare(frame.contentDocument,720,motion.options,motion.durations[i]);},deck.infographic);
 const result=await page.evaluate(motion=>{
  const doc=document.querySelector('iframe').contentDocument,svg=doc.querySelector('svg'),snapshot=()=>[...doc.querySelectorAll('[data-h3-motion-object]')].map(n=>[n.dataset.h3MotionObject,n.getAttribute('transform'),n.getAttribute('opacity')]);
  H3Motion.render(document,motion,4.5);const expected=snapshot();H3Motion.render(document,motion,0);H3Motion.render(document,motion,4.5);const afterForward=snapshot();H3Motion.render(document,motion,9);H3Motion.render(document,motion,4.5);
  return {expected,afterForward,afterBackward:snapshot(),sameDom:svg===doc.querySelector('svg'),objects:doc.querySelectorAll('[data-h3-motion-object]').length};
 },deck.infographic);
 assert.deepEqual(result.afterForward,result.expected);assert.deepEqual(result.afterBackward,result.expected);assert.equal(result.sameDom,true);assert.equal(result.objects,3);
 await page.screenshot({path:folder+'/preview-4.5.png'});
 await writeFile(folder+'/browser-proof.json',JSON.stringify({passed:true,seekInvariant:true,cachedDom:true,objects:3,preview:'preview-4.5.png'},null,2));
 console.log('PASS: shared trusted renderer, three objects, forward/backward seeks, cached DOM, screenshot at4.5s.');
}finally{await browser.close();}
