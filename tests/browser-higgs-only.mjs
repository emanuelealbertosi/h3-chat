import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostic='';child.stderr.on('data',x=>diagnostic+=x);
const lines=createInterface({input:child.stdout}),first=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostic);})]);const fixture=JSON.parse(first[0]);lines.close();
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(fixture.url);await page.evaluate(id=>localStorage.setItem('h3.visual-options.'+id,JSON.stringify({voice:true,voice_fields:{engine:'chatterbox',emotion:'enthusiasm',pitch:'high',params:{chatterbox:{temperature:.8}}}})),fixture.chat);await page.reload();await page.locator(`[data-chat="${fixture.chat}"]`).click();
 const group=page.locator('#voice-inputs [aria-label="Motore vocale"]');assert.equal(await group.locator('button').count(),1);assert.equal(await group.locator('[data-value="higgs"]').getAttribute('aria-pressed'),'true');
 await page.waitForFunction(()=>document.querySelector('#voice-inputs [data-voice-field="emotion"]').value==='enthusiasm');
 assert.equal(await page.locator('#voice-inputs [data-voice-field="emotion"]').inputValue(),'enthusiasm');assert.equal(await page.locator('#voice-inputs [data-voice-field="pitch"]').inputValue(),'high');
 assert.equal(await page.locator('#voice-inputs [data-voice-field="emotion"]').evaluate(e=>e.closest('.prompt-field').hidden),false);
 await page.click('[data-mode-settings="voice-inputs"]');assert.match(await page.locator('#voice-inputs').textContent(),/Higgs/);await page.locator('#prompt-mode-settings footer button').click();
 await page.route('**/api/chats/*/messages',r=>r.fulfill({json:{job_id:'synthetic',intent:'voice'}}));const pending=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith('/messages'));
 await page.fill('#prompt','Testo: Oggi impariamo qualcosa di nuovo.');await page.locator('#composer').evaluate(e=>e.requestSubmit());const sent=(await pending).postDataJSON();assert.equal(sent.voice_fields.engine,'higgs');assert.equal(sent.voice_fields.emotion,'enthusiasm');assert.equal(sent.voice_fields.pitch,'high');assert.deepEqual(sent.voice_fields.params,{});
 await page.click('#settings-open');await page.click('[data-tab="advanced"]');assert.equal(await page.locator('[data-setting="voice_engine"] option').count(),1);assert.equal(await page.locator('[data-setting^="voice_qwen"],[data-setting^="voice_chatterbox"]').count(),0);
 const precision=page.locator('[data-setting="voice_precision"]');assert.equal(await precision.inputValue(),'8bit');assert.deepEqual(await precision.locator('option').evaluateAll(nodes=>nodes.map(n=>n.value)),['4bit','8bit','bf16']);await precision.selectOption('bf16');assert.equal(await precision.inputValue(),'bf16');assert.match(await precision.locator('option:checked').textContent(),/senza quantizzazione/);
 const state=await(await page.request.get(fixture.url+'/api/state')).json();assert.deepEqual(Object.keys(state.voice_engines),['higgs']);assert.deepEqual(errors,[]);console.log('PASS: cached retired engine becomes Higgs, chosen acting retained, sent request and settings expose Higgs only.');
}catch(e){console.error(diagnostic);throw e;}finally{await browser.close();child.kill();}
