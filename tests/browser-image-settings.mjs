import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const config=JSON.parse(await readFile(new URL('../work/qa-v06-config.json',import.meta.url),'utf8'));
const output=new URL('../work/qa-v06-ui/',import.meta.url);await mkdir(output,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
const api=async(path,body)=>page.evaluate(async({path,body})=>{
 const state=await (await fetch('/api/state')).json();
 const response=await fetch('/api'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':state.token},body:JSON.stringify(body)});
 const value=await response.json();if(!response.ok)throw Error(JSON.stringify(value));return value;
},{path,body});
const shot=async name=>page.screenshot({path:new URL(name+'.png',output).pathname.replace(/^\/([A-Za-z]:)/,'$1')});
try{
 await page.goto(process.env.H3_TEST_URL||'http://127.0.0.1:8788');await page.waitForFunction(()=>document.querySelector('#think-note').textContent.length>0);
 await api('/settings',{image_advanced:false,chat_advanced:false,image_overrides:{},lora_dirs:[]});await page.evaluate(()=>localStorage.clear());await page.reload();await page.waitForFunction(()=>document.querySelector('#think-note').textContent.length>0);
 await page.click('#settings-open');await page.click('[data-tab="advanced"]');
 await page.selectOption('#image-settings-model',config.anima);
 assert.equal(await page.isChecked('#image-advanced'),false);assert.equal(await page.isVisible('#image-advanced-fields'),false);
 assert.match(await page.locator('.image-preset-summary').innerText(),/8 step · CFG 1/);await shot('preferences-defaults');
 await page.check('#image-advanced');await page.fill('[data-image-setting="steps"]','10');await page.fill('[data-image-setting="width"]','768');
 await page.selectOption('[data-image-setting="sampler"]','euler');await page.selectOption('[data-image-setting="scheduler"]','simple');
 await page.fill('[data-image-setting="seed"]','456');await page.fill('[data-image-setting="negative_prompt"]','sfocato');
 await page.selectOption('#image-settings-model','');assert.equal(await page.inputValue('#image-settings-model'),'');
 assert.equal(await page.inputValue('[data-image-setting="steps"]'),'20');await page.selectOption('#image-settings-model',config.anima);
 assert.equal(await page.inputValue('[data-image-setting="steps"]'),'10');await shot('preferences-advanced');
 await page.uncheck('#image-advanced');
 for(const dir of config.dirs){
  await page.click('#lora-add-directory');await page.fill('#model-browser-path',dir);await page.click('#model-browser-address button');
  await page.waitForFunction(()=>!document.querySelector('#model-browser-choose-directory').disabled);
  await page.click('#model-browser-choose-directory');
 }
 assert.equal(await page.locator('[data-lora-dir]').count(),2);await page.click('#settings-save');await page.waitForSelector('#settings',{state:'hidden'});
 let state=await api('/state');assert.equal(state.settings.image_advanced,false);assert.equal(state.settings.image_overrides[config.anima].steps,10);assert.deepEqual(state.settings.lora_dirs,config.dirs);
 await page.locator(`[data-chat="${config.chat}"]`).click();
 assert.equal(await page.locator('.image-parameters').count(),0);
 await page.check('#chat-advanced');await page.waitForSelector('.image-parameters');await page.click('.image-parameters summary');
 assert.match(await page.locator('.image-parameters').innerText(),/Seed 12345/);await shot('chat-details');
 await page.click('#lora-open');await page.waitForSelector('[data-lora-id]');
 assert.equal(await page.locator('[data-lora-id]:disabled').count(),1);
 const enabled=page.locator('[data-lora-id]:enabled');await enabled.nth(0).check();await enabled.nth(1).check();
 await page.selectOption('#lora-target',config.flux);await page.locator('[data-lora-id]:enabled:not(:checked)').check();await page.click('#lora-close');
 assert.equal(await page.locator('.lora-chip').count(),3);
 const weight=page.locator('[data-lora-weight="0"]');await weight.fill('.6');
 await page.waitForTimeout(4000);assert.equal(await weight.inputValue(),'.6');await weight.press('Tab');
 await shot('chat-loras');
 await page.reload();await page.waitForFunction(()=>document.querySelector('#think-note').textContent.length>0);await page.locator(`[data-chat="${config.chat}"]`).click();
 await page.waitForFunction(()=>document.querySelectorAll('.lora-chip').length===3);assert.equal(await page.locator('.lora-chip').count(),3);assert.equal(Number(await page.locator('[data-lora-weight="0"]').inputValue()),.6);
 assert.equal(await page.isChecked('#chat-advanced'),true);
 await page.click('#new-chat');await page.waitForFunction(()=>document.querySelectorAll('.lora-chip').length===0);assert.equal(await page.locator('.lora-chip').count(),0);await page.locator(`[data-chat="${config.chat}"]`).click();await page.waitForFunction(()=>document.querySelectorAll('.lora-chip').length===3);assert.equal(await page.locator('.lora-chip').count(),3);
 await page.uncheck('#chat-advanced');await page.waitForSelector('.image-parameters',{state:'detached'});
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(200);await shot('mobile');
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.click('#lora-open');await page.waitForSelector('[data-lora-id]');await shot('mobile-loras');assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.deepEqual(errors,[]);await writeFile(new URL('result.json',output),JSON.stringify({passed:true,errors,checks:['default presets','advanced visibility and persistence','model overrides','two external LoRA folders','three LoRAs across two targets','weight editing during polling','per-chat persistence','chat generation details','mobile 390px']},null,2));
 console.log('Preferenze, preset, LoRA, dettagli chat e mobile OK');
}finally{await browser.close();}
