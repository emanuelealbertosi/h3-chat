import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});
let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);
const lines=createInterface({input:child.stdout}),first=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);
const fixture=JSON.parse(first[0]);lines.close();
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']}).catch(error=>{child.kill();throw error;}),page=await browser.newPage({viewport:{width:1360,height:1000}}),errors=[];
page.on('pageerror',error=>errors.push(error.message));
let posted=null,snapshot=null;
try{
 await page.route('**/api/state',async route=>{
  const response=await route.fetch(),state=await response.json();
  state.models.push({id:'api-only-qa',name:'Fake external LLM',api:true,ready:true,complete:true,files:[],size:0,capabilities:['chat'],vision:{enabled:false,expected:false},thinking:{supported:false},identity:{label:'Fake external LLM'}});
  state.models.push({id:'remote-image-qa',name:'Fake remote images',remote_media:true,ready:true,complete:true,files:[],size:0,capabilities:['create','edit'],architecture:'remote-image'});
  if(posted)Object.assign(state.settings,posted);snapshot=state;await route.fulfill({json:state});
 });
 await page.route('**/api/assess',route=>route.fulfill({json:{hardware:{cpu_name:'No GPU fixture',cpu_threads:4,ram:{total_mb:8192,free_mb:6144},gpu:[],note:'Fixture'},references:1,overall:{status:'ok',note:'API simulation',title:'Server esterni',unique_models:2,advice:'Nessun peso locale',ram_gb:0,vram_gb:0},models:[],memory:{models:[]}}}));
 await page.route('**/api/settings',route=>{posted=route.request().postDataJSON();return route.fulfill({json:{...snapshot.settings,...posted}});});
 await page.goto(fixture.url);await page.waitForSelector(`[data-chat="${fixture.chat}"]`);await page.click('#settings-open');await page.click('#setup-api-only');
 assert.equal(await page.inputValue('[data-setting="profile"]'),'cpu');assert.equal(await page.inputValue('[data-setting="backend"]'),'cpu');
 assert.equal(await page.inputValue('[data-setting="chat_model"]'),'api-only-qa');assert.equal(await page.inputValue('[data-setting="create_model"]'),'remote-image-qa');
 assert.match(await page.locator('.api-only-setup').innerText(),/RAG resta locale su CPU/);
 await page.click('#setup-api-providers');assert.equal(await page.locator('[data-tab="providers"]').getAttribute('class'),'active');
 await page.click('[data-tab="setup"]');assert.equal(await page.inputValue('[data-setting="chat_model"]'),'api-only-qa');
 await page.setViewportSize({width:390,height:844});assert.equal(await page.locator('.api-only-setup').evaluate(element=>element.scrollWidth>element.clientWidth+2),false);
 await page.click('#settings-save');await page.waitForFunction(()=>!document.querySelector('#settings').open);
 assert.equal(posted.rag_device,'cpu');assert.equal(posted.llm_device,'cpu');assert.equal(posted.image_device,'cpu');assert.equal(posted.music_model,'');assert.equal(posted.video_model,'');assert.equal(posted.transcribe_auto,false);assert.equal(posted.voice_auto,false);assert.equal(posted.setup_done,true);
 assert.deepEqual(errors,[]);console.log('API-only setup passed: external defaults, CPU RAG, provider navigation, saved values, mobile layout. Fake providers; GPU disabled.');
}catch(error){console.error(diagnostics,errors,await page.locator('#toast').innerText().catch(()=>''));throw error;}finally{await browser.close();child.kill();}
