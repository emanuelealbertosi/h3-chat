import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe'],env:{...process.env,H3_FIXTURE_STEERING:'1'}});
let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);
const lines=createInterface({input:child.stdout});const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);lines.close();
const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']}),page=await browser.newPage(),errors=[];
page.on('pageerror',e=>errors.push(e.message));
const field=k=>page.locator('[data-llm-setting="'+k+'"]');
try{
 await page.route('**/api/state',async route=>{
  const response=await route.fetch(),state=await response.json(),model=state.models.find(m=>m.id===fixture.model);
  // UI-only shape fixture: no weights or inference are involved.
  model.identity={...model.identity,architecture:'qwen35'};model.parameters={...model.parameters,embedding:5120,layers:65};
  await route.fulfill({response,json:state});
 });
 await page.goto(fixture.url);await page.click(`[data-chat="${fixture.chat}"]`);await page.click('#settings-open');await page.waitForFunction(()=>document.querySelector('#settings').open);await page.click('[data-tab="advanced"]');await page.selectOption('#llm-settings-model',fixture.model);
 assert.equal(await field('llm_steering_enabled').isChecked(),false);assert.equal(await field('llm_steering_enabled').isEnabled(),true);
 assert.equal(await field('llm_steering_file').isDisabled(),true);
 await field('llm_steering_enabled').check();await field('llm_steering_file').fill(fixture.steering_file);await field('llm_steering_strength').fill('0.03');
 await page.selectOption('#llm-settings-model',fixture.second_model);assert.equal(await field('llm_steering_enabled').isDisabled(),true);assert.equal(await field('llm_steering_enabled').isChecked(),false);
 await page.selectOption('#llm-settings-model',fixture.model);assert.equal(await field('llm_steering_enabled').isChecked(),true);assert.equal(await field('llm_steering_strength').inputValue(),'0.03');
 const saved=page.waitForResponse(r=>r.url().endsWith('/api/settings'));await page.click('#settings-save');assert.equal((await saved).status(),200);
 await page.reload();await page.click(`[data-chat="${fixture.chat}"]`);await page.click('#settings-open');await page.click('[data-tab="advanced"]');await page.selectOption('#llm-settings-model',fixture.model);
 assert.equal(await field('llm_steering_file').inputValue(),fixture.steering_file);assert.equal(await field('llm_steering_enabled').isChecked(),true);
 await field('llm_steering_enabled').uncheck();assert.equal(await field('llm_steering_strength').isDisabled(),true);
 assert.deepEqual(errors,[]);console.log('Steering controls: opt-in, unsupported-model exclusion, per-model persistence, reload and disable passed. Disposable fixture only.');
}catch(error){console.error(diagnostics);throw error;}finally{await browser.close();child.kill();}
