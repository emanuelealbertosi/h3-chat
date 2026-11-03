import {spawn} from 'node:child_process';import {createRequire} from 'node:module';import {once} from 'node:events';import {createInterface} from 'node:readline';import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn(process.env.H3_TEST_PYTHON||'runtime/python/python.exe',['-X','utf8','tests/serve_study_fixture.py'],{stdio:['ignore','pipe','pipe']});let logs='';child.stderr.on('data',b=>logs+=b);
const lines=createInterface({input:child.stdout});const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(logs);})]);lines.close();
const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']}),page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(fixture.url);await page.click(`[data-chat="${fixture.chat}"]`);await page.click('#voice-toggle');await page.click('[data-mode-settings="voice-inputs"]');
 const modal=page.locator('#prompt-mode-settings'),group=modal.getByRole('group',{name:'Timbro vocale',exact:true});
 await group.getByRole('button',{name:'Limpida · italiana · Higgs BF16',exact:true}).click();
 assert.equal(await modal.locator('[data-voice-field="profile"]').inputValue(),'limpida');assert.equal(await modal.locator('[data-voice-field="engine"]').inputValue(),'higgs');await modal.locator('footer button').click();
 await page.reload();await page.click(`[data-chat="${fixture.chat}"]`);await page.click('[data-mode-settings="voice-inputs"]');assert.equal(await modal.locator('[data-voice-field="profile"]').inputValue(),'limpida');await modal.locator('footer button').click();
 await page.click('#prompt-study');await page.click('[data-mode-settings="study-options"]');
 await modal.locator('[data-study="kind"]').selectOption('dialogue');await modal.locator('[data-study="count"]').fill('2');await modal.locator('[data-study="source_text"]').fill('La fotosintesi utilizza luce, acqua e anidride carbonica. Le piante producono ossigeno e zuccheri.');
 await modal.locator('[data-study-voice="voice_a"]').selectOption('limpida');await modal.locator('[data-study-voice="voice_b"]').selectOption('aurora');await modal.locator('footer button').click();
 const queued=page.waitForResponse(r=>r.url().endsWith('/messages')&&r.request().method()==='POST');await page.fill('#prompt','Crea un dialogo di studio dalle fonti');await page.click('#send');const ticket=await(await queued).json();
 await page.evaluate(async job=>{const state=await fetch('/api/state').then(r=>r.json());await fetch('/fixture/execute',{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':state.token},body:JSON.stringify({job})});},ticket.job_id);
 await page.reload();await page.click(`[data-chat="${fixture.chat}"]`);if(!await page.locator('#canvas-panel').isVisible())await page.click('#canvas-toggle');await page.locator('.study-view').waitFor();
 assert.equal(await page.locator('.study-view [data-study-voice="voice_a"]').inputValue(),'limpida');assert.equal(await page.locator('.study-view [data-study-voice="voice_b"]').inputValue(),'aurora');
 await page.route('**/study/*/audio',route=>route.fulfill({json:{job_id:'synthetic-audio',canvas:true,intent:'study_audio'}}));
 await page.locator('.study-audio-options > summary').click();const sent=page.waitForRequest(r=>r.url().endsWith('/audio')&&r.method()==='POST');await page.getByRole('button',{name:'Crea audio a due voci',exact:true}).click();assert.deepEqual((await sent).postDataJSON(),{voice_a:'limpida',voice_b:'aurora'});
 assert.deepEqual(errors,[]);console.log('PASS: Voice named profiles persist; Studio settings and canvas select A/B and send exact choices. No synthesis.');
}finally{await browser.close();child.kill();}
