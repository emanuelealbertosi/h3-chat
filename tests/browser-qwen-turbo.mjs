import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostic='';child.stderr.on('data',x=>diagnostic+=x);
const lines=createInterface({input:child.stdout});const first=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostic);})]);const fixture=JSON.parse(first[0]);lines.close();
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 const state=await (await page.request.get(fixture.url+'/api/state')).json();const video=state.models.find(m=>m.id===state.settings.video_model);
 const files=Object.fromEntries(video.files.filter(f=>['diffusion','llm','vae'].includes(f.role)).map(f=>[f.role,f.path]));
 const response=await page.request.post(fixture.url+'/api/external-models',{data:{profile:'qwen21-turbo',name:'Turbo sintetico',files},headers:{'X-H3-Token':state.token}});assert.equal(response.status(),201);const model=await response.json();
 await page.goto(fixture.url);await page.waitForSelector('#settings-open');await page.click('#settings-open');await page.click('[data-tab="advanced"]');
 await page.selectOption('#image-settings-model',model.id);assert.match(await page.locator('.image-preset-summary').innerText(),/8 step · CFG 1/);assert.match(await page.locator('.image-preset-summary').innerText(),/8 passi ufficiali/);
 await page.check('#image-advanced');assert.equal(await page.inputValue('[data-image-setting="scheduler"]'),'qwen21_turbo');assert.equal(await page.inputValue('[data-image-setting="steps"]'),'8');
 await page.fill('[data-image-setting="width"]','768');const saved=page.waitForResponse(r=>r.url().endsWith('/settings')&&r.request().method()==='POST');await page.click('#settings-save');assert.equal((await saved).status(),200);
 await page.click('#settings-open');await page.click('[data-tab="advanced"]');await page.selectOption('#image-settings-model',model.id);assert.equal(await page.inputValue('[data-image-setting="width"]'),'768');assert.equal(await page.inputValue('[data-image-setting="steps"]'),'8');
 assert.deepEqual(errors,[]);console.log('Turbo profile, official scheduler label, eight-step defaults and per-model settings save passed.');
}catch(error){console.error(diagnostic);throw error;}finally{await browser.close();child.kill();}
