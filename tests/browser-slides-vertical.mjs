import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright'),JSZip=require('jszip');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);
const lines=createInterface({input:child.stdout});const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);lines.close();const fixture=JSON.parse(line);
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await mkdir('work/vertical-slides-qa',{recursive:true});await page.goto(fixture.url);await page.click(`[data-chat="${fixture.chat}"]`);await page.click('#prompt-slides');await page.getByRole('button',{name:'9:16',exact:true}).click();assert.equal(await page.inputValue('#slides-format'),'9:16');
 await page.evaluate(async chat=>{
  const {token}=await(await fetch('/api/state')).json(),headers={'Content-Type':'application/json','X-H3-Token':token};
  const created=await fetch('/fixture/slides/html',{method:'POST',headers,body:'{}'});if(!created.ok)throw Error(await created.text());
  const canvas=await(await fetch('/api/canvas/'+chat)).json(),deck=JSON.parse(canvas.content.slice(13,-4));deck.format='9:16';deck.pages[0].html='<style>body{background:#163e48;color:white;padding:70px;font:38px Arial}h1{font-size:78px}.bottom{position:absolute;top:1800px}</style><h1>Infografica verticale</h1><p>Testo modificabile e proporzioni mantenute.</p><p class="bottom">Ultimo blocco</p>';
  canvas.content='```h3-slides\n'+JSON.stringify(deck)+'\n```';const saved=await fetch('/api/canvas/'+chat,{method:'PUT',headers,body:JSON.stringify(canvas)});if(!saved.ok)throw Error(await saved.text());
 },fixture.chat);
 await page.click('#canvas-toggle');const iframe=page.frameLocator('.h3-html-page iframe');await iframe.locator('h1').filter({hasText:'Infografica verticale'}).waitFor();await page.waitForFunction(()=>parseFloat(document.querySelector('.h3-html-page')?.style.height)>2000);
 const frame=await page.locator('.h3-html-page').evaluate(e=>({width:e.offsetWidth,height:parseFloat(e.style.height)}));assert.ok(Math.abs(frame.width/frame.height-9/16)<2e-5);
 await page.click('#slide-edit');await iframe.locator('.bottom').click();await page.click('#slide-html-properties summary');assert.ok(Number(await page.getAttribute('#slide-html-height','max'))>2200);await page.click('#slide-html-save');
 await page.waitForFunction(()=>document.querySelector('#canvas-save-status')?.textContent.includes('Salvato'));
 for(const kind of ['pdf','pptx']){const event=page.waitForEvent('download',{timeout:120000});await page.click(`[data-export="${kind}"]`);await(await event).saveAs('work/vertical-slides-qa/slides.'+kind);}
 assert.equal((await readFile('work/vertical-slides-qa/slides.pdf')).subarray(0,5).toString(),'%PDF-');
 const zip=await JSZip.loadAsync(await readFile('work/vertical-slides-qa/slides.pptx')),xml=await zip.file('ppt/presentation.xml').async('string'),size=xml.match(/<p:sldSz[^>]*cx="(\d+)"[^>]*cy="(\d+)"/);assert.ok(size);assert.ok(Math.abs(Number(size[1])/Number(size[2])-9/16)<1e-6);
 await page.screenshot({path:'work/vertical-slides-qa/canvas.png',fullPage:true});assert.deepEqual(errors,[]);console.log('PASS: vertical format selection, canvas aspect ratio, full-height editing, PDF and portrait PowerPoint export.');
}catch(e){console.error(diagnostics);throw e;}finally{await browser.close();child.kill();}
