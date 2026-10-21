import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import {build} from 'esbuild';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
await mkdir('work/video-editor-draft-qa',{recursive:true});
await build({entryPoints:['tests/video-steps-browser-entry.js'],outfile:'work/video-editor-draft-qa/harness.js',bundle:true,format:'iife',platform:'browser',target:'es2022'});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe'],env:{...process.env,H3_TIMELINE_PREVIEW_FIXTURE:'1'}});
let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);lines.close();
const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']});
const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[],drafts=new Map(),writes=[];let reordered=false,rejectDraft=false;
page.on('pageerror',e=>errors.push(e.message));
const refs=[{id:'face',name:'Face.png',mime:'image/png',path:'outputs/fixture.png'},{id:'outfit',name:'Outfit.png',mime:'image/png',path:'outputs/fixture.png'},{id:'later',name:'Later.png',mime:'image/png',path:'outputs/fixture.png'}];
await page.exposeFunction('draftFixtureApi',async({path,body,method})=>{
 const parts=path.split('/'),key=parts[2]+'/'+parts[4];
 if(body){
  writes.push({path,body,method:method||'POST'});
  if(parts[3]==='video-editor-draft'){
   if(method==='DELETE'){drafts.delete(key);return {ok:true};}
   if(rejectDraft)throw Error('Synthetic save failure');
   const saved={version:1,saved_at:Date.now()/1000,state:structuredClone(body.state),image_refs:body.state.image_ids.map(id=>refs.find(x=>x.id===id))};drafts.set(key,saved);return saved;
  }
  return {job_id:'synthetic'};
 }
 const images=(reordered?[refs[2],refs[1],refs[0]]:refs.slice(0,2)).map((r,i)=>({...r,index:i+1,url:'/media/'+r.path}));
 return {model_id:'model-a',models:[{id:'model-a',name:'Model A',parameters:{steps:12,megapixels:.7,attention:'sage'}},{id:'model-b',name:'Model B',parameters:{steps:12,megapixels:.7,attention:'sage'}}],draft_supported:true,editor_draft:drafts.get(key)||null,working_timeline:true,partial_edit:true,duration:6,preview_audio:{url:'/media/outputs/preview-audio.wav',start:0},images,clips:[1,2,3].map(n=>({clip:n,start:(n-1)*2,end:n*2,url:'/media/outputs/preview-source.mp4',preview_start:n-1,prompt:'Original direction',images:[],lip_sync:false,selected_version:'original-'+n,versions:[{id:'original-'+n,label:'Originale',url:'/media/outputs/preview-source.mp4',preview_start:n-1,prompt:'Original direction'},{id:'edited-'+n,label:'Versione 1',url:'/media/outputs/preview-edit.mp4',preview_start:0,prompt:'Edited direction'}]}))};
});
const prepare=async()=>{
 await page.goto(fixture.url);
 await page.route('**/static/draft-test.js',async route=>route.fulfill({contentType:'application/javascript',body:await readFile('work/video-editor-draft-qa/harness.js','utf8')}));
 await page.addScriptTag({url:fixture.url+'/static/draft-test.js'});
 await page.evaluate(()=>window.syntheticBusy=true);
};
const open=async(chat='chat-a',source='video-a',tail=false)=>page.evaluate(async({chat,source,tail})=>{
 await window.videoStepFixture.openVideoEdit({chatId:chat,source,busy:()=>window.syntheticBusy,api:async(path,body,method)=>{
  const result=await window.draftFixtureApi({path,body,method});
  if(tail&&!body){result.duration=6+20/24;result.clips.push({clip:4,start:6,end:6+20/24,url:'/media/outputs/preview-source.mp4',preview_start:0,images:[],lip_sync:false,prompt:'Short original tail'});}
  return result;
 }});
},{chat,source,tail});
try{
 await prepare();await open();let dialog=page.locator('.video-clip-dialog');
 await dialog.locator('[data-focus="2"]').click();const card=dialog.locator('#video-clip-editor-2');
 await card.locator('[data-prompt]').fill('Dress <Picture 1> using <Picture 2>');await card.locator('[data-part]').click();
 await card.locator('[data-start]').fill('0.25');await card.locator('[data-start]').dispatchEvent('change');
 await card.locator('[data-end]').fill('1.75');await card.locator('[data-end]').dispatchEvent('change');
 await card.locator('[data-lipsync]').check();
 await card.locator('[data-image-summary]').click();
 await card.getByRole('button',{name:'Picture 1 · Face.png',exact:true}).click();await card.getByRole('button',{name:'Picture 2 · Outfit.png',exact:true}).click();
 await card.locator('[data-anchor-first]').check();await card.locator('[data-anchor-mode="three"]').click();
 await card.locator('[data-anchor-picture="first"]').selectOption('1');await card.locator('[data-anchor-picture="middle"]').selectOption('2');await card.locator('[data-anchor-picture="last"]').selectOption('1');
 await dialog.locator('[data-focus="2"]').click();await dialog.locator('[data-version-id="edited-2"]').click();
 await dialog.locator('[name="model"]').selectOption('model-b');await dialog.locator('[name="attention"]').selectOption('veda');
 await dialog.getByRole('button',{name:'0,98 MP',exact:true}).click();await dialog.locator('[name="video_steps"]').fill('16');await dialog.locator('[name="video_steps"]').dispatchEvent('input');
 await dialog.locator('[data-seed-mode="fixed"]').click();await dialog.locator('[name="seed"]').fill('123');
 await dialog.getByRole('button',{name:'0,20 · rapido',exact:true}).click();await dialog.locator('[name="assistant"]').uncheck();await dialog.locator('[name="remount"]').uncheck();
 await dialog.locator('.video-edit-batch summary').click();await dialog.locator('[data-common-prompt]').fill('Shared outfit <Picture 2>');
 assert.equal(await dialog.locator('[type="submit"]').isDisabled(),true);assert.equal(await dialog.locator('[data-save-editor-draft]').isEnabled(),true);
 await dialog.locator('[data-save-editor-draft]').click();await page.waitForFunction(()=>document.querySelector('[data-editor-draft-status]').textContent.startsWith('Bozza salvata'));
 assert.equal(writes.length,1);assert.equal(drafts.get('chat-a/video-a').state.clips[1].first,6);assert.equal(drafts.get('chat-a/video-a').state.clips[1].last,42);
 await card.locator('[data-prompt]').fill('Unsaved changes');await dialog.locator('[data-restore-editor-draft]').click();
 await page.waitForFunction(()=>document.querySelectorAll('.video-clip-dialog').length===1&&document.querySelector('#video-clip-editor-2 [data-prompt]')?.value==='Dress <Picture 1> using <Picture 2>');
 await dialog.locator('[data-close]').click();reordered=true;await prepare();await open();
 assert.equal(await dialog.locator('#video-clip-editor-2 [data-prompt]').inputValue(),'Dress <Picture 3> using <Picture 2>');
 assert.equal(await dialog.locator('#video-clip-editor-2 [data-first]').inputValue(),'6');assert.equal(await dialog.locator('#video-clip-editor-2 [data-last]').inputValue(),'42');
 assert.equal(await dialog.locator('[name="model"]').inputValue(),'model-b');assert.equal(await dialog.locator('[name="attention"]').inputValue(),'veda');
 assert.equal(await dialog.locator('[name="megapixels"]').inputValue(),'0.98');assert.equal(await dialog.locator('[name="video_steps"]').inputValue(),'16');assert.equal(await dialog.locator('[name="seed"]').inputValue(),'123');
 assert.equal(await dialog.locator('[name="assistant"]').isChecked(),false);assert.equal(await dialog.locator('[name="remount"]').isChecked(),false);
 assert.equal(await dialog.locator('#video-clip-editor-2 [data-anchor-picture="first"]').inputValue(),'3');assert.equal(await dialog.locator('#video-clip-editor-2 [data-anchor-picture="middle"]').inputValue(),'2');
 await dialog.locator('[data-focus="2"]').click();assert.equal(await dialog.locator('[data-version-id="edited-2"]').getAttribute('aria-pressed'),'true');
 await dialog.locator('[data-timeline-preview-open]').click();await page.waitForFunction(()=>document.querySelector('[data-timeline-status]').textContent==='Clip 1 · Originale');
 assert.equal(writes.length,1);await page.screenshot({path:'work/video-editor-draft-qa/desktop.png'});
 await page.setViewportSize({width:390,height:844});assert.ok(await dialog.evaluate(e=>e.scrollWidth<=e.clientWidth+2));await dialog.locator('.video-draft-toolbar').scrollIntoViewIfNeeded();await page.screenshot({path:'work/video-editor-draft-qa/mobile.png'});
 await page.evaluate(()=>window.syntheticBusy=false);await page.waitForFunction(()=>!document.querySelector('.video-clip-dialog [type="submit"]').disabled);
 await dialog.locator('[type="submit"]').click();await dialog.waitFor({state:'detached'});assert.equal(writes.length,3);assert.match(writes[1].path,/video-editor-draft/);assert.equal(writes[1].body.state.parameters.seed,123);assert.equal(writes[2].body.parameters.seed,123);assert.deepEqual(writes[2].body.patches[0].images,[3,2]);assert.equal(writes[2].body.patches[0].start,.25);assert.equal(writes[2].body.patches[0].end,1.75);assert.equal(writes[2].body.remount,false);
 await open();assert.equal(await dialog.locator('[name="seed"]').inputValue(),'123');assert.equal(await dialog.locator('#video-clip-editor-2 [data-prompt]').inputValue(),'Dress <Picture 3> using <Picture 2>');await dialog.locator('[data-close]').click();
 await open('chat-b');assert.equal(await dialog.locator('[data-restore-editor-draft]').isDisabled(),true);await dialog.locator('[data-close]').click();
 await open('chat-a','video-b');assert.equal(await dialog.locator('[data-restore-editor-draft]').isDisabled(),true);await dialog.locator('[data-close]').click();
 await open();await dialog.locator('[data-clear-editor-draft]').click();await page.waitForFunction(()=>document.querySelectorAll('.video-clip-dialog').length===1&&!document.querySelector('[data-clear-editor-draft]').disabled&&!document.querySelector('#video-clip-editor-2')?.getAttribute('style'));
 assert.equal(drafts.has('chat-a/video-a'),false);assert.equal(await dialog.locator('[data-restore-editor-draft]').isDisabled(),true);assert.equal(await dialog.locator('.video-edit-clip:visible').count(),0);
 await dialog.locator('[data-close]').click();
 await page.setViewportSize({width:1400,height:1000});await open();
 await dialog.locator('[data-select-all-clips]').click();assert.equal(await dialog.locator('[data-enabled]:checked').count(),3);
 assert.equal(await dialog.locator('.video-edit-clip:visible').count(),1);
 await dialog.locator('[data-clear-clips]').click();assert.equal(await dialog.locator('[data-enabled]:checked').count(),0);
 await dialog.locator('[data-focus="2"]').click();await dialog.locator('#video-clip-editor-2 [data-image-summary]').click();
 await dialog.locator('#video-clip-editor-2').getByRole('button',{name:'Picture 2 · Outfit.png',exact:true}).click();
 await dialog.locator('.video-edit-batch summary').click();await dialog.locator('[data-common-prompt]').fill('Replace the woman with the adult anime character from <Picture 2>, preserving anime style.');
 await dialog.locator('[data-apply-all]').click();assert.equal(await dialog.locator('[data-enabled]:checked').count(),3);
 await dialog.locator('[type="submit"]').click();await dialog.waitFor({state:'detached'});const batch=writes.at(-1).body;
 assert.equal(batch.patches.length,3);assert.equal(new Set(batch.patches.map(x=>x.prompt)).size,1);
 assert.ok(batch.patches.every(x=>x.mode==='video'&&JSON.stringify(x.images)==='[2]'));
 await open('chat-a','legacy-tail',true);await dialog.locator('[data-select-all-clips]').click();
 assert.equal(await dialog.locator('[data-enabled]:checked').count(),3);assert.equal(await dialog.locator('[data-focus="4"]').locator('..').locator('[data-enabled]').isDisabled(),true);
 assert.match(await dialog.locator('[data-focus="4"]').innerText(),/0:06.833/);
 await dialog.locator('[data-focus="4"]').click();assert.equal(await dialog.locator('[data-enabled]:checked').count(),3);
 assert.equal(await dialog.locator('#video-clip-editor-4').isVisible(),true);
 await page.screenshot({path:'work/video-editor-draft-qa/batch-tail.png'});
 await dialog.locator('[data-close]').click();assert.deepEqual(errors,[]);
 await prepare();await page.evaluate(()=>window.syntheticBusy=false);
 await page.evaluate(async()=>window.videoStepFixture.openVideoEdit({chatId:'reload',source:'source',api:async(path,body,method)=>window.draftFixtureApi({path,body,method}),
 initialModel:'model-b',initialSteps:12,initialAssistant:false,initialParameters:{megapixels:.5,seed:-1},
 initialReferences:[{id:'face',name:'Face.png',mime:'image/png',path:'outputs/fixture.png'}],
 initialEdit:{source:'source',image_ids:['face','outfit'],remount:false,versions:{'2':'edited-2'},patches:[{clip:2,prompt:'Use <Picture 1>',images:[1],mode:'video',start:.25,end:1.75,audio_guide:false,reference_megapixels:.2}]}}));
 dialog=page.locator('.video-clip-dialog');assert.equal(await dialog.locator('[data-enabled]:checked').count(),1);
 assert.equal(await dialog.locator('#video-clip-editor-2 [data-prompt]').inputValue(),'Use <Picture 3>');
 assert.equal(await dialog.locator('#video-clip-editor-2 [data-first]').inputValue(),'6');
 assert.equal(await dialog.locator('#video-clip-editor-2 [data-audio-guide]').isChecked(),false);
 await dialog.locator('#video-clip-editor-2 [data-lipsync]').check();assert.equal(await dialog.locator('#video-clip-editor-2 [data-audio-guide]').isChecked(),true);
 await dialog.locator('#video-clip-editor-2 [data-audio-guide]').uncheck();assert.equal(await dialog.locator('#video-clip-editor-2 [data-lipsync]').isChecked(),false);
 await dialog.locator('[data-lipsync-all]').check();
 assert.equal(await dialog.locator('[data-lipsync]:checked').count(),3);assert.equal(await dialog.locator('[data-audio-guide]:checked').count(),3);
 await dialog.locator('#video-clip-editor-2 [data-audio-guide]').uncheck();
 assert.equal(await dialog.locator('[data-lipsync-all]').evaluate(x=>x.indeterminate),true);
 await dialog.locator('#video-clip-editor-2 [data-lipsync]').check();
 await dialog.locator('.video-edit-batch summary').click();await dialog.locator('[data-common-prompt]').fill('Preserve source motion and original voice');await dialog.locator('[data-apply-all]').click();
 assert.equal(await dialog.locator('[data-lipsync-all]').isChecked(),true);assert.equal(await dialog.locator('[data-lipsync]:checked').count(),3);assert.equal(await dialog.locator('[data-audio-guide]:checked').count(),3);
 await dialog.locator('[data-save-editor-draft]').click();await page.waitForFunction(()=>document.querySelector('[data-editor-draft-status]').textContent.startsWith('Bozza salvata'));
 const audioDraft=writes.at(-1).body.state;assert.equal(audioDraft.clips.every(x=>x.lip_sync&&x.audio_guide),true);
 await dialog.locator('[data-lipsync-all]').uncheck();assert.equal(await dialog.locator('[data-lipsync]:checked').count(),0);
 await dialog.locator('[data-restore-editor-draft]').click();await page.waitForFunction(()=>document.querySelectorAll('.video-clip-dialog').length===1&&document.querySelector('[data-lipsync-all]').checked);
 dialog=page.locator('.video-clip-dialog');rejectDraft=true;const queuedBefore=writes.filter(w=>w.path.endsWith('/video-edit')).length;await dialog.locator('[type="submit"]').click();
 await page.waitForFunction(()=>document.querySelector('[data-error]')?.textContent.includes('Impostazioni non salvate'));
 assert.equal(writes.filter(w=>w.path.endsWith('/video-edit')).length,queuedBefore);assert.equal(await dialog.isVisible(),true);rejectDraft=false;
 await dialog.locator('[type="submit"]').click();
 await dialog.waitFor({state:'detached'});
 const allAudioPost=writes.at(-1).body;assert.equal(allAudioPost.patches.length,3);assert.equal(allAudioPost.patches.every(x=>x.lip_sync&&x.audio_guide),true);
 assert.deepEqual(errors,[]);
 console.log('Passed: save while busy, restore unsaved changes, reload, image identity remapping, versions/intervals/seed/settings, preview while busy, automatic launch enable, independent drafts, clear, desktop/mobile.');
}catch(e){await page.screenshot({path:'work/video-editor-draft-qa/error.png'});console.error(diagnostics);throw e;}finally{await browser.close();child.kill();}
