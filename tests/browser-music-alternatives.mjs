import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let log='';child.stderr.on('data',v=>log+=v);
const lines=createInterface({input:child.stdout});const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(log);})]);lines.close();const fixture=JSON.parse(line);
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']}),page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));let submitted;
try{
 await page.route('**/api/state',async route=>{const response=await route.fetch(),s=await response.json();s.models.push({id:'yue-fixture',name:'YuE2 test',ready:true,engine:'music',capabilities:['music']},{id:'mini-fixture',name:'MiniMax Music 3 test',architecture:'minimax-music',engine:'vision',ready:true,capabilities:['music']});s.settings.music_model='yue-fixture';await route.fulfill({response,json:s});});
 await page.route('**/api/chats/*/messages',async route=>{submitted=route.request().postDataJSON();await route.fulfill({json:{job_id:'fixture-only',intent:'music'}});});
 await page.goto(fixture.url);await page.locator('[data-chat="'+fixture.chat+'"]').click();await page.click('#music-toggle');
 const resing=page.locator('[data-music-resing]');assert(await resing.isVisible());await resing.click();assert.equal(await resing.getAttribute('aria-pressed'),'true');
 await page.click('[data-mode-settings="music-inputs"]');await page.locator('[data-music-request-model]').selectOption('mini-fixture');
 assert.equal(await page.locator('[data-music-request="top_k"]').inputValue(),'50');assert.equal(await page.locator('[data-music-request="cot"]').count(),0);assert.equal(await page.locator('[data-music-field="abc"]').isVisible(),false);
 await page.locator('[data-music-request="seed"]').fill('27');await page.locator('[data-music-request="top_k"]').fill('25');await page.locator('[data-music-field="lyrics"]').fill('[Verse]\nNuovo sole');
 await page.locator('#prompt-mode-settings footer button').click();assert(await resing.isDisabled());assert.equal(await resing.getAttribute('aria-pressed'),'false');
 await page.locator('#prompt').fill('Crea il brano');await page.click('#send');await page.waitForFunction(()=>document.querySelector('#prompt').value==='');
 assert.equal(submitted.music_model,'mini-fixture');assert.equal(submitted.music_parameters.seed,27);assert.equal(submitted.music_parameters.top_k,25);assert.equal(submitted.music_resing,false);assert.equal(submitted.music_fields.lyrics,'[Verse]\nNuovo sole');assert.equal(submitted.music_fields.abc,'');
 await page.click('[data-mode-settings="music-inputs"]');await page.locator('[data-music-request-model]').selectOption('yue-fixture');assert.equal(await page.locator('[data-music-request="cot"]').inputValue(),'full');assert.equal(await page.locator('[data-music-request="top_k"]').count(),0);await page.locator('#prompt-mode-settings footer button').click();assert.equal(await resing.isDisabled(),false);
 await page.reload();await page.locator('[data-chat="'+fixture.chat+'"]').click();await page.waitForFunction(()=>document.querySelector('#music-toggle').getAttribute('aria-pressed')==='true');await page.click('[data-mode-settings="music-inputs"]');await page.locator('[data-music-request-model]').selectOption('mini-fixture');assert.equal(await page.locator('[data-music-request="seed"]').inputValue(),'27');await page.locator('#prompt-mode-settings footer button').click();
 await page.click('#settings-open');await page.click('[data-tab="advanced"]');await page.locator('#music-settings-model').selectOption('mini-fixture');assert.equal(await page.locator('[data-minimax-setting="top_k"]').inputValue(),'50');await page.locator('[data-minimax-setting="top_k"]').fill('35');
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);assert.deepEqual(errors,[]);
 console.log('PASS: per-chat music engine, distinct controls, persistent presets, Re-sing button next to settings, correct submitted payload and responsive preferences. No inference.');
}finally{await browser.close();child.kill();}
