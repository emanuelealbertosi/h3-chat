// Disposable API fixture only. Downloads are intercepted; no weights or GPU jobs.
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const out='work/settings-center-qa';await mkdir(out,{recursive:true});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_study_fixture.py'],{stdio:['ignore','pipe','pipe'],env:process.env});let logs='';child.stderr.on('data',x=>logs+=x);
const lines=createInterface({input:child.stdout});const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(logs);})]);lines.close();const fixture=JSON.parse(line);let browser,page;const errors=[];
try{
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});page=await browser.newPage({viewport:{width:1440,height:900}});const downloads=[];let mockTasks=[];let saved=null;
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/state',async route=>{const response=await route.fetch(),state=await response.json();state.downloads=mockTasks;await route.fulfill({json:state});});
 await page.route('**/api/downloads/*/cancel',route=>{mockTasks=mockTasks.map(t=>({...t,status:'cancelled'}));return route.fulfill({json:{ok:true}});});
 await page.route('**/api/downloads',route=>{downloads.push(route.request().postDataJSON());mockTasks=[{...downloads.at(-1),status:'running',file:'models/sample.gguf',received:500,total:1000}];return route.fulfill({json:{id:downloads.at(-1).id},status:202});});
 await page.route('**/api/hardware',route=>route.fulfill({json:{cpu_name:'Test CPU',cpu_threads:8,ram:{total_mb:16384,free_mb:12000},gpu:[]}}));
 await page.route('**/api/settings',async route=>{saved=route.request().postDataJSON();const response=await route.fetch();await route.fulfill({response});});
 await page.goto(fixture.url);await page.waitForSelector(`[data-chat="${fixture.chat}"]`);await page.click('#settings-open');const dialog=page.locator('#settings');
 await page.click('[data-tab="providers"]');await page.selectOption('[data-api="preset"]','heabsy');assert.equal(await page.inputValue('[data-api="base_url"]'),'https://api.heabsy.com/v1');assert.equal(await page.inputValue('[data-api="api_key"]'),'');assert.equal(await page.locator('[data-api="api_key"]').getAttribute('type'),'password');await page.click('[data-tab="setup"]');await dialog.getByRole('button',{name:'2 · Il tuo computer',exact:true}).click();await page.locator('[data-setup-hardware-apply]:enabled').waitFor();await page.click('[data-setup-hardware-apply]');
 assert.equal(await page.inputValue('[data-setting="backend"]'),'cpu');assert.equal(await page.inputValue('[data-setting="profile"]'),'cpu');
 await page.screenshot({path:out+'/setup.png'});
 // Contextual installation links must navigate, not start a download.
 await page.click('#install-runtime');assert.equal(downloads.length,0);assert.equal(await page.inputValue('[data-install-view]'),'runtime');
 const inventory=await page.locator('[data-center-install]').evaluateAll(bs=>bs.map(b=>({id:b.dataset.centerInstall,kind:b.dataset.centerKind})));
 assert.ok(inventory.some(x=>x.id==='tools_asr'&&x.kind==='runtime'));assert.ok(inventory.some(x=>x.id==='embeddinggemma'&&x.kind==='tool_model'));
 await page.locator('[data-install-search]').fill('LaTeX');assert.equal(await page.locator('.installation-list>.model-card:visible').count(),1);
 await page.screenshot({path:out+'/installations.png'});
 await page.locator('[data-install-search]').fill('');const install=page.locator('[data-center-kind="runtime"]:enabled').first(),runtimeId=await install.getAttribute('data-center-install');await page.locator('[data-install-search]').fill('');await install.click();assert.deepEqual(downloads.at(-1),{id:runtimeId,kind:'runtime'});await page.selectOption('[data-install-view]','downloads');await page.locator('.installation-queue [data-cancel-download]').click();await page.waitForFunction(()=>document.querySelector('.installation-queue')?.textContent.includes('Interrotto'));
 await page.locator('[data-install-search]').fill('');await page.selectOption('[data-install-view]','tool_model');assert.ok(await page.locator('.installation-list>.model-card:visible').count()>=5);
 await page.locator('[data-center-install="embeddinggemma"][data-center-kind="tool_model"]').click();assert.deepEqual(downloads.at(-1),{id:'embeddinggemma',kind:'tool_model'});await page.selectOption('[data-install-view]','downloads');await page.locator('.installation-queue progress:visible').waitFor();assert.equal(await page.locator('.installation-queue progress').getAttribute('value'),'500');await page.locator('.installation-queue [data-cancel-download]').click();await page.waitForFunction(()=>document.querySelector('.installation-queue')?.textContent.includes('Interrotto'));
 await page.selectOption('[data-install-view]','models');const card=page.locator('.installation-list>.model-card:visible').first();const beforeChecks=downloads.length;await card.getByRole('button',{name:'Controlla compatibilità con questo PC',exact:true}).click();await page.waitForFunction(()=>[...document.querySelectorAll('.installation-list [role="status"]')].some(e=>e.textContent.includes('RAM stimata:')));assert.equal(downloads.length,beforeChecks);
 await page.click('[data-tab="advanced"]');
 const nav=dialog.locator('#settings-body>.settings-page-layout>.settings-page-nav');assert.ok(await nav.locator('button').count()>=10);
 await nav.getByRole('button',{name:'Istruzioni personali',exact:true}).click();await page.locator('[data-setting="system_prompt"]').fill('Bozza da conservare tra tutte le sezioni.');
 await nav.getByRole('button',{name:'Immagini e LoRA',exact:true}).click();assert.equal(await page.locator('#settings-body>.settings-page-layout>.settings-page-content>.settings-page:visible').count(),1);
 await page.screenshot({path:out+'/preferences.png'});
 await page.click('[data-tab="models"]');await page.click('[data-tab="advanced"]');await nav.getByRole('button',{name:'Istruzioni personali',exact:true}).click();assert.equal(await page.inputValue('[data-setting="system_prompt"]'),'Bozza da conservare tra tutte le sezioni.');
 // A hidden preference must survive saving from a different page.
 await nav.getByRole('button',{name:'Computer e memoria',exact:true}).click();
 const geometric=async()=>dialog.evaluate(d=>{const r=d.getBoundingClientRect(),f=d.querySelector('footer').getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,footer:f.bottom,overflow:d.scrollWidth>d.clientWidth+2,window:innerHeight};});
 const desktop=await geometric();assert.ok(desktop.footer<=desktop.window);assert.equal(desktop.overflow,false);
 await page.setViewportSize({width:390,height:760});const mobile=await geometric();assert.ok(mobile.x>=0&&mobile.w<=390);assert.ok(mobile.footer<=760);assert.equal(mobile.overflow,false);await page.screenshot({path:out+'/mobile.png'});
 await page.click('#settings-save');await page.waitForFunction(()=>!document.querySelector('#settings').open);assert.equal(saved.system_prompt,'Bozza da conservare tra tutte le sezioni.');assert.equal(saved.backend,'cpu');
 await page.click('#prompt-agent');await page.click('[data-mode-settings=agent-options]');const agent=page.locator('#agent-preferences');await agent.locator('.settings-page-nav').getByRole('button',{name:'Web e autorizzazioni',exact:true}).click();assert.ok(await agent.locator('[data-agent=confirm_writes]').isVisible());await agent.locator('.settings-page-nav').getByRole('button',{name:'Budget e tempi',exact:true}).click();assert.ok(await agent.locator('[data-agent=token_budget]').isVisible());await page.screenshot({path:out+'/agent-settings.png'});await agent.locator('[data-agent-close]').click();
 await page.setViewportSize({width:1440,height:900});await page.click('#prompt-slides');await page.click('[data-mode-settings="slides-options"]');
 const mode=page.locator('#prompt-mode-settings'),modeNav=page.locator('#slides-options>.settings-page-layout>.settings-page-nav');
 assert.ok(await modeNav.locator('button').count()>=3);await modeNav.getByRole('button',{name:'Generale',exact:true}).click();await page.fill('#slides-count','17');
 await modeNav.getByRole('button',{name:'Sfondi',exact:true}).click();assert.equal(await page.inputValue('#slides-count'),'17');assert.ok(await mode.locator('[data-presentation-presets="slides"] [data-save]').isVisible());
 await page.screenshot({path:out+'/slide-settings.png'});await modeNav.getByRole('button',{name:'Generale',exact:true}).click();assert.equal(await page.inputValue('#slides-count'),'17');await mode.locator('footer .primary').click();
 assert.deepEqual(errors,[]);const report={passed:true,hardware_cpu_suggestion:true,central_runtime_and_rag_inventory:inventory,contextual_links_do_not_download:true,explicit_downloads:downloads,unsaved_values_preserved:true,one_active_topic:true,desktop,mobile,production_jobs:0,real_downloads:0};await writeFile(out+'/verification.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}catch(error){console.error(logs,errors,await page?.locator('#toast').innerText().catch(()=>''));await page?.screenshot({path:out+'/failure.png'}).catch(()=>{});console.error((await page?.locator('#settings-body').innerHTML().catch(()=>''))?.slice(0,1800));throw error;}finally{await browser?.close();child.kill();}
