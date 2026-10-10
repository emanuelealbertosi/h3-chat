import {createRequire} from 'node:module';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']}),page=await browser.newPage({viewport:{width:960,height:720}});
const motion=await readFile('static/infographic-motion.js','utf8');
const html='<style>body{background:#152033;color:white}h1{font:48px/1.2 Arial;width:560px;margin:0}p{color:#91c7bb}img{width:10px;height:10px}</style><h1 data-motion="fade" data-start="1" data-duration="2">Novità <strong>è 👨‍👩‍👧!</strong><br>Una seconda riga.</h1><p data-motion="slide" data-start="1">Corpo del testo.</p><img data-motion="zoom" data-start="1" alt="Immagine">';
try{
 for(const effect of ['typewriter','drop','wave','bump','flip','slide']){
  await page.setContent(html);await page.evaluate(motion);
  const before=await page.locator('h1').evaluate(e=>({text:e.textContent,height:e.offsetHeight}));
  const opt={text_motion:effect,text_scope:'headings',text_speed:'normal',text_direction:'left',text_look:'neon',text_color:'custom',text_primary:'#ffffff',text_accent:'#00e5ff'};
  const state=async t=>page.evaluate(({t,opt})=>{H3Motion.apply(document,t,8,opt);const e=document.querySelector('h1');return {text:e.textContent,height:e.offsetHeight,opacity:Number(e.style.opacity),transform:e.style.transform,color:getComputedStyle(e).color,shadow:getComputedStyle(e).textShadow,chars:[...e.querySelectorAll('[data-h3-letter]')].map(c=>({text:c.textContent,opacity:Number(c.style.opacity),transform:c.style.transform})),imageMotion:document.querySelector('img').dataset.motion,bodyShadow:getComputedStyle(document.querySelector('p')).textShadow,strong:!!e.querySelector('strong'),breaks:e.querySelectorAll('br').length};},{t,opt});
  const hidden=await state(.9);assert.equal(hidden.opacity,0);
  const middle=await state(2);const end=await state(4);
  assert.equal(end.text,before.text);assert.equal(end.height,before.height);assert.equal(end.opacity,1);assert.equal(end.strong,true);assert.equal(end.breaks,1);assert.equal(end.imageMotion,'zoom');assert.equal(end.bodyShadow,'none');assert.equal(end.color,'rgb(255, 255, 255)');assert.notEqual(end.shadow,'none');
  if(['typewriter','drop','wave'].includes(effect)){
   assert.ok(middle.chars.some(c=>c.opacity<1));assert.ok(middle.chars.some(c=>c.opacity>0));assert.ok(end.chars.every(c=>c.opacity===1&&c.transform==='none'));
   assert.equal(end.chars.filter(c=>c.text==='👨‍👩‍👧').length,1);
   const rewind=await state(.9);assert.ok(rewind.chars.every(c=>c.opacity===0));assert.deepEqual(await state(4),end);
   // Repeated preparation must reuse existing letters, never wrap them again.
   await page.evaluate(()=>H3Motion.screen(document,{layout:'full'},8));assert.equal((await state(4)).chars.length,end.chars.length);
  }
  if(effect==='slide')assert.match(middle.transform,/translate\(-35px,\s*0px\)/);
 }
 for(const [direction,x,y] of [['left',-35,0],['right',35,0],['up',0,-35],['down',0,35]]){
  await page.setContent(html);await page.evaluate(motion);await page.evaluate(direction=>H3Motion.apply(document,2,8,{text_motion:'slide',text_direction:direction}),direction);
  assert.equal(await page.locator('h1').evaluate(e=>e.style.transform),`translate(${x}px, ${y}px)`);
 }
 await page.setContent(html);await page.evaluate(motion);
 await page.evaluate(()=>H3Motion.apply(document,4,8,{text_motion:'auto',text_look:'auto',text_color:'auto'}));
 assert.equal(await page.locator('[data-h3-letter]').count(),0);assert.equal(await page.locator('h1').evaluate(e=>e.style.textShadow),'');
 await page.evaluate(()=>H3Motion.apply(document,4.5,8,{text_motion:'auto',text_color:'cycle',text_primary:'#ffffff',text_accent:'#00e5ff'}));
 assert.equal(await page.locator('h1').evaluate(e=>getComputedStyle(e).color),'rgb(0, 229, 255)');
 await page.setContent(html.replace('data-motion="fade" data-start="1" data-duration="2"',''));await page.evaluate(motion);
 await page.evaluate(()=>H3Motion.apply(document,4,8,{text_color:'cycle',text_primary:'#ffffff',text_accent:'#00e5ff'}));
 assert.equal(await page.locator('h1').evaluate(e=>getComputedStyle(e).color),'rgb(0, 229, 255)');
 // Preview and export use exactly the same options and clock.
 const options={text_motion:'drop',text_scope:'headings',text_speed:'slow'};
 await page.setContent('<iframe data-h3-scene="0"></iframe>');await page.evaluate(motion);
 await page.locator('iframe').evaluate((f,html)=>{f.contentDocument.open();f.contentDocument.write(html);f.contentDocument.close();},html);
 const result=await page.evaluate(options=>{const doc=document.querySelector('iframe').contentDocument;H3Motion.apply(doc,1.7,8,options);const sample=()=>[...doc.querySelectorAll('[data-h3-letter]')].map(e=>e.style.cssText);const preview=sample();H3Motion.render(document,{durations:[8],transition:'cut',options},1.7);return [preview,sample()];},options);
 assert.deepEqual(result[0],result[1]);
 // Explicit per-element effects win over the global preset; images stay unchanged.
 await page.setContent(html.replace('data-motion="fade"','data-motion="flip" data-text-override="true"'));await page.evaluate(motion);await page.evaluate(()=>H3Motion.apply(document,2,8,{text_motion:'drop'}));
 assert.match(await page.locator('h1').evaluate(e=>e.style.transform),/rotateX/);assert.equal(await page.locator('[data-h3-letter]').count(),0);
 // Real prompt and canvas controls save compatible options through their modals.
 const bundle=await build({entryPoints:['ui/infographics.js'],bundle:true,write:false,format:'iife',globalName:'InfographicUI'});
 await page.setContent('<select id="lab-tool"><option value="infographic">Infografica</option></select><div id="prompt-context"></div><div id="canvas"></div><div id="frame"><iframe></iframe></div>');
 await page.evaluate(bundle.outputFiles[0].text);
 await page.evaluate(()=>{globalThis.controls=InfographicUI.initInfographics({getState:()=>({models:[]}),getAttachments:()=>[]});controls.render();});
 await page.locator('[data-infographic-field="text_motion"] [data-value="drop"]').click();
 assert.equal((await page.evaluate(()=>controls.read())).text_motion,'drop');
 const deck={pages:[{html}],infographic:{durations:[8],transition:'cut',options:{text_motion:'auto'}}};
 await page.locator('iframe').evaluate((f,html)=>{f.contentDocument.open();f.contentDocument.write(html);f.contentDocument.close();},html);
 await page.evaluate(deck=>InfographicUI.mountInfographic(document.querySelector('#canvas'),deck,0,document.querySelector('#frame'),{editable:true,onChange:async content=>{globalThis.saved=JSON.parse(content.slice(13,-4));},api:async()=>{}},{id:'test',media:[]}),deck);
 await page.locator('[data-text-settings]').click();assert.ok(await page.locator('dialog[open]').count());
 await page.locator('dialog[open] [data-infographic-field="text_motion"] [data-value="bump"]').click();await page.locator('[data-save-text]').click();
 assert.equal(await page.evaluate(()=>saved.infographic.options.text_motion),'bump');
 console.log('PASS: real graphemes, falling/typed/wave letters, reverse seeking, four-direction motion, color, neon, unchanged layout/assets, export parity and saved prompt/canvas modals.');
}finally{await browser.close();}
