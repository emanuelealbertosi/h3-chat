import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import {build} from 'esbuild';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
await mkdir('work/timeline-preview-qa',{recursive:true});
await build({entryPoints:['tests/video-steps-browser-entry.js'],outfile:'work/timeline-preview-qa/harness.js',bundle:true,format:'iife',platform:'browser',target:'es2022'});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe'],env:{...process.env,H3_TIMELINE_PREVIEW_FIXTURE:'1'}});
let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);lines.close();
const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']});
const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(fixture.url);
 await page.route('**/static/timeline-preview-test.js',async route=>route.fulfill({contentType:'application/javascript',body:await readFile('work/timeline-preview-qa/harness.js','utf8')}));
 await page.addScriptTag({url:fixture.url+'/static/timeline-preview-test.js'});
 await page.evaluate(async()=>{
  window.previewPosts=[];
  const source='/media/outputs/preview-source.mp4',edited='/media/outputs/preview-edit.mp4';
  await window.videoStepFixture.openVideoEdit({chatId:'synthetic',source:'saved-timeline',api:async(path,body)=>{
   if(body){window.previewPosts.push(body);return {job_id:'synthetic'};}
   return {working_timeline:true,duration:6,preview_audio:{url:'/media/outputs/preview-audio.wav',start:2.25},images:[],clips:[
    {clip:1,start:0,end:2,url:source,preview_start:1,prompt:'Original first clip',images:[],selected_version:'original-1',versions:[{id:'original-1',label:'Originale',url:source,preview_start:1,prompt:'Original'}]},
    {clip:2,start:2,end:4,url:edited,preview_start:0,prompt:'Edited blue clip',images:[],selected_version:'edited-2',versions:[{id:'original-2',label:'Originale',url:source,preview_start:3,prompt:'Original'},{id:'edited-2',label:'Versione 1',url:edited,preview_start:0,prompt:'Edited'}]},
    {clip:3,start:4,end:6,url:source,preview_start:6,prompt:'Original final clip',images:[],selected_version:'original-3',versions:[{id:'original-3',label:'Originale',url:source,preview_start:6,prompt:'Original'}]}
   ]};
  }});
 });
 const dialog=page.locator('.video-clip-dialog'),preview=dialog.locator('.video-timeline-preview');
 await preview.locator('[data-timeline-preview-open]').click();
 await page.waitForFunction(()=>document.querySelector('[data-timeline-status]').textContent==='Clip 1 · Originale');
 assert.equal(await preview.locator('[data-timeline-audio]').getAttribute('src'),'/media/outputs/preview-audio.wav');
 const getState=()=>preview.evaluate(e=>{const a=e.querySelector('audio'),v=e.querySelector('video:not([hidden])');return {audio:a.currentTime,video:v.currentTime,url:v.getAttribute('src'),muted:v.muted,paused:a.paused,status:e.querySelector('[data-timeline-status]').textContent};});
 let s=await getState();assert.ok(Math.abs(s.audio-2.25)<.08);assert.ok(Math.abs(s.video-1)<.08);
 await preview.locator('[data-timeline-play]').click();
 await page.waitForFunction(()=>document.querySelector('[data-timeline-status]').textContent==='Clip 2 · Versione 1',{},{timeout:15000});
 s=await getState();assert.equal(s.url,'/media/outputs/preview-edit.mp4');assert.equal(s.muted,true);assert.ok(Math.abs((s.audio-2.25)-2-s.video)<.16);
 await page.waitForFunction(()=>document.querySelector('[data-timeline-status]').textContent==='Fine anteprima.',{},{timeout:15000});
 assert.equal((await getState()).paused,true);
 await dialog.getByRole('button',{name:'Modifica clip 2, 0:02–0:04',exact:true}).click();
 await preview.locator('[data-preview-range="clip"]').click();
 await page.waitForFunction(()=>document.querySelector('[data-timeline-status]').textContent==='Clip 2 · Versione 1');
 assert.equal(await preview.locator('[data-timeline-seek]').getAttribute('min'),'2');assert.equal(await preview.locator('[data-timeline-seek]').getAttribute('max'),'4');
 await dialog.locator('[data-version-id="original-2"]').click();
 await page.waitForFunction(()=>document.querySelector('[data-timeline-status]').textContent==='Clip 2 · Originale');
 s=await getState();assert.equal(s.url,'/media/outputs/preview-source.mp4');assert.ok(Math.abs(s.video-3)<.08);assert.ok(Math.abs(s.audio-4.25)<.08);
 await preview.locator('[data-preview-range="custom"]').click();
 await preview.locator('[data-preview-start]').fill('0:01.5');await preview.locator('[data-preview-end]').fill('0:04.5');await preview.locator('[data-preview-end]').dispatchEvent('change');
 await page.waitForFunction(()=>document.querySelector('[data-timeline-status]').textContent==='Clip 1 · Originale');
 await preview.locator('[data-timeline-seek]').evaluate(e=>{e.value='4.2';e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));});
 await page.waitForFunction(()=>document.querySelector('[data-timeline-status]').textContent==='Clip 3 · Originale');
 s=await getState();assert.ok(Math.abs(s.audio-6.45)<.08);assert.ok(Math.abs(s.video-6.2)<.08);
 await preview.locator('[data-timeline-play]').click();await page.waitForFunction(()=>document.querySelector('[data-timeline-status]').textContent==='Fine anteprima.');
 await preview.locator('[data-timeline-stop]').click();await page.waitForFunction(()=>document.querySelector('[data-timeline-status]').textContent==='Clip 1 · Originale');
 await page.screenshot({path:'work/timeline-preview-qa/desktop.png'});
 await page.setViewportSize({width:390,height:844});assert.ok(await dialog.evaluate(e=>e.scrollWidth<=e.clientWidth+2));await preview.scrollIntoViewIfNeeded();await page.screenshot({path:'work/timeline-preview-qa/mobile.png'});
 assert.deepEqual(await page.evaluate(()=>window.previewPosts),[]);await dialog.locator('[data-close]').click();assert.equal(await page.locator('.video-clip-dialog').count(),0);
 assert.deepEqual(errors,[]);console.log('Passed: edited playlist, uninterrupted original audio clock, source offsets, version switching, clip/custom ranges, seek, cleanup, no queued jobs, desktop/mobile.');
}catch(e){await page.screenshot({path:'work/timeline-preview-qa/error.png'});console.error(diagnostics);console.error(await page.evaluate(()=>({status:document.querySelector('[data-timeline-status]')?.textContent,media:[...document.querySelectorAll('.video-timeline-preview video,.video-timeline-preview audio')].map(v=>({tag:v.tagName,url:v.getAttribute('src'),time:v.currentTime,ready:v.readyState,seeking:v.seeking,paused:v.paused,hidden:v.hidden,error:v.error?.message}))})));throw e;}finally{await browser.close();child.kill();}
