import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));const base=process.env.H3_TEST_URL||'http://127.0.0.1:8789';
const state=async()=>await (await page.request.get(base+'/api/state')).json();
const save=async()=>{const r=page.waitForResponse(r=>r.url().endsWith('/api/settings'));await page.click('#settings-save');assert.equal((await r).status(),200);await page.waitForFunction(()=>!document.querySelector('#settings').open);};
const field=k=>'[data-llm-setting="'+k+'"]';
try{
 await page.goto(base);await page.waitForFunction(()=>document.querySelector('#generation-settings').textContent.includes('Contesto'));
 let s=await state();const a=s.settings.chat_model,b=s.models.find(m=>m.id!==a&&m.capabilities.includes('chat')).id;
 const images=s.models.filter(m=>m.engine==='vision'),ia=images.find(m=>m.architecture==='qwen21').id,ib=images.find(m=>m.architecture==='ming').id;
 await page.click('#settings-open');await page.click('[data-tab="advanced"]');
 await page.selectOption('#llm-settings-model',a);await page.fill(field('context'),'65536');await page.fill(field('max_tokens'),'6000');await page.fill(field('temperature'),'0.8');
 await page.selectOption('#llm-settings-model',b);await page.fill(field('context'),'8192');await page.fill(field('max_tokens'),'2048');await page.fill(field('temperature'),'0.2');
 await page.selectOption('#image-settings-model',ia);await page.check('#image-advanced');
 for(const [k,v] of Object.entries({width:768,height:512,steps:9,cfg:1,seed:123}))await page.fill('[data-image-setting="'+k+'"]',String(v));
 await page.selectOption('#image-settings-model',ib);
 for(const [k,v] of Object.entries({width:1024,height:1024,steps:5,cfg:2,seed:456}))await page.fill('[data-image-setting="'+k+'"]',String(v));
 await save();s=await state();assert.equal(s.settings.chat_model,a);assert.equal(s.settings.context,65536);assert.equal(s.settings.llm_overrides[b].context,8192);
 assert.equal(s.settings.image_overrides[ia].steps,9);assert.equal(s.settings.image_overrides[ib].steps,5);assert.equal(s.settings.image_overrides[ia].seed,123);
 await page.click('#settings-open');await page.selectOption('[data-setting="chat_model"]',b);await save();s=await state();assert.equal(s.settings.context,8192);assert.equal(s.settings.temperature,.2);assert.equal(s.settings.max_tokens,2048);
 await page.click('#settings-open');await page.selectOption('[data-setting="chat_model"]',a);await save();s=await state();assert.equal(s.settings.context,65536);assert.equal(s.settings.temperature,.8);
 await page.reload();await page.waitForFunction(()=>document.querySelector('#generation-settings').textContent.includes('Contesto'));
 await page.click('#settings-open');await page.click('[data-tab="advanced"]');await page.selectOption('#image-settings-model',ia);
 assert.equal(await page.inputValue('[data-image-setting="width"]'),'768');assert.equal(await page.inputValue('[data-image-setting="steps"]'),'9');
 await page.selectOption('#image-settings-model',ib);assert.equal(await page.inputValue('[data-image-setting="steps"]'),'5');assert.equal(await page.inputValue('[data-image-setting="seed"]'),'456');
 assert.equal(await page.locator('#image-settings-model option[value=""]').count(),0);
 await page.selectOption('#llm-settings-model',b);assert.equal(await page.inputValue(field('temperature')),'0.2');
 for(const arch of ['anima','sd','ming','qwen21']){const model=s.models.find(m=>m.architecture===arch);await page.selectOption('#image-settings-model',model.id);assert.match(await page.locator('#image-assistant-format').innerText(),['anima','sd'].includes(arch)?/tag in inglese separati da virgole/:/istruzioni descrittive in inglese/);}
 await page.selectOption('#image-settings-model',ia);
 await page.screenshot({path:new URL('../work/qa-v09/presets.png',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1')});
 assert.deepEqual(errors,[]);console.log('Per-model presets passed: edit inactive LLM without changing default, A/B restore, independent output limits and image presets retained after reload.');
}finally{await browser.close();}
