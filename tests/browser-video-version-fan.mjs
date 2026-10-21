import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import {build} from 'esbuild';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const folder='work/video-version-fan-qa';await mkdir(folder,{recursive:true});
await build({entryPoints:['tests/video-steps-browser-entry.js'],outfile:folder+'/harness.js',bundle:true,format:'iife',platform:'browser',target:'es2022'});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe'],env:{...process.env,H3_TIMELINE_PREVIEW_FIXTURE:'1'}});
let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);lines.close();
const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']});
const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(fixture.url);await page.route('**/static/version-fan-test.js',async route=>route.fulfill({contentType:'application/javascript',body:await readFile(folder+'/harness.js','utf8')}));
 await page.addScriptTag({url:fixture.url+'/static/version-fan-test.js'});
 await page.evaluate(async()=>{
  window.fanPosts=[];
  await window.videoStepFixture.openVideoEdit({chatId:'synthetic',source:'versions-film',api:async(path,body)=>{
   if(body){window.fanPosts.push({path,body});return {job_id:'synthetic'};}
   return {working_timeline:true,duration:48,images:[],clips:Array.from({length:24},(_,i)=>{
    const n=i+1,versions=Array.from({length:n===2?3:n===3?16:1},(_,j)=>({id:`clip-${n}-version-${j}`,label:j?'Versione '+j:'Originale',url:'/media/outputs/'+(j?'preview-edit.mp4':'preview-source.mp4'),preview_start:j?0:1,prompt:'Direction '+j,created:j?1792120200+j*3600:null,seed:j?(j===1?517890679:0):-1}));
    return {clip:n,start:i*2,end:i*2+2,url:versions[0].url,preview_start:1,prompt:'Original direction',images:[],selected_version:versions[0].id,versions};
   })};
  }});
 });
 const dialog=page.locator('.video-clip-dialog'),fan=dialog.locator('.video-timeline-versions');
 assert.equal(await dialog.locator('.video-clip-versions select').count(),0);
 assert.equal(await dialog.locator('[data-focus="1"] [data-version-count]').textContent(),'0');
 assert.equal(await dialog.locator('[data-focus="2"] [data-version-count]').textContent(),'2');
 assert.equal(await dialog.locator('[data-focus="3"] [data-version-count]').textContent(),'15');
 await dialog.locator('[data-focus="2"]').click();assert.equal(await fan.isVisible(),true);
 assert.equal(await dialog.locator('[data-focus="2"] [data-clip-seed]').textContent(),'Seed non registrato');assert.equal(await fan.locator('[data-version-id]').count(),3);assert.equal(await fan.locator('[data-version-seed]').nth(1).textContent(),'Seed: 517890679');assert.equal(await fan.locator('[data-version-seed]').nth(2).textContent(),'Seed: 0');assert.equal(await fan.locator('time').count(),2);
 assert.match(await fan.locator('time').first().textContent(),/2026/);
 assert.equal(await fan.locator('[data-version-id="clip-2-version-0"]').getAttribute('aria-pressed'),'true');
 await page.waitForFunction(()=>{const c=document.querySelector('.video-version-card canvas');return c?.getContext('2d').getImageData(160,90,1,1).data[3]>0;});
 await fan.locator('[data-version-id="clip-2-version-1"]').click();
 assert.equal(await fan.locator('[data-version-id="clip-2-version-1"]').getAttribute('aria-pressed'),'true');assert.equal(await dialog.locator('[data-focus="2"] [data-clip-seed]').textContent(),'Seed: 517890679');assert.equal(await dialog.locator('#video-clip-editor-2 [data-used-seed]').textContent(),'Seed: 517890679');
 assert.equal(await dialog.locator('#video-clip-editor-2 video').getAttribute('src'),'/media/outputs/preview-edit.mp4');
 assert.equal(await dialog.locator('[data-focus="2"] [data-version-count]').textContent(),'2');
 assert.equal(await page.evaluate(()=>fanPosts.length),0);
 await fan.locator('[data-version-preview]').first().click();
 await page.waitForFunction(()=>{const v=document.querySelector('.video-version-player');return v?.readyState>=2&&!v.paused&&v.currentTime>=1;});
 assert.equal(await fan.locator('video').evaluate(v=>v.muted),true);
 await fan.locator('[data-close-versions]').click();assert.equal(await fan.locator('video').count(),0);
 await dialog.locator('[data-focus="2"]').click();assert.equal(await fan.locator('[data-version-id="clip-2-version-1"]').getAttribute('aria-pressed'),'true');
 await fan.locator('[data-version-id]').first().focus();await page.keyboard.press('Escape');
 assert.equal(await fan.isVisible(),false);assert.equal(await dialog.isVisible(),true);
 await dialog.locator('[data-focus="2"]').click();
 await page.waitForFunction(()=>[...document.querySelectorAll('.video-versions-fan canvas')].every(c=>c.dataset.previewReady==='true'));
 await page.screenshot({path:folder+'/desktop.png',animations:'disabled'});
 await page.setViewportSize({width:390,height:844});await dialog.locator('[data-focus="3"]').click();
 assert.equal(await fan.locator('[data-version-id]').count(),16);
 const fit=await fan.evaluate(e=>{const r=e.getBoundingClientRect(),s=e.querySelector('.video-versions-fan');return {left:r.left,right:r.right,width:innerWidth,scroll:s.scrollWidth>s.clientWidth};});
 assert.ok(fit.left>=0&&fit.right<=fit.width);assert.equal(fit.scroll,true);
 await fan.locator('[data-version-id]').first().focus();await page.keyboard.press('End');
 assert.equal(await fan.locator('[data-version-id]').last().evaluate(e=>e===document.activeElement),true);
 await page.keyboard.press('Enter');assert.equal(await fan.locator('[data-version-id]').last().getAttribute('aria-pressed'),'true');
 await page.screenshot({path:folder+'/mobile.png',animations:'disabled'});
 await dialog.locator('[data-focus="1"]').click();assert.equal(await fan.locator('[data-version-id]').count(),1);
 await dialog.locator('[data-close]').click();assert.equal(await page.locator('.video-timeline-versions').count(),0);
 assert.deepEqual(errors,[]);console.log('PASS timeline fan: original excluded from badge, dates, lazy previews, version selection, no submissions, single playback, close/Escape, keyboard, overflow and mobile.');
}catch(e){await page.screenshot({path:folder+'/error.png'});console.error(diagnostics);throw e;}finally{await browser.close();child.kill();}
