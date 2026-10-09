import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostic='';child.stderr.on('data',x=>diagnostic+=x);
const lines=createInterface({input:child.stdout});const first=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostic);})]);const fixture=JSON.parse(first[0]);lines.close();
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
let phase='queued',now=130;
try{
 await page.route('**/api/state',async route=>{const response=await route.fetch(),state=await response.json();state.server_time=now;
  state.jobs=[{id:'timing-job',chat_id:fixture.chat,message_id:'timing-message',created:100,status:phase,stage:phase==='queued'?'In coda · attesa motore':'Scrittura della risposta'}];await route.fulfill({response,json:state});});
 await page.route('**/api/chats/'+fixture.chat,async route=>{const response=await route.fetch(),chat=await response.json();const timing=phase==='queued'?{}:phase==='running'?{queued_at:100,started_at:130}:{queued_at:100,started_at:130,finished_at:195,elapsed_seconds:65,queue_seconds:30,total_seconds:95};
  chat.messages=[{id:'timing-message',role:'assistant',status:phase,content:phase==='done'?'Risposta completata.':'',media:[],meta:{intent:'chat',timing}}];await route.fulfill({response,json:chat});});
 await page.goto(fixture.url);await page.waitForSelector(`[data-chat="${fixture.chat}"]`);await page.click(`[data-chat="${fixture.chat}"]`);
 const article=page.locator('#msg-timing-message');await article.locator('.activity-elapsed').waitFor();assert.equal(await article.locator('.activity-elapsed').innerText(),'In coda da: 30 s');
 phase='running';now=140;await page.waitForFunction(()=>document.querySelector('.activity-elapsed')?.textContent==='Tempo trascorso: 10 s · Attesa in coda: 30 s');
 phase='done';now=195;await article.locator('.message-duration').waitFor();assert.equal(await article.locator('.message-duration').innerText(),'Durata: 1 min 5 s · Attesa in coda: 30 s');assert.equal(await article.locator('.generation-activity').count(),0);
 now=500;await page.reload();await page.waitForSelector(`[data-chat="${fixture.chat}"]`);await page.click(`[data-chat="${fixture.chat}"]`);await article.locator('.message-duration').waitFor();assert.equal(await article.locator('.message-duration').innerText(),'Durata: 1 min 5 s · Attesa in coda: 30 s');
 await page.setViewportSize({width:390,height:844});assert.ok(await article.locator('.message-duration').isVisible());assert.deepEqual(errors,[]);
 console.log('Browser request timings: queued, running, completed, retained after reload and visible on mobile.');
}catch(error){console.error(diagnostic);throw error;}finally{await browser.close();child.kill();}
