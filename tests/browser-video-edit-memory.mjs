import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import {build} from 'esbuild';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
await mkdir('work/video-edit-memory-qa',{recursive:true});
await build({entryPoints:['tests/video-steps-browser-entry.js'],outfile:'work/video-edit-memory-qa/harness.js',bundle:true,format:'iife',platform:'browser',target:'es2022'});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe'],env:{...process.env,H3_TIMELINE_PREVIEW_FIXTURE:'1'}});
let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);lines.close();
const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']});
const page=await browser.newPage({viewport:{width:1350,height:1000}}),errors=[],writes=[];let saved=null;
page.on('pageerror',e=>errors.push(e.message));
await page.exposeFunction('memoryApi',async({path,body,method})=>{
 if(body){
  writes.push({path,body});
  if(path.includes('video-editor-draft')){
   if(method==='DELETE'){saved=null;return {ok:true};}
   saved={version:1,saved_at:Date.now()/1000,state:structuredClone(body.state),image_refs:[]};return saved;
  }
  return {job_id:'synthetic'};
 }
 return {model_id:'m',models:[{id:'m',name:'Synthetic H3',parameters:{steps:12,megapixels:.7,attention:'veda'}}],
  memory_recovery:true,end_frame_recovery:true,draft_supported:true,editor_draft:saved,partial_edit:true,images:[],duration:6,
  clips:[1,2,3].map(n=>({clip:n,start:(n-1)*2,end:n*2,url:'/media/outputs/preview-source.mp4',preview_start:0,prompt:'Original',images:[],
   memory:{available:n>1,default:n===2,cut:n!==2}}))};
});
const open=()=>page.evaluate(()=>window.videoStepFixture.openVideoEdit({chatId:'owned-chat',source:'owned-video',
 api:(path,body,method)=>window.memoryApi({path,body,method})}));
try{
 await page.goto(fixture.url);await page.route('**/static/memory-test.js',async route=>route.fulfill({contentType:'application/javascript',body:await readFile('work/video-edit-memory-qa/harness.js','utf8')}));
 await page.addScriptTag({url:fixture.url+'/static/memory-test.js'});
 await open();let dialog=page.locator('.video-clip-dialog');
 await dialog.locator('[data-focus="1"]').click();let first=dialog.locator('#video-clip-editor-1');
 await first.locator('[data-reference-mode]').click();assert(await first.locator('[data-recover-memory]').isDisabled());
 await dialog.locator('[data-clear-clips]').click();await dialog.locator('[data-focus="2"]').click();let card=dialog.locator('#video-clip-editor-2');
 assert(await card.locator('[data-recover-memory]').isDisabled());await card.locator('[data-reference-mode]').click();
 assert(await card.locator('[data-recover-memory]').isChecked());assert(await card.locator('[data-recover-memory]').isEnabled());
 await card.locator('[data-end-frame]').selectOption('next');assert.equal(await card.locator('[data-end-frame]').inputValue(),'next');
 await card.locator('[data-part]').click();assert(await card.locator('[data-recover-memory]').isDisabled());assert(await card.locator('[data-end-frame]').isDisabled());
 await card.locator('[data-whole]').click();assert(await card.locator('[data-recover-memory]').isChecked());assert.equal(await card.locator('[data-end-frame]').inputValue(),'next');
 await card.locator('[data-prompt]').fill('Continue from the previous clip, ending in the next shot pose.');
 await dialog.locator('[name="assistant"]').uncheck();await dialog.locator('[data-save-editor-draft]').click();
 await page.waitForFunction(()=>document.querySelector('[data-editor-draft-status]').textContent.includes('Bozza salvata'));
 assert.equal(saved.state.clips[1].recover_memory,true);assert.equal(saved.state.clips[1].end_frame,'next');
 await dialog.locator('[data-close]').click();await open();dialog=page.locator('.video-clip-dialog');card=dialog.locator('#video-clip-editor-2');
 assert(await card.locator('[data-recover-memory]').isChecked());assert.equal(await card.locator('[data-end-frame]').inputValue(),'next');
 await card.locator('.video-edit-memory').screenshot({path:'work/video-edit-memory-qa/memory-control.png'});
 await card.locator('.video-edit-end-frame').screenshot({path:'work/video-edit-memory-qa/end-frame-control.png'});
 await dialog.locator('[type="submit"]').click();await page.waitForFunction(()=>!document.querySelector('.video-clip-dialog'));
 const launch=writes.find(x=>x.path.endsWith('/video-edit')).body;
 assert.equal(launch.patches.length,1);assert.equal(launch.patches[0].recover_memory,true);assert.equal(launch.patches[0].end_frame,'next');assert.equal(launch.assistant,false);
 saved=null;await page.setViewportSize({width:430,height:900});await open();dialog=page.locator('.video-clip-dialog');
 await dialog.locator('[data-focus="3"]').click();card=dialog.locator('#video-clip-editor-3');await card.locator('[data-reference-mode]').click();
 assert(!(await card.locator('[data-recover-memory]').isChecked()));assert(await card.locator('[data-recover-memory]').isEnabled());
 assert(await card.locator('[data-end-frame] option[value="next"]').evaluate(o=>o.disabled),await card.locator('[data-end-frame]').evaluate(s=>s.outerHTML));
 await card.locator('[data-recover-memory]').check();await card.locator('[data-end-frame]').selectOption('original');
 await page.screenshot({path:'work/video-edit-memory-qa/mobile.png',fullPage:true});
 assert(await dialog.evaluate(d=>d.scrollWidth<=d.clientWidth+2));assert.deepEqual(errors,[]);
 console.log('PASS: memory and final frame together, first/cut clips, whole/partial/mode guards, draft reload, payload and mobile layout.');
}finally{await browser.close();child.kill();}
