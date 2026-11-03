import {spawn} from 'node:child_process';import {createRequire} from 'node:module';import {once} from 'node:events';import {createInterface} from 'node:readline';import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostics='';child.stderr.on('data',b=>diagnostics+=b);
const lines=createInterface({input:child.stdout});const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);lines.close();const fixture=JSON.parse(line);
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']}),page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(fixture.url);await page.click(`[data-chat="${fixture.chat}"]`);await page.click('#prompt-infographic');await page.click('[data-mode-settings="infographic-options"]');
 await page.locator('[data-infographic-field="character_animation"] [data-value="articulated"]').click();await page.locator('[data-infographic-field="pace"] [data-value="explainer"]').click();
 assert.equal(await page.locator('[data-infographic-field="animation_engine"] [data-value="motion"]').getAttribute('aria-pressed'),'true');
 await page.locator('#prompt-mode-settings footer button').click();
 await page.route('**/api/chats/*/messages',route=>route.fulfill({json:{job_id:'synthetic',canvas:true,intent:'infographic'}}));
 const sending=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith('/messages'));await page.fill('#prompt','Personaggio articolato che saluta.');await page.locator('#composer').evaluate(e=>e.requestSubmit());
 const sent=(await sending).postDataJSON();assert.equal(sent.infographic.character_animation,'articulated');assert.equal(sent.infographic.pace,'explainer');assert.equal(sent.infographic.layout,'full');
 await page.unroute('**/api/chats/*/messages');
 const joints=await page.evaluate(async()=>{const {token}=await(await fetch('/api/state')).json();const r=await fetch('/fixture/motion-rig',{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':token},body:'{}'});if(!r.ok)throw Error(await r.text());return r.json();});
 await page.reload();await page.click(`[data-chat="${fixture.chat}"]`);await page.click('#canvas-toggle');await page.locator('[data-save]').first().waitFor();
 const slider=page.locator('#canvas-preview [data-time]').first();
 const seek=async time=>{await slider.evaluate((e,t)=>{e.value=t;e.dispatchEvent(new Event('input',{bubbles:true}));},String(time));return page.evaluate(({upper,lower})=>{const doc=document.querySelector('#canvas-preview iframe').contentDocument,u=doc.querySelector(`[data-h3-motion-object="${upper}"]`).getCTM(),l=doc.querySelector(`[data-h3-motion-object="${lower}"]`).getCTM();const expected=new DOMPoint(0,117).matrixTransform(u);return {upper:[u.a,u.b,u.c,u.d,u.e,u.f],lower:[l.a,l.b,l.c,l.d,l.e,l.f],jointError:Math.hypot(expected.x-l.e,expected.y-l.f),crops:doc.querySelectorAll('svg svg').length};},joints);};
 const first=await seek(1.05),raised=await seek(3.5),again=await seek(1.05);assert.notDeepEqual(first.upper,raised.upper);assert.deepEqual(first,again);assert.ok(raised.jointError<.001);assert.equal(raised.crops,10);
 assert.ok(await page.getByText('Salva personaggio animabile · Personaggio sintetico',{exact:true}).count());assert.deepEqual(errors,[]);
 console.log('PASS: opt-in articulated mode and rapid pace reach request; atlas cropping, attached elbow, gesture changes, deterministic seek, and save-character control work on CPU.');
}catch(e){console.error(diagnostics);throw e;}finally{await browser.close();child.kill();}
