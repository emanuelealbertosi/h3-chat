import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {readFile,mkdir} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright'),JSZip=require('jszip');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostic='';child.stderr.on('data',x=>diagnostic+=x);
const lines=createInterface({input:child.stdout}),timer=setTimeout(()=>child.kill(),30000),first=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostic);})]);clearTimeout(timer);const fixture=JSON.parse(first[0]);lines.close();
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1640,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>{
  window.contrastPaints=new WeakMap();const fill=CanvasRenderingContext2D.prototype.fillText,clear=CanvasRenderingContext2D.prototype.clearRect;
  CanvasRenderingContext2D.prototype.clearRect=function(...args){window.contrastPaints.set(this.canvas,[]);return clear.apply(this,args);};
  CanvasRenderingContext2D.prototype.fillText=function(text,...args){if(this.canvas.closest('.h3-slide-page')){const list=window.contrastPaints.get(this.canvas)||[];list.push({text,color:this.fillStyle,alpha:this.globalAlpha});window.contrastPaints.set(this.canvas,list);}return fill.call(this,text,...args);};
});
// Independent measurement of direct text, including translucent surfaces and
// opacity; the test does not import the app's contrast correction functions.
async function inspect(){return page.locator('.h3-slide-page').evaluateAll(frames=>{
  const rgb=s=>{if(s.startsWith('#'))return [1,3,5].map(i=>parseInt(s.slice(i,i+2),16)).concat(1);const a=s.match(/[\d.]+/g)?.map(Number)||[0,0,0,0];return [...a.slice(0,3),a[3]??1];};
  const blend=(a,b,opacity=1)=>a.slice(0,3).map((v,i)=>v*a[3]*opacity+b[i]*(1-a[3]*opacity)).concat(1);
  const lum=a=>a.slice(0,3).map(v=>{const c=v/255;return c<=.04045?c/12.92:((c+.055)/1.055)**2.4;}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
  const failures=[],chartColors=[];let checked=0;
  for(const frame of frames){const walker=document.createTreeWalker(frame,NodeFilter.SHOW_TEXT);let node;while(node=walker.nextNode()){
    const el=node.parentElement;if(!node.data.trim()||el.closest('.no-export,svg,math,.katex-mathml')||!el.getBoundingClientRect().width)continue;
    const layers=[];let opacity=1;for(let p=el;p;p=p.parentElement){const s=getComputedStyle(p);layers.push(rgb(s.backgroundColor));opacity*=Number(s.opacity);if(p===frame)break;}
    const bg=layers.reverse().reduce((b,a)=>blend(a,b),[255,255,255,1]),fg=blend(rgb(getComputedStyle(el).color),bg,opacity),a=lum(bg),b=lum(fg),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);checked++;
    if(ratio<4.5-1e-6)failures.push({text:node.data.slice(0,60),ratio,fg:getComputedStyle(el).color,bg});
  }
    for(const canvas of frame.querySelectorAll('canvas')){
      const layers=[];for(let p=canvas;p;p=p.parentElement){layers.push(rgb(getComputedStyle(p).backgroundColor));if(p===frame)break;}
      const bg=layers.reverse().reduce((b,a)=>blend(a,b),[255,255,255,1]),paints=window.contrastPaints.get(canvas)||[];
      const hex=a=>a.slice(0,3).map(x=>Math.round(x).toString(16).padStart(2,'0')).join('').toUpperCase();chartColors.push({background:hex(bg),foreground:paints.length?hex(rgb(paints[0].color)):''});
      for(const paint of paints){const a=lum(bg),b=lum(blend(rgb(paint.color),bg,paint.alpha)),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);checked++;if(ratio<4.5-1e-6)failures.push({...paint,ratio});}
      if(!paints.length)failures.push({text:'Chart labels not painted'});
    }
    for(const text of frame.querySelectorAll('.diagram svg text')){
      const layers=[];for(let p=text;p;p=p.parentElement){layers.push(rgb(getComputedStyle(p).backgroundColor));if(p===frame)break;}
      let bg=layers.reverse().reduce((b,a)=>blend(a,b),[255,255,255,1]);const shape=text.closest('g.node,g.cluster,g.edgeLabel')?.querySelector('rect,polygon,circle,ellipse');if(shape)bg=blend(rgb(getComputedStyle(shape).fill),bg);
      const a=lum(bg),b=lum(blend(rgb(getComputedStyle(text).fill),bg)),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);checked++;if(ratio<4.5-1e-6)failures.push({text:text.textContent,ratio});
    }
  }return {checked,failures,chartColors};});}
try{
  await mkdir('work/slide-contrast-qa',{recursive:true});await page.goto(fixture.url);await page.click(`[data-chat="${fixture.chat}"]`);await page.click('#canvas-toggle');
  for(const theme of ['lagoon','indigo','sunset'])for(const design of ['professional','playful','comic']){
    await page.evaluate(async ({theme,design})=>{const {token}=await(await fetch('/api/state')).json();const response=await fetch('/fixture/slides/contrast',{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':token},body:JSON.stringify({theme,design})});if(!response.ok)throw Error(await response.text());},{theme,design});
    await page.waitForSelector('.slide-theme-'+theme+'.slide-design-'+design);
    for(let i=0;i<3;i++){
      await page.selectOption('.slides-navigation select',String(i));await page.waitForFunction(i=>{const frame=document.querySelector('.h3-slide-page');return frame?.dataset.page===String(i+1)&&frame.dataset.contrastChecked==='true';},i);await page.waitForTimeout(100);
      const measured=await inspect();assert.ok(measured.checked>2);assert.deepEqual(measured.failures,[],theme+'/'+design+'/'+i+' '+JSON.stringify(measured.failures));
    }
  }
  const expectedChart=(await inspect()).chartColors[0];assert.ok(expectedChart);
  await page.selectOption('.slides-navigation select','1');await page.click('#slide-edit');await page.click('[data-node-id="text-plain"]');assert.notEqual(await page.inputValue('#slide-color'),'#ffffff');
  await page.locator('.h3-slide-page').first().screenshot({path:'work/slide-contrast-qa/surfaces.png'});await page.click('#slide-edit');
  let download=page.waitForEvent('download',{timeout:120000});await page.click('[data-export="pptx"]');await(await download).saveAs('work/slide-contrast-qa/contrast.pptx');
  const zip=await JSZip.loadAsync(await readFile('work/slide-contrast-qa/contrast.pptx')),charts=Object.keys(zip.files).filter(n=>/^ppt\/charts\/chart\d+\.xml$/.test(n));assert.equal(charts.length,1);const xml=await zip.file(charts[0]).async('string');assert.ok(xml.includes(expectedChart.background));assert.ok(xml.includes(expectedChart.foreground));assert.ok(!xml.includes('53636A'));
  download=page.waitForEvent('download',{timeout:120000});await page.click('[data-export="pdf"]');await(await download).saveAs('work/slide-contrast-qa/contrast.pdf');
  assert.deepEqual(errors,[]);console.log('Contrast: all three themes and styles, cover tables/math, nested light/dark panels, code tokens, transparent surfaces, overrides, editor and PDF/PPTX passed.');
}catch(e){await page.screenshot({path:'work/slide-contrast-qa/error.png',fullPage:true});throw e;}
finally{await browser.close();child.kill();}
