import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);
const lines=createInterface({input:child.stdout});const first=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);const fixture=JSON.parse(first[0]);lines.close();
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1640,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
const iframe=()=>page.frameLocator('.h3-html-page iframe');
const fits=()=>iframe().locator('body').evaluate(body=>[...body.querySelectorAll('*')].filter(e=>!e.closest('style,[data-h3-editor]')&&(!e.closest('svg')||e.tagName.toLowerCase()==='svg')).every(e=>{const r=e.getBoundingClientRect();return r.left>=-2&&r.right<=1282&&r.top>=-2&&r.bottom<=722;}));
try{
 await mkdir('work/slide-bounds-qa',{recursive:true});await page.goto(fixture.url);await page.click(`[data-chat="${fixture.chat}"]`);
 await page.evaluate(async()=>{const {token}=await(await fetch('/api/state')).json();const r=await fetch('/fixture/slides/html-bounds',{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':token},body:'{}'});if(!r.ok)throw Error(await r.text());});
 await page.click('#canvas-toggle');await iframe().locator('svg').waitFor();assert.equal(await fits(),true);assert.equal(await page.locator('.slide-layout-warning').isVisible(),false);
 assert.equal(await iframe().locator('.main').evaluate(e=>getComputedStyle(e).display),'grid');assert.match(await iframe().locator('.main').evaluate(e=>getComputedStyle(e).gridTemplateColumns),/^340px /);
 assert.equal(await iframe().locator('svg').evaluate(svg=>{const b=svg.getBBox(),v=svg.viewBox.baseVal;return b.x>=v.x&&b.y>=v.y&&b.x+b.width<=v.x+v.width&&b.y+b.height<=v.y+v.height;}),true);
 await page.screenshot({path:'work/slide-bounds-qa/diagram.png',fullPage:true});
 await page.selectOption('.slides-navigation select','1');await iframe().locator('img').waitFor();assert.equal(await fits(),true);assert.equal(await iframe().locator('img').evaluate(e=>getComputedStyle(e).objectFit),'contain');
 await page.screenshot({path:'work/slide-bounds-qa/image.png',fullPage:true});
 await page.selectOption('.slides-navigation select','2');await iframe().locator('.ok').waitFor();assert.equal(await fits(),true);assert.equal(await page.locator('.h3-html-page').getAttribute('data-layout-adjusted'),null);
 assert.equal(await iframe().locator('.ok').getAttribute('style'),null);assert.equal(await iframe().locator('[data-h3-layout]').count(),0);
 const download=page.waitForEvent('download',{timeout:120000});await page.click('[data-export=html]');const file=await download;await file.saveAs('work/slide-bounds-qa/slides.html');const exported=await readFile('work/slide-bounds-qa/slides.html','utf8');assert.ok(/preserveAspectRatio="xMidYMid meet"/i.test(exported),"SVG fitting must survive export");assert.ok(exported.includes("object-fit: contain"),"Image proportions must survive export");
 await page.selectOption('.slides-navigation select','0');await iframe().locator('svg').waitFor();await page.click('#slide-edit');await page.click('#slide-html-save');await page.waitForFunction(()=>document.querySelector('#canvas-save-status')?.textContent.includes('Salvato'));await page.reload();await page.click(`[data-chat="${fixture.chat}"]`);await page.click('#canvas-toggle');await iframe().locator('svg').waitFor();assert.equal(await fits(),true);
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(150);assert.equal(await fits(),true);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);assert.deepEqual(errors,[]);
 console.log('Intrinsic SVG/grid overflow, SVG labels, oversized image proportions, free layout preservation, HTML export, graphical save/reload and mobile passed.');
}catch(e){await page.screenshot({path:'work/slide-bounds-qa/error.png',fullPage:true});console.error(diagnostics);throw e;}finally{await browser.close();child.kill();}
