import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const folder='work/dialog-layout-2026-11-03';await mkdir(folder,{recursive:true});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_study_fixture.py'],{stdio:['ignore','pipe','pipe'],env:process.env});let logs='';child.stderr.on('data',x=>logs+=x);const lines=createInterface({input:child.stdout});const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(logs);})]);lines.close();const fixture=JSON.parse(line);let browser;
try{
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(fixture.url);await page.click(`[data-chat="${fixture.chat}"]`);await page.click('#prompt-study');await page.click('[data-mode-settings="study-options"]');const dialog=page.locator('#prompt-mode-settings');
 const geometry=()=>dialog.evaluate(d=>{const r=d.getBoundingClientRect(),footer=d.querySelector('footer').getBoundingClientRect(),body=d.querySelector('.prompt-options-body').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,windowWidth:innerWidth,windowHeight:innerHeight,footerBottom:footer.bottom,bodyBottom:body.bottom,scroll:d.scrollWidth<=d.clientWidth+1};});
 const desktop=await geometry();assert.ok(desktop.width>=desktop.windowWidth*2/3);assert.ok(desktop.height>=desktop.windowHeight*2/3);assert.ok(desktop.footerBottom<=desktop.y+desktop.height);assert.ok(desktop.scroll);
 const fields=await dialog.locator('[data-study]').evaluateAll(fields=>fields.map(e=>({key:e.dataset.study,rect:e.getBoundingClientRect().toJSON(),font:getComputedStyle(e).fontSize,padding:getComputedStyle(e).padding,border:getComputedStyle(e).borderRadius})));
 const top=fields.filter(e=>['kind','count','level'].includes(e.key));assert.ok(top.every(e=>Math.abs(e.rect.y-top[0].rect.y)<1),'Main fields share one desktop row');assert.ok(fields.every(e=>parseFloat(e.font)>=13));assert.ok(fields.find(e=>e.key==='source_text').rect.width>desktop.width*.85);assert.ok(fields.find(e=>e.key==='source_text').rect.height>=200);
 assert.equal(await dialog.locator('.study-settings-voices').isVisible(),false);await dialog.locator('[data-study=kind]').selectOption('dialogue');assert.equal(await dialog.locator('.study-settings-voices').isVisible(),true);await dialog.locator('[data-study=kind]').selectOption('flashcards');
 await page.screenshot({path:folder+'/studio-desktop.png'});await dialog.locator('footer .primary').click();
 await page.click('#settings-open');await page.locator('#settings[open]').waitFor();await page.screenshot({path:folder+'/preferences-desktop.png'});await page.click('#settings-close');
 // Audit each existing native dialog's geometry without invoking its action.
 const inventory=await page.evaluate(()=>{const out=[];for(const d of document.querySelectorAll('dialog')){if(d.open)d.close();if(!d.isConnected)continue;d.showModal();const r=d.getBoundingClientRect();out.push({id:d.id,cls:d.className,width:r.width,height:r.height,scroll:d.scrollWidth>d.clientWidth+1});d.close();}return out;});
 assert.ok(inventory.length>=6);for(const d of inventory){assert.ok(d.width>=1000,d.id+' width '+d.width);assert.ok(d.height>=666,d.id+' height '+d.height);}
 await page.click('[data-mode-settings="study-options"]');await page.setViewportSize({width:390,height:844});const mobile=await geometry();assert.ok(mobile.width<=390&&mobile.x>=0);assert.ok(mobile.height<=844&&mobile.y>=0);assert.ok(mobile.scroll);assert.ok(mobile.footerBottom<=mobile.y+mobile.height+1);
 const controls=await dialog.locator('[data-study]').evaluateAll(fields=>fields.map(e=>({key:e.dataset.study,r:e.getBoundingClientRect().toJSON()})));assert.ok(controls.every(e=>e.r.x>=0&&e.r.right<=390));assert.ok(controls[1].r.y>controls[0].r.y,'Fields stack on phones');await page.screenshot({path:folder+'/studio-mobile.png'});
 await dialog.locator('[data-study=source_text]').fill('Testo preservato');await dialog.locator('footer .primary').click();await page.click('[data-mode-settings="study-options"]');assert.equal(await dialog.locator('[data-study=source_text]').inputValue(),'Testo preservato');assert.deepEqual(errors,[]);
 const report={passed:true,desktop,mobile,inventory,shared_form_controls:true,study_grid:true,voices_conditional:true,values_preserved:true,production_jobs:0};await writeFile(folder+'/verification.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}catch(error){console.error(logs);throw error;}finally{await browser?.close();child.kill();}
