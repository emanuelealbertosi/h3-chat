import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);
const lines=createInterface({input:child.stdout});const first=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);const fixture=JSON.parse(first[0]);lines.close();
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1400,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(fixture.url);await page.click('#prompt-manim');await page.click('[data-mode-settings="manim-presentation-options"]');
 assert.equal(await page.locator('#manim-presentation-enable').isDisabled(),true);
 await page.locator('#file-input').setInputFiles({name:'slide.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4\nsynthetic upload only')});
 await page.waitForFunction(()=>!document.querySelector('#manim-presentation-enable').disabled);await page.click('#manim-presentation-enable');
 assert.equal(await page.getAttribute('[data-manim-mode="preserve"]','aria-pressed'),'true');
 await page.click('[data-manim-mode="reconstruct"]');
 await page.route('**/api/chats/*/messages',route=>route.fulfill({json:{job_id:'synthetic',intent:'manim'}}));
 await page.locator('#prompt-mode-settings footer button').click();const request=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith('/messages'));await page.fill('#prompt','Anima questa presentazione');await page.locator('#composer').evaluate(e=>e.requestSubmit());
 const body=(await request).postDataJSON();assert.deepEqual(body.manim_presentation,{mode:'reconstruct',source:'attachments'});assert.equal(body.media[0].mime,'application/pdf');
 await page.waitForFunction(()=>document.querySelectorAll('#attachments .attachment').length===0);assert.equal(await page.locator('#manim-presentation-enable').isDisabled(),true);
 // Use a complete canvas deck; this exercises actual PDF capture and upload.
 await page.evaluate(async id=>{
  const state=await fetch('/api/state').then(r=>r.json());const deck={version:1,engine:'llm',format:'4:3',title:'Canvas test',pages:[{title:'Prima',status:'ready',html:'<main style="background:#cfeedd;padding:60px"><h1>Prima slide</h1><p>Una spiegazione completa.</p></main>'},{title:'Seconda',status:'ready',html:'<main style="background:#ffeedd;padding:60px"><h1>Seconda slide</h1></main>'}]};
  const response=await fetch('/api/canvas/'+id,{method:'PUT',headers:{'Content-Type':'application/json','X-H3-Token':state.token},body:JSON.stringify({title:'Canvas test',content:'```h3-slides\n'+JSON.stringify(deck)+'\n```',media:[]})});if(!response.ok)throw Error(await response.text());
 },fixture.chat);
 await page.reload();await page.click(`[data-chat="${fixture.chat}"]`);await page.click('#prompt-manim');await page.click('#canvas-toggle');await page.click('[data-mode-settings="manim-presentation-options"]');
 await page.waitForFunction(()=>!document.querySelector('[data-manim-source="canvas"]').disabled);await page.click('#manim-presentation-enable');
 assert.equal(await page.getAttribute('[data-manim-source="canvas"]','aria-pressed'),'true');
 await page.locator('#prompt-mode-settings footer button').click();const canvasRequest=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith('/messages'));await page.fill('#prompt','Anima le slide nel canvas');await page.locator('#composer').evaluate(e=>e.requestSubmit());
 const captured=(await canvasRequest).postDataJSON();assert.deepEqual(captured.manim_presentation,{mode:'preserve',source:'canvas'});assert.equal(captured.media.length,1);assert.equal(captured.media[0].mime,'application/pdf');
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 assert.deepEqual(errors,[]);console.log('Manim source gating, mode payload, removal reset, actual canvas PDF capture and mobile passed.');
}catch(e){console.error(diagnostics);throw e;}finally{await browser.close();child.kill();}
