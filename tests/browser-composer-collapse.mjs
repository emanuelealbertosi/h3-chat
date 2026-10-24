import {spawn} from 'node:child_process';import {once} from 'node:events';import {createInterface} from 'node:readline';import {createRequire} from 'node:module';import {mkdirSync} from 'node:fs';import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_execution_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);
const lines=createInterface({input:child.stdout}),first=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]),fixture=JSON.parse(first[0]);lines.close();
let browser;
try{
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(fixture.url);await page.locator('#prompt-collapse').waitFor();
 await page.locator('#new-chat').click();await page.locator('#prompt-slides').click();
 await page.locator('[data-mode-settings=slides-options]').click();await page.locator('#slides-timeout').fill('6000');await page.locator('#prompt-mode-settings').getByRole('button',{name:'Fatto',exact:true}).click();
 await page.locator('#prompt').fill('Bozza da conservare senza inviarla');
 const open=await page.locator('#scroll-area').boundingBox();assert.ok(open.height>200,JSON.stringify(open));
 const area=await page.locator('.composer-area').boundingBox();assert.ok(area.height<=720*.55+1,JSON.stringify(area));
 assert.equal(await page.locator('#send').isVisible(),true);
 await page.locator('#prompt-collapse').click();assert.equal(await page.locator('#composer').isVisible(),false);
 assert.match(await page.locator('.prompt-collapsed-summary').innerText(),/Slide.*Bozza presente/);
 const closed=await page.locator('#scroll-area').boundingBox();assert.ok(closed.height-open.height>150,JSON.stringify({open,closed}));
 assert.equal(await page.locator('#prompt-collapse').getAttribute('aria-expanded'),'false');
 await page.locator('#prompt-collapse').press('Enter');assert.equal(await page.locator('#composer').isVisible(),true);assert.equal(await page.locator('#prompt').inputValue(),'Bozza da conservare senza inviarla');assert.equal(await page.locator('#slides-timeout').inputValue(),'6000');assert.equal(await page.locator('#prompt').evaluate(e=>e===document.activeElement),true);
 await page.locator('#prompt-collapse').click();await page.reload();await page.locator('#prompt-collapse[aria-expanded=false]').waitFor();assert.equal(await page.locator('#composer').isVisible(),false);
 // Restoring a suggested prompt must reveal the composer even after a reload.
 await page.locator('[data-prompt]').first().click();assert.equal(await page.locator('#composer').isVisible(),true);assert.ok((await page.locator('#prompt').inputValue()).length>0);
 // The fixture has no worker: queue/cancel exercises the real UI without inference.
 await page.locator('#prompt-auto').click();await page.locator('#prompt').fill('Richiesta del test isolato');await page.locator('#send').click();await page.locator('#stop').waitFor();
 await page.locator('#prompt-collapse').click();assert.equal(await page.locator('#stop').isVisible(),true);assert.equal(await page.locator('#job-status').isVisible(),true);
 await page.locator('#stop').click();await page.waitForFunction(()=>document.querySelector('#stop').hidden);assert.equal(await page.locator('#composer').isVisible(),false);
 await page.setViewportSize({width:390,height:640});await page.waitForTimeout(250);await page.locator('#prompt-collapse').click();assert.equal(await page.locator('#send').isVisible(),true);
 const send=await page.locator('#send').boundingBox();assert.ok(send.x>=0&&send.x+send.width<=390,JSON.stringify(send));
 const small=await page.locator('#scroll-area').boundingBox();assert.ok(small.height>150,JSON.stringify(small));assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 mkdirSync('work/composer-collapse-2026-10-24',{recursive:true});await page.screenshot({path:'work/composer-collapse-2026-10-24/mobile-open.png'});await page.locator('#prompt-collapse').click();await page.screenshot({path:'work/composer-collapse-2026-10-24/mobile-collapsed.png'});
 assert.deepEqual(errors,[]);console.log(JSON.stringify({status:'passed',desktop_chat_height_open:open.height,desktop_chat_height_collapsed:closed.height,mobile_chat_height_open:small.height,draft_and_settings_preserved:true,reload_persistence:true,keyboard_and_programmatic_reopen:true,stop_works_when_collapsed:true,real_inference_started:false}));
}catch(e){console.error(diagnostics);throw e;}finally{await browser?.close();child.kill();}
