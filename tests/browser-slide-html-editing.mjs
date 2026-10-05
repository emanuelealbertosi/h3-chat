import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});
let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);
const lines=createInterface({input:child.stdout}),timer=setTimeout(()=>child.kill(),30000);
const first=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);clearTimeout(timer);
const fixture=JSON.parse(first[0]);lines.close();
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1640,height:1100}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
const iframe=()=>page.frameLocator('.h3-html-page iframe');
const status=()=>page.locator('#slide-html-status').textContent();
const snapshot=()=>iframe().locator('body').evaluate(body=>{const clone=body.cloneNode(true);clone.querySelectorAll('[data-h3-editor]').forEach(e=>e.remove());return clone.innerHTML;});
async function projectedRect(selector){
 const outer=await page.locator('.h3-html-page iframe').boundingBox(),inner=await iframe().locator(selector).evaluate(e=>e.getBoundingClientRect().toJSON()),scale=outer.width/1280;
 return {x:outer.x+inner.x*scale,y:outer.y+inner.y*scale,width:inner.width*scale,height:inner.height*scale};
}
async function handle(action,dx,dy){
 const selector=`[data-h3-editor] [data-action="${action}"]`;await iframe().locator(selector).scrollIntoViewIfNeeded();const r=await projectedRect(selector);
 await page.mouse.move(r.x+r.width/2,r.y+r.height/2);await page.mouse.down();await page.mouse.move(r.x+r.width/2+dx,r.y+r.height/2+dy,{steps:5});await page.mouse.up();
}
try{
 await mkdir('work/slide-html-editing-qa',{recursive:true});await page.goto(fixture.url);await page.click(`[data-chat="${fixture.chat}"]`);
 await page.evaluate(async()=>{const {token}=await(await fetch('/api/state')).json();const r=await fetch('/fixture/slides/html',{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':token},body:'{}'});if(!r.ok)throw Error(await r.text());});
 await page.click('#canvas-toggle');await iframe().locator('h1').waitFor();await page.click('#slide-edit');
 assert.equal(await iframe().locator('[data-h3-layout]').count(),0,'Free model HTML must keep its layout by default');
 const paragraph=iframe().locator('main>p');await paragraph.click();const initial=await paragraph.evaluate(e=>e.getBoundingClientRect().width);
 await handle('resize',30,10);assert.ok(await paragraph.evaluate(e=>e.getBoundingClientRect().width)>initial,'Resize handle must change size');
 const resized=await snapshot();await handle('move',15,5);assert.match(await paragraph.getAttribute('style'),/--h3-dx/);
 await page.click('#slide-html-undo');assert.equal(await snapshot(),resized);await page.click('#slide-html-redo');assert.notEqual(await snapshot(),resized);
 await paragraph.click();await page.click('#slide-html-parent');assert.match(await page.locator('#slide-html-selection').textContent(),/gruppo/);
 await page.selectOption('#slide-html-layout','columns-2');await page.click('#slide-html-arrange');assert.equal(await status(),'Modifiche da salvare');
 assert.equal(await iframe().locator('[data-h3-root]').getAttribute('data-h3-layout'),'columns-2');
 await page.click('#slide-html-block');assert.equal(await status(),'Modifiche da salvare');
 await page.click('#slide-html-add');assert.equal(await status(),'Modifiche da salvare');
 await page.click('#slide-html-properties summary');await page.fill('#slide-html-text','Un nuovo blocco modificabile');
 await page.click('#slide-html-properties summary');await page.click('#slide-html-parent');await page.selectOption('#slide-html-scope','group');
 await page.selectOption('#slide-html-layout','columns-2');await page.click('#slide-html-arrange');assert.equal(await status(),'Modifiche da salvare');
 const block=iframe().locator('section[data-h3-layout]');assert.equal(await block.getAttribute('data-h3-layout'),'columns-2');
 const beforeReorder=await block.evaluate(e=>e.previousElementSibling?.tagName);await page.click('#slide-html-previous');
 assert.notEqual(await block.evaluate(e=>e.previousElementSibling?.tagName),beforeReorder);
 await page.locator('.slides-viewport').scrollIntoViewIfNeeded();
 await iframe().locator('[data-action="move"]').scrollIntoViewIfNeeded();await page.waitForTimeout(300);const move=await projectedRect('[data-action="move"]'),destination=await projectedRect('[data-h3-root]>svg');
 const beforeDrag=await block.evaluate(e=>[...e.parentElement.children].map(e=>e.tagName).join(','));
 await page.mouse.move(move.x+move.width/2,move.y+move.height/2);await page.mouse.down();await page.mouse.move(destination.x+destination.width*.5,destination.y+destination.height*.6,{steps:6});await page.mouse.up();
 assert.notEqual(await block.evaluate(e=>[...e.parentElement.children].map(e=>e.tagName).join(',')),beforeDrag,'Dragging in an automatic grid must reorder blocks');
 await iframe().locator('section h3').click();await page.click('#slide-html-copy');assert.equal(await iframe().locator('section h3').count(),2);
 await page.click('#slide-html-delete');assert.equal(await iframe().locator('section h3').count(),1);
 await page.click('#slide-html-images summary');
 const png=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=80;c.height=60;return c.toDataURL().split(',')[1];});
 await page.locator('[data-file]').setInputFiles({name:'blocco.png',mimeType:'image/png',buffer:Buffer.from(png,'base64')});
 await page.waitForFunction(()=>document.querySelector('#slide-html-status')?.textContent.includes('inserita'));
 await page.click('#slide-html-images summary');
 const geometry=await iframe().locator('[data-h3-root]').evaluate(root=>[...root.querySelectorAll('main,main>p,main>img,[data-h3-root]>svg')].map(e=>({tag:e.tagName,rect:e.getBoundingClientRect().toJSON(),width:e.style.width,translate:e.style.translate})));
 const main=geometry.find(e=>e.tag==='MAIN').rect;
 for(const child of geometry.filter(e=>e.tag==='P'||e.tag==='IMG')){assert.ok(child.rect.left>=main.left-1&&child.rect.right<=main.right+1,'Nested content must stay within its column');assert.ok(child.rect.width>0);}
 await page.locator('.slides-viewport').screenshot({path:'work/slide-html-editing-qa/automatic-layout.png'});
 await page.click('#slide-html-save');await page.waitForFunction(()=>document.querySelector('#canvas-save-status')?.textContent.includes('Salvato'));
 const saved=await page.evaluate(async chat=>await(await fetch('/api/canvas/'+chat)).json(),fixture.chat);
 assert.match(saved.content,/Un nuovo blocco modificabile/);assert.match(saved.content,/data-h3-layout/);assert.ok(saved.media.some(m=>m.name==='blocco.png'));
 assert.ok(!saved.content.includes('data-h3-editor'),'Editing handles must not be saved or exported');
 await page.locator('.slides-viewport').screenshot({path:'work/slide-html-editing-qa/saved-layout.png'});
 await page.reload();await page.click(`[data-chat="${fixture.chat}"]`);await page.click('#canvas-toggle');await iframe().locator('[data-h3-root]').waitFor();
 assert.equal(await iframe().locator('[data-h3-root]').getAttribute('data-h3-layout'),'columns-2');
 assert.match(await iframe().locator('section').textContent(),/Un nuovo blocco modificabile/);
 await page.click('#slide-edit');await iframe().locator('section h3').click();await page.click('#slide-html-parent');
 await page.selectOption('#slide-html-scope','group');await page.selectOption('#slide-html-layout','free');await page.click('#slide-html-arrange');
 assert.equal(await iframe().locator('section').getAttribute('data-h3-layout'),'free');
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(350);
 const overflow=await page.locator('.slide-html-editor').evaluate(e=>e.scrollWidth>e.clientWidth+1);assert.equal(overflow,false);
 assert.deepEqual(errors,[]);console.log('Free HTML editing: group selection, resizing, dragging, undo/redo, insertion, automatic columns, reordering, images, persistence and mobile passed.');
}catch(e){console.error(diagnostics);await page.screenshot({path:'work/slide-html-editing-qa/error.png',fullPage:true});console.error('Editor:',await status().catch(()=>''));throw e;}finally{await browser.close();child.kill();}
