import {spawn} from 'node:child_process';
import {once} from 'node:events';import {createInterface} from 'node:readline';import {createRequire} from 'node:module';import {mkdirSync} from 'node:fs';import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_execution_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);
const lines=createInterface({input:child.stdout}),first=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]),fixture=JSON.parse(first[0]);lines.close();
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']}),page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(fixture.url);await page.locator('[data-execution=cpu]').waitFor();
 await page.locator('#prompt-slides').click();await page.locator('[data-mode-settings=slides-options]').click();
 await page.getByRole('group',{name:'Testi',exact:true}).getByRole('button',{name:'Scuri',exact:true}).click();
 await page.getByRole('group',{name:'Sfondo',exact:true}).getByRole('button',{name:'Chiaro',exact:true}).click();
 await page.getByRole('group',{name:'Palette',exact:true}).getByRole('button',{name:'Pastello',exact:true}).click();
 assert.equal(await page.locator('#slides-text-tone').inputValue(),'dark');assert.equal(await page.locator('#slides-background').inputValue(),'light');assert.equal(await page.locator('#slides-palette').inputValue(),'pastel');
 await page.locator('#prompt-mode-settings').getByRole('button',{name:'Fatto',exact:true}).click();
 await page.locator('[data-execution=cpu]').click();await page.waitForFunction(()=>document.querySelector('[data-execution=cpu]').getAttribute('aria-pressed')==='true');
 for(const id of ['prompt-images','music-toggle','video-toggle','voice-toggle','prompt-video-edit','transcribe-toggle','upscale-open','video-recreate-open','video-remix-open','video-edit-open'])assert.equal(await page.locator('#'+id).isDisabled(),true,id);
 assert.equal(await page.locator('#chat-model').inputValue(),fixture.api);assert.equal(await page.locator('#chat-model option[value="'+fixture.local+'"]').count(),0);
 let state=await page.evaluate(()=>fetch('/api/state').then(r=>r.json()));assert.equal(state.settings.chat_model,fixture.local);assert.equal(state.settings.rag_device,'gpu');assert.equal(state.execution.mode,'cpu');
 await page.reload();await page.locator('[data-execution=cpu][aria-pressed=true]').waitFor();assert.equal(await page.locator('#prompt-images').isDisabled(),true);
 await page.locator('[data-execution=gpu]').click();await page.waitForFunction(()=>document.querySelector('[data-execution=gpu]').getAttribute('aria-pressed')==='true');
 assert.equal(await page.locator('#prompt-images').isDisabled(),false);assert.equal(await page.locator('#chat-model').inputValue(),fixture.local);
 await page.locator('[data-execution=cpu]').click();await page.waitForFunction(()=>document.querySelector('[data-execution=cpu]').getAttribute('aria-pressed')==='true');
 await page.evaluate(async id=>{const {token}=await(await fetch('/api/state')).json();const r=await fetch('/api/providers/'+id,{method:'DELETE',headers:{'X-H3-Token':token,'Content-Type':'application/json'},body:'{}'});if(!r.ok)throw Error(await r.text());},fixture.api);
 await page.reload();await page.locator('[data-execution=cpu][aria-pressed=true]').waitFor();assert.equal(await page.locator('#send').isDisabled(),true);assert.match(await page.locator('#execution-hint').innerText(),/Collega un provider/);
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(100);assert.equal(await page.locator('[data-execution=cpu]').isVisible(),true);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 mkdirSync('work/execution-mode-qa',{recursive:true});await page.screenshot({path:'work/execution-mode-qa/mobile.png'});assert.deepEqual(errors,[]);console.log('CPU/GPU switch: disabled media, API-only chat selection, refresh persistence, GPU restoration, no-API guidance and mobile passed.');
}catch(e){console.error(diagnostics);throw e;}finally{await browser.close();child.kill();}
