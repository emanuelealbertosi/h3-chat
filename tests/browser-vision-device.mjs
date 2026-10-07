import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostic='';child.stderr.on('data',x=>diagnostic+=x);
const lines=createInterface({input:child.stdout}),timer=setTimeout(()=>child.kill(),30000);const first=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostic);})]);clearTimeout(timer);const fixture=JSON.parse(first[0]);lines.close();
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 const state=await(await fetch(fixture.url+'/api/state')).json();
 const response=await fetch(fixture.url+'/api/settings',{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':state.token},body:JSON.stringify({profile:'low',backend:'cuda'})});assert.equal(response.status,200);
 await page.route('**/api/state',async route=>{const r=await route.fetch(),s=await r.json();s.models=s.models.map(m=>m.id===s.settings.chat_model?{...m,vision:{enabled:true}}:m);await route.fulfill({response:r,json:s});});
 await page.goto(fixture.url);const device=page.locator('#chat-vision-device');
 await page.waitForFunction(()=>!document.querySelector('#chat-vision-device').disabled);
 assert.equal(await device.inputValue(),'cpu');
 await page.click('#prompt-options-open');await page.getByRole('button',{name:'GPU',exact:true}).click();await page.getByRole('button',{name:'Fatto',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#vision-badge').textContent==='Vision · GPU'&&!document.querySelector('#chat-vision-device').disabled);
 assert.equal((await(await fetch(fixture.url+'/api/state')).json()).settings.vision_device,'gpu');
 await page.reload();await page.waitForFunction(()=>document.querySelector('#chat-vision-device').value==='gpu'&&!document.querySelector('#chat-vision-device').disabled);
 await page.click('#prompt-options-open');await page.getByRole('button',{name:'CPU',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#vision-badge').textContent==='Vision · CPU');
 await page.getByRole('button',{name:'Vision attiva',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#chat-vision-device').disabled&&document.querySelector('#vision-badge').textContent==='Vision disattivata');
 await page.getByRole('button',{name:'Vision attiva',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#chat-vision-device').disabled);
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 await page.getByRole('button',{name:'Fatto',exact:true}).click();assert.deepEqual(errors,[]);console.log('Vision CPU/GPU: settings API, selection, reload persistence, Vision Off and mobile verified.');
}catch(e){await page.screenshot({path:'work/composer-qa/vision-error.png',fullPage:true});throw e;}finally{await browser.close();child.kill();}
