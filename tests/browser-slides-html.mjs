import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright'),JSZip=require('jszip');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);
const lines=createInterface({input:child.stdout}),timer=setTimeout(()=>child.kill(),30000);const first=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);clearTimeout(timer);const fixture=JSON.parse(first[0]);lines.close();
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1640,height:1100}}),errors=[],remote=[];
page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith(fixture.url)&&!r.url().startsWith('data:'))remote.push(r.url());});
page.on('console',m=>{if(m.type()==='error')console.error(m.text());});
const post=path=>page.evaluate(async path=>{const {token}=await(await fetch('/api/state')).json();const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':token},body:'{}'});if(!r.ok)throw Error(await r.text());},path);
const saved=()=>page.evaluate(async chat=>await(await fetch('/api/canvas/'+chat)).json(),fixture.chat);
const iframe=()=>page.frameLocator('.h3-html-page iframe');
try{
  await mkdir('work/slides-html-qa',{recursive:true});await page.goto(fixture.url);await page.click(`[data-chat="${fixture.chat}"]`);await page.selectOption('#lab-tool','slides');assert.equal(await page.inputValue('#slides-engine'),'llm');
  await post('/fixture/slides/html-stream');await page.click('#canvas-toggle');await iframe().locator('h1').waitFor();assert.match(await iframe().locator('h1').textContent(),/modello/);assert.equal(await page.locator('#slide-edit').isDisabled(),true);
  await post('/fixture/slides/html');await page.waitForFunction(()=>!document.querySelector('#slide-edit')?.disabled);await iframe().locator('svg').waitFor();
  await iframe().locator('.katex').waitFor();
  assert.equal(await iframe().locator('h1').evaluate(e=>getComputedStyle(e).color),'rgb(255, 209, 102)');assert.equal(await iframe().locator('main').evaluate(e=>getComputedStyle(e).display),'grid');assert.equal(await page.evaluate(()=>window.__h3Injected),undefined);assert.equal(await iframe().locator('script').count(),0);
  assert.equal(await iframe().locator('img[data-asset-id]').evaluate(e=>e.naturalWidth>0),true);
  await page.click('#slide-edit');await iframe().locator('h1').click();await page.click('#slide-html-properties summary');await page.fill('#slide-html-text','Titolo modificato liberamente');await page.fill('#slide-html-size','64');await page.click('#slide-html-save');await page.waitForFunction(()=>document.querySelector('#canvas-save-status')?.textContent.includes('Salvato'));
  assert.match((await saved()).content,/Titolo modificato liberamente/);
  await iframe().locator('img[data-asset-id]').click();await page.click('#slide-html-images summary');await page.click('[data-rag]');await page.locator('[data-results] button').first().waitFor();await page.locator('[data-results] button').first().click();await page.waitForFunction(()=>document.querySelector('#slide-html-status')?.textContent.includes('inserita'));await page.click('#slide-html-save');await page.waitForTimeout(600);
  assert.ok((await saved()).media.some(m=>m.provenance?.kind==='rag'));
  const png=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=80;c.height=50;c.getContext('2d').fillRect(0,0,80,50);return c.toDataURL().split(',')[1];});
  await page.click('#slide-html-images summary');await page.locator('[data-file]').setInputFiles({name:'nuova.png',mimeType:'image/png',buffer:Buffer.from(png,'base64')});await page.waitForFunction(()=>document.querySelector('#slide-html-status')?.textContent.includes('inserita'));await page.click('#slide-html-save');await page.waitForTimeout(500);
  const before=await saved();assert.ok(before.media.some(m=>m.name==='nuova.png'));
  await page.screenshot({path:'work/slides-html-qa/canvas.png',fullPage:true});
  for(const kind of ['pdf','pptx','html']){
    console.log('Export',kind);
    const event=page.waitForEvent('download',{timeout:120000});await page.click(`[data-export="${kind}"]`);const file=await event;await file.saveAs('work/slides-html-qa/slides.'+kind);
  }
  assert.equal((await readFile('work/slides-html-qa/slides.pdf')).subarray(0,5).toString(),'%PDF-');const zip=await JSZip.loadAsync(await readFile('work/slides-html-qa/slides.pptx'));const xml=await zip.file('ppt/slides/slide1.xml').async('string');const text=[...xml.matchAll(/<a:t>(.*?)<\/a:t>/g)].map(m=>m[1]).join('');assert.match(text,/Titolo modificato/);assert.match(xml,/FFD166/i);
  const html=await readFile('work/slides-html-qa/slides.html','utf8');assert.match(html,/display: grid/);assert.match(html,/data:image/);assert.ok(!html.includes('<script'));
  await page.reload();await page.click(`[data-chat="${fixture.chat}"]`);await page.click('#canvas-toggle');await iframe().locator('h1').waitFor();assert.match(await iframe().locator('h1').textContent(),/Titolo modificato/);
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(300);assert.ok(await page.locator('.slides-viewport').evaluate(e=>e.getBoundingClientRect().width>100));assert.deepEqual(errors,[]);
  assert.ok(!remote.some(url=>url.includes('example.com')),'Generated HTML must not access the network');
  console.log('Free HTML: streaming, original CSS/SVG, isolation, graphical edits, RAG/PC image replacement, persistent media, editable PPTX, PDF, HTML and mobile passed.');
}catch(e){console.error(diagnostics);await page.screenshot({path:'work/slides-html-qa/error.png',fullPage:true});throw e;}finally{await browser.close();child.kill();}
