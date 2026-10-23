import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import {build} from 'esbuild';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
await mkdir('work/video-batch-qa',{recursive:true});
await build({entryPoints:['tests/video-steps-browser-entry.js'],outfile:'work/video-batch-qa/harness.js',bundle:true,format:'iife',platform:'browser',target:'es2022'});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe'],env:{...process.env,TEMP:'F:/H3-TestTmp',TMP:'F:/H3-TestTmp',H3_TIMELINE_PREVIEW_FIXTURE:'1'}});
let diagnostic='';child.stderr.on('data',x=>diagnostic+=x);const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostic);})]);lines.close();
const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']});
const page=await browser.newPage({viewport:{width:1350,height:1000}}),errors=[],writes=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(fixture.url);await page.click(`[data-chat="${fixture.chat}"]`);await page.click('#video-toggle');await page.click('[data-mode-settings="video-hint"]');
 let modal=page.locator('#prompt-mode-settings');
 assert(await modal.locator('#video-request-variants').isVisible());assert(await modal.locator('#video-request-variants').isEnabled());
 await modal.locator('#video-request-variants').fill('3');await modal.locator('#video-request-variants').dispatchEvent('change');
 await modal.locator('#video-request-variants-mode').selectOption('video');await modal.locator('footer button').click();
 await page.route('**/api/chats/*/messages',r=>r.fulfill({json:{job_id:'synthetic',intent:'video',canvas:false}}));
 const posted=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith('/messages'));
 await page.fill('#prompt','Synthetic first video request');await page.locator('#composer').evaluate(e=>e.requestSubmit());
 const body=(await posted).postDataJSON();assert.equal(body.video_parameters.variants,3);assert.equal(body.video_parameters.variants_mode,'video');
 await page.reload();await page.click(`[data-chat="${fixture.chat}"]`);await page.click('[data-mode-settings="video-hint"]');
 modal=page.locator('#prompt-mode-settings');assert.equal(await modal.locator('#video-request-variants').inputValue(),'3');assert.equal(await modal.locator('#video-request-variants-mode').inputValue(),'video');await modal.locator('footer button').click();
 await page.exposeFunction('batchFixtureApi',async({path,body})=>{
  if(body){writes.push({path,body});return {job_id:'synthetic'};}
  return {model_id:'m',batch_variants:true,batch_requested:3,batch_mode:'video',batch_id:'batch-fixture',duration:6,partial_edit:true,working_timeline:true,images:[],models:[{id:'m',name:'Fixture H3',parameters:{steps:12,megapixels:.7,variants:1}}],
   clips:[1,2,3].map(c=>({clip:c,start:(c-1)*2,end:c*2,url:'/media/outputs/preview-source.mp4',preview_start:0,prompt:'Original',images:[],mode:'reference',selected_version:`c${c}v1`,
    versions:[1,2,3].map(v=>({id:`c${c}v${v}`,label:`Batch ${v}`,variant_index:v,variant_batch_id:'batch-fixture',variants_mode:'video',seed:c*10+v,url:'/media/outputs/preview-source.mp4',preview_start:0,prompt:'Original'}))}))};
 });
 await page.route('**/static/batch-harness.js',async r=>r.fulfill({contentType:'application/javascript',body:await readFile('work/video-batch-qa/harness.js','utf8')}));
 await page.addScriptTag({url:fixture.url+'/static/batch-harness.js'});
 await page.evaluate(()=>window.videoStepFixture.openVideoEdit({chatId:'owned-chat',source:'owned-video',initialPrompt:'Fresh full clip',initialParameters:{variants:3,variants_mode:'clip'},api:(path,body)=>window.batchFixtureApi({path,body})}));
 const editor=page.locator('.video-clip-dialog');
 assert.equal(await editor.locator('[name="variants"]').inputValue(),'3');
 await editor.locator('[name="variants"]').scrollIntoViewIfNeeded();await page.screenshot({path:'work/video-batch-qa/batch-settings.png',fullPage:true});
 await editor.locator('[data-batch-branch]').selectOption('3');
 for(const [c,seed] of [[1,13],[2,23],[3,33]])assert.match(await editor.locator(`[data-focus="${c}"] [data-clip-seed]`).textContent(),new RegExp(String(seed)));
 await editor.locator('[data-select-all-clips]').click();await editor.locator('details.video-edit-batch>summary').click();await editor.locator('[data-common-prompt]').fill('Fresh complete scene');await editor.locator('[data-apply-all]').click();
 await page.screenshot({path:'work/video-batch-qa/editor.png',fullPage:true});
 await editor.locator('[type="submit"]').click();
 const edit=writes.find(x=>x.path.endsWith('/video-edit')).body;
 assert.equal(edit.parameters.variants,3);assert.equal(edit.parameters.variants_mode,'clip');assert.equal(edit.patches.length,3);
 assert.deepEqual(edit.versions,{'1':'c1v3','2':'c2v3','3':'c3v3'});assert(edit.patches.every(p=>p.start==null&&p.end==null));
 assert.deepEqual(errors,[]);console.log('Batch first chat request, persisted controls, full-version selection and full-clip edit payload passed; no generation performed.');
}finally{await browser.close();child.kill();}
