import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const base=process.env.H3_TEST_URL||'http://127.0.0.1:8788';
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage(),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 const live=await (await page.request.get(base+'/api/state')).json();
 let old=true,reads=0;
 await page.route('**/api/state',async route=>{
  reads++;const response=await route.fetch(),state=await response.json();
  if(old){delete state.llm_options;state.version='0.8.0';}
  await route.fulfill({response,json:state});
 });
 await page.goto(base);await page.waitForFunction(()=>document.querySelector('#generation-settings').textContent.includes('Contesto'));
 await page.click('#settings-open');await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('motore precedente'));
 assert.equal(await page.locator('#settings').evaluate(d=>d.open),false);
 assert.doesNotMatch(await page.locator('#toast').innerText(),/undefined|reading/);
 old=false;const before=reads;
 await page.click('#settings-open');await page.waitForFunction(()=>document.querySelector('#settings').open);
 assert.ok(reads>before,'Opening settings refreshes the server state');
 await page.click('[data-tab="advanced"]');await page.waitForSelector('#llm-settings-model');
 assert.equal(await page.inputValue('[data-llm-setting="context"]'),String(live.settings.context));
 assert.deepEqual(errors,[]);
 console.log('Settings version regression passed: old engine explained without crashing; updated engine recovered on the same page without changing saved settings.');
}finally{await browser.close();}
