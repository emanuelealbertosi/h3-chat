import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdir} from 'node:fs/promises';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
const base=process.env.H3_TEST_URL||'http://127.0.0.1:8789';
try{
 await page.goto(base);await page.waitForFunction(()=>document.querySelector('#generation-settings').textContent.includes('Contesto'));
 const initial=await (await page.request.get(base+'/api/state')).json();
 const model=initial.models.find(m=>m.id===initial.settings.chat_model&&m.parameters?.context_length>=262144)||initial.models.find(m=>m.parameters?.context_length>=262144);assert.ok(model,'Connect a GGUF declaring at least 256k in the isolated test database.');
 const open=async()=>{await page.click('#settings-open');await page.click('[data-tab="advanced"]');await page.selectOption('#llm-settings-model',model.id);};
 await page.click('#settings-open');await page.selectOption('[data-setting="chat_model"]',model.id);await page.click('[data-tab="advanced"]');await page.selectOption('#llm-settings-model',model.id);
 const saved=[];
 for(const size of [65536,131072,262144]){
  assert.match(await page.locator('#context-model-note').innerText(),/262.144/);
  await page.fill('[data-setting="context"]',String(size));await page.locator('[data-setting="context"]').blur();
  assert.equal(await page.locator('[data-setting="context"]').evaluate(e=>e.validity.valid),true);
  assert.equal(await page.locator('#context-presets option[value="65536"]').count(),1);
  const result=page.waitForResponse(r=>r.url().endsWith('/api/settings'));
  await page.click('#settings-save');const response=await result;assert.equal(response.status(),200);saved.push(await response.json());
  await page.waitForFunction(()=>!document.querySelector('#settings').open);
  await page.waitForFunction(value=>document.querySelector('#generation-settings').textContent.includes(Number(value).toLocaleString('it-IT')),size);
  await open();assert.equal(await page.inputValue('[data-setting="context"]'),String(size));
 }
 for(const s of saved){assert.equal(s.max_tokens,initial.settings.max_tokens);assert.equal(s.prompt_max_tokens,initial.settings.prompt_max_tokens);}
 await page.fill('[data-setting="context"]','524288');await page.locator('[data-setting="context"]').blur();
 assert.match(await page.locator('#context-model-note').innerText(),/supera il contesto dichiarato/);
 await page.fill('[data-setting="context"]','65536');await page.locator('[data-setting="context"]').blur();
 await page.waitForFunction(()=>document.querySelector('#memory-assessment').innerText.includes('contesto LLM 65536'));
 assert.ok((await page.locator('#memory-assessment').innerText()).includes('Stime per'));
 await mkdir(new URL('../work/qa-v082-ui/',import.meta.url),{recursive:true});
 await page.screenshot({path:new URL('../work/qa-v082-ui/context-64k.png',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1')});
 await page.click('#settings-save');await page.waitForFunction(()=>!document.querySelector('#settings').open);
 const assess=async context=>{const r=await page.request.post(base+'/api/assess',{headers:{'X-H3-Token':initial.token},data:{settings:{context},references:1}});assert.equal(r.status(),200);return (await r.json()).models.find(m=>m.role==='chat_model');};
 const small=await assess(16384),large=await assess(65536);assert.ok(large.ram_gb+large.vram_gb>small.ram_gb+small.vram_gb);
 const unknown=initial.models.find(m=>m.capabilities.includes('chat')&&!m.parameters?.context_length);
 if(unknown){await page.click('#settings-open');await page.selectOption('[data-setting="chat_model"]',unknown.id);await page.click('[data-tab="advanced"]');await page.selectOption('#llm-settings-model',unknown.id);assert.match(await page.locator('#context-model-note').innerText(),/non rilevato/);await page.click('#settings-close');}
 assert.deepEqual(errors,[]);console.log('Context UI passed: 64k/128k/256k save and reopen; GGUF context, larger-context warning, unknown metadata, output limits preserved and memory growth.');
}finally{await browser.close();}
