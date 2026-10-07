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
 await page.route('**/api/knowledge/embedding-default',route=>route.fulfill({json:{path:fixture.embeddinggemma2}}));
 const state=async()=>await (await page.request.get(fixture.url+'/api/state')).json();let original;
 await page.goto(fixture.url);await page.waitForFunction(()=>document.querySelector('#new-chat')&&!document.querySelector('#new-chat').disabled);original=(await state()).settings;
 await page.click('#settings-open');await page.click('[data-tab="advanced"]');
 assert.equal(await page.inputValue('[data-setting="rag_embedding_profile"]'),original.rag_embedding_profile);
 assert.equal(await page.locator('[data-setting="rag_embedding_profile"] option[value="embeddinggemma2"]').count(),1);
 let download;await page.route('**/api/downloads',async route=>{download=route.request().postDataJSON();await route.fulfill({json:{id:'embeddinggemma2'}});});
 await page.click('#rag-download-gemma2');await page.waitForFunction(()=>document.querySelector('#rag-download-gemma2')!==null);
 assert.deepEqual(download,{id:'embeddinggemma2',kind:'tool_model'});assert.equal((await state()).settings.rag_embedding_profile,original.rag_embedding_profile);
 await page.click('#rag-use-gemma2');await page.waitForFunction(()=>document.querySelector('[data-setting="rag_embedding_profile"]').value==='embeddinggemma2');
 assert.match(await page.inputValue('[data-setting="rag_embedding_model"]'),/EmbeddingGemma-2/);
 assert.equal((await state()).settings.rag_embedding_profile,original.rag_embedding_profile);
 const saved=page.waitForResponse(r=>r.url().endsWith('/settings')&&r.request().method()==='POST');await page.click('#settings-save');assert.equal((await saved).status(),200);await page.waitForFunction(()=>!document.querySelector('#settings').open);
 assert.equal((await state()).settings.rag_embedding_profile,'embeddinggemma2');
 await page.click('#new-project');await page.fill('#project-name','Gemma opzionale');await page.click('#project-save');await page.waitForFunction(()=>!document.querySelector('[data-project-rag-visual]').disabled);
 assert.match(await page.locator('[data-project-rag-note]').innerText(),/EmbeddingGemma 2/);assert.equal(await page.locator('[data-project-rag-visual]').isChecked(),true);
 await page.reload();await page.waitForFunction(()=>document.querySelector('#new-chat')&&!document.querySelector('#new-chat').disabled);assert.equal((await state()).settings.rag_embedding_profile,'embeddinggemma2');
 assert.deepEqual(errors,[]);console.log('EmbeddingGemma 2 option, explicit selection, unchanged default after download, saved path and multimodal project controls passed.');
}catch(error){console.error(diagnostic);throw error;}finally{await browser.close();child.kill();}
