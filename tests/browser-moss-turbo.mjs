import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let logs='';child.stderr.on('data',x=>logs+=x);const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(logs);})]);lines.close();const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']}),page=await browser.newPage({viewport:{width:1380,height:950}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.route('**/api/state',async route=>{const response=await route.fetch(),state=await response.json();state.image_options.moss_dmd2={ready:true};for(const [id,name] of [['mi','MOSS INT8'],['mb','MOSS BF16'],['kr','Kromoss INT8']])state.models.push({id,name,ready:true,local:true,engine:'vision',architecture:'moss',capabilities:['create','edit'],max_refs:1,width:1024,height:1024,steps:50,cfg:3,sampler:'euler',scheduler:'sgm_uniform',strength:.65});state.settings.create_model='mi';await route.fulfill({response,json:state});});
 await page.route('**/api/chats/*/messages',route=>route.fulfill({json:{job_id:'synthetic-only',intent:'create'}}));
 await page.goto(fixture.url);await page.click(`[data-chat="${fixture.chat}"]`);await page.click('#prompt-images');await page.click('[data-mode-settings="prompt-image-panel"]');
 const control=key=>page.locator(`[data-image-request="${key}"]`),flag=()=>page.locator('[data-moss-turbo]');
 await control('steps').fill('30');await control('cfg').fill('4');await control('sampler').selectOption('res_multistep');await control('scheduler').selectOption('simple');await control('seed').fill('42');await control('megapixels').fill('2.25');await control('aspect').selectOption('1:1');
 await flag().check();assert.equal(await control('steps').inputValue(),'8');assert.equal(await control('cfg').inputValue(),'1');assert.equal(await control('sampler').inputValue(),'euler');assert.equal(await control('scheduler').inputValue(),'sgm_uniform');assert(await control('steps').isDisabled());assert.equal(await control('seed').inputValue(),'42');
 await page.locator('#prompt-mode-settings footer button').click();await page.reload();await page.click(`[data-chat="${fixture.chat}"]`);await page.click('[data-mode-settings="prompt-image-panel"]');assert(await flag().isChecked());
 await flag().uncheck();for(const [key,value] of Object.entries({steps:'30',cfg:'4',sampler:'res_multistep',scheduler:'simple',seed:'42',megapixels:'2.25'}))assert.equal(await control(key).inputValue(),value);assert(await control('steps').isEnabled());
 await flag().check();await page.locator('#prompt-mode-settings footer button').click();
 for(const id of ['mb','kr']){await page.selectOption('#image-model',id,{force:true});await page.click('[data-mode-settings="prompt-image-panel"]');assert(!(await flag().isChecked()));await flag().check();assert.equal(await control('steps').inputValue(),'8');await page.locator('#prompt-mode-settings footer button').click();}
 await page.selectOption('#image-model','mi',{force:true});await page.click('[data-mode-settings="prompt-image-panel"]');assert(await flag().isChecked());
 await mkdir('work/moss-dmd2-2026-10-23/browser',{recursive:true});await page.screenshot({path:'work/moss-dmd2-2026-10-23/browser/turbo-desktop.png'});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'work/moss-dmd2-2026-10-23/browser/turbo-mobile.png'});assert.equal(await page.locator('#prompt-mode-settings').evaluate(e=>e.scrollWidth>e.clientWidth+2),false);
 await page.locator('#prompt-mode-settings footer button').click();const request=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith('/messages'));await page.fill('#prompt','A cat');await page.click('#send');const body=(await request).postDataJSON();assert(body.image_parameters.moss_turbo);assert.equal(body.image_parameters.steps,8);assert.equal(body.image_parameters.moss_turbo_previous.steps,30);assert.equal(body.image_parameters.seed,42);assert.deepEqual(errors,[]);
 console.log('PASS: Turbo toggle, reload, restoration, INT8/BF16/Kromoss isolation, payload and mobile; no real generation.');
}finally{await browser.close();child.kill();}
