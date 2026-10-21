import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import {build} from 'esbuild';
import assert from 'node:assert/strict';
const folder='work/video-fractional-range-qa';await mkdir(folder,{recursive:true});
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
await build({entryPoints:['tests/video-steps-browser-entry.js'],outfile:folder+'/harness.js',bundle:true,format:'iife',platform:'browser',target:'es2022'});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let logs='';child.stderr.on('data',x=>logs+=x);const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(logs);})]);lines.close();const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']}),page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[],posts=[];let saved=null;
page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&m.text().includes('not focusable'))errors.push(m.text());});
await page.exposeFunction('fractionalApi',async(path,body)=>{
 if(path.includes('video-import-progress'))return {updated_at:0};
 if(body){posts.push({path,body});if(path.includes('video-editor-draft')){saved={state:body.state,saved_at:Date.now()/1000,image_refs:[]};return saved;}return {job_id:'synthetic-only'};}
 return {source:'source',model_id:'model-a',imported:true,segment_seconds:10,draft_supported:true,editor_draft:saved,partial_edit:true,duration:20+25/24,images:[],
  models:[{id:'model-a',name:'Model A',parameters:{steps:12,megapixels:.7,attention:'sage'}}],
  clips:[0,1,2].map(n=>({clip:n+1,start:n*10,end:n===2?20+25/24:(n+1)*10,url:'/media/outputs/fixture.mp4',preview_start:0,prompt:'Original scene',images:[],lip_sync:false}))};
});
try{
 await page.goto(fixture.url);await page.route('**/static/fractional-test.js',async route=>route.fulfill({contentType:'application/javascript',body:await readFile(folder+'/harness.js','utf8')}));await page.addScriptTag({url:fixture.url+'/static/fractional-test.js'});
 await page.evaluate(()=>window.videoStepFixture.openVideoEdit({api:window.fractionalApi,chatId:'chat',source:'source',segmentSeconds:10,initialPrompt:'Change the jacket'}));
 let dialog=page.locator('.video-clip-dialog');const restore=dialog.locator('[data-restore-editor-draft]');
 assert(await restore.isDisabled());assert.match(await restore.getAttribute('title'),/Nessuna bozza salvata/);assert.equal(await restore.evaluate(e=>getComputedStyle(e).cursor),'not-allowed');
 const end=dialog.locator('#video-clip-editor-3 [data-end]');assert(await end.isDisabled());
 await dialog.locator('[data-select-all-clips]').click();assert(await dialog.locator('form').evaluate(e=>e.checkValidity()));
 await dialog.locator('[data-focus="3"]').click();await dialog.locator('#video-clip-editor-3 [data-part]').click();assert(!(await end.isDisabled()));assert.equal(Number(await end.inputValue()),25/24);assert(await end.evaluate(e=>e.validity.valid));
 await dialog.locator('[name="megapixels"]').fill('0.99');await dialog.locator('[type="submit"]').click();assert.equal(posts.length,0);assert(await dialog.locator('[data-error]').isVisible());assert.match(await dialog.locator('[data-error]').textContent(),/Controlla Risoluzione/);
 await dialog.locator('[name="megapixels"]').fill('0.7');await dialog.locator('[data-save-editor-draft]').click();await page.waitForFunction(()=>document.querySelector('[data-editor-draft-status]')?.textContent.startsWith('Bozza salvata'));assert.equal(saved.state.clips[2].last,25);assert(await restore.isEnabled());
 await dialog.locator('[data-restore-editor-draft]').click();await page.waitForFunction(()=>document.querySelectorAll('.video-clip-dialog').length===1&&!document.querySelector('[data-restore-editor-draft]').disabled);dialog=page.locator('.video-clip-dialog');assert.equal(Number(await dialog.locator('#video-clip-editor-3 [data-end]').inputValue()),25/24);assert(await dialog.locator('form').evaluate(e=>e.checkValidity()));
 await page.screenshot({path:folder+'/fractional-clip.png'});await dialog.locator('[type="submit"]').click();await dialog.waitFor({state:'detached'});
 assert.deepEqual(posts.map(p=>p.path),['/chats/chat/video-editor-draft/source','/chats/chat/video-editor-draft/source','/chats/chat/video-edit']);
 assert.equal(posts.at(-1).body.patches.length,3);assert.equal(posts.at(-1).body.patches[2].end,25/24);assert.equal(posts.at(-1).body.segment_seconds,10);assert.deepEqual(errors,[]);
 console.log('PASS: 10s imported segments with a 25-frame tail, exact whole/partial bounds, draft save/restore, explicit validation errors, generation request after save; no real generation.');
}finally{await browser.close();child.kill();}
