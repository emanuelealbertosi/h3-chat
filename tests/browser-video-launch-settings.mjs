import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import {build} from 'esbuild';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const folder='work/video-launch-settings-qa';await mkdir(folder,{recursive:true});
await build({entryPoints:['tests/video-steps-browser-entry.js'],outfile:folder+'/harness.js',bundle:true,format:'iife',platform:'browser',target:'es2022'});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe'],env:{...process.env,H3_TIMELINE_PREVIEW_FIXTURE:'1'}});
let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);lines.close();
const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']});
const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(fixture.url);await page.route('**/static/launch-test.js',async route=>route.fulfill({contentType:'application/javascript',body:await readFile(folder+'/harness.js','utf8')}));await page.addScriptTag({url:fixture.url+'/static/launch-test.js'});
 await page.evaluate(()=>{
  const parameters=(seed,chunks,mp,cfg)=>({seed,attention:'veda',attention_chunks:chunks,attention_chunks_mode:'manual',megapixels:mp,steps:12,cfg,shift_video:9,shift_audio:3,offload:true,veda_sparsity:80,veda_reference_sparsity:60,loras:[],source_conditioning:'reference',pdd_enabled:false});
  const launch2={model:'first',parameters:parameters(10,8,.7,2),steps:12,assistant:false,reference_megapixels:.2,saved_at:123};
  const launch3={model:'second',parameters:parameters(20,56,.98,3),steps:16,assistant:true,reference_megapixels:.5,saved_at:124};
  launch3.parameters.loras=[{path:'F:/fixture/Aunt Cass.safetensors',weight:.8}];
  window.launchWrites=[];window.launchDraft=null;
  window.launchData={model_id:'first',models:[{id:'first',name:'First H3',parameters:{steps:12,megapixels:.5,cfg:1,attention:'sage'}},{id:'second',name:'Second H3',parameters:{steps:12,megapixels:.5,cfg:1,attention:'sage'}}],draft_supported:true,launch_settings:true,attention_choices:true,
   working_timeline:true,partial_edit:true,duration:6,images:[],clips:[1,2,3].map(n=>({clip:n,start:(n-1)*2,end:n*2,url:'/media/outputs/preview-source.mp4',prompt:'Original',images:[],selected_version:n===2?'done-2':'original-'+n,versions:[{id:'original-'+n,label:'Originale',url:'/media/outputs/preview-source.mp4',preview_start:0,prompt:'Original'},...(n===2?[{id:'done-2',label:'Versione 1',url:'/media/outputs/preview-edit.mp4',preview_start:0,prompt:'Edited'}]:[])]})),
   last_launch:{job_id:'frozen-job',saved_at:124,model:launch3.model,parameters:launch3.parameters,steps:16,assistant:true,image_refs:[],pending_clips:[3],completed_clips:[2],clip_launches:{'2':launch2,'3':launch3},edit:{source:'original',image_ids:[],remount:true,versions:{'1':'original-1','2':'done-2','3':'original-3'},patches:[{clip:2,mode:'video',prompt:'Red jacket',images:[],audio_guide:false,reference_megapixels:.2},{clip:3,mode:'video',prompt:'Blue jacket',images:[],start:.25,end:1.75,lip_sync:true,audio_guide:true,reference_megapixels:.5}]}}};
  window.launchApi=async(path,body)=>{
   if(body){launchWrites.push({path,body});if(path.includes('/video-editor-draft/')){launchDraft={version:1,saved_at:Date.now()/1000,state:structuredClone(body.state),image_refs:[]};return launchDraft;}return {job_id:'synthetic'};}
   return structuredClone({...launchData,editor_draft:launchDraft});
  };
 });
 const open=()=>page.evaluate(()=>window.videoStepFixture.openVideoEdit({chatId:'chat',source:'timeline',api:window.launchApi}));
 await open();let dialog=page.locator('.video-clip-dialog');
 assert.equal(await dialog.locator('[data-last-launch]').count(),1);
 assert.equal(await dialog.locator('[name="model"]').inputValue(),'second');assert.equal(await dialog.locator('[name="seed"]').inputValue(),'20');
 assert.equal(await dialog.locator('[name="attention"]').inputValue(),'veda56');assert.equal(await dialog.locator('[name="megapixels"]').inputValue(),'0.98');
 assert.equal(await dialog.locator('[name="video_steps"]').inputValue(),'16');assert.equal(await dialog.locator('[name="reference_megapixels"]').inputValue(),'0.5');
 assert.equal(await dialog.locator('[data-enabled]:checked').count(),1);assert.equal(await dialog.locator('#video-clip-editor-3 [data-start]').inputValue(),'0.25');
 await dialog.locator('[data-focus="2"]').click();assert.equal(await dialog.locator('[name="model"]').inputValue(),'first');assert.equal(await dialog.locator('[name="seed"]').inputValue(),'10');
 assert.equal(await dialog.locator('[name="attention"]').inputValue(),'veda8');assert.equal(await dialog.locator('[name="reference_megapixels"]').inputValue(),'0.2');
 assert.equal(await dialog.locator('[data-version-id="done-2"]').getAttribute('aria-pressed'),'true');
 await dialog.locator('[name="attention"]').selectOption('pytorch');await dialog.locator('[name="seed"]').fill('777');
 await dialog.locator('[data-focus="3"]').click();assert.equal(await dialog.locator('[name="attention"]').inputValue(),'pytorch');assert.equal(await dialog.locator('[name="seed"]').inputValue(),'777');
 await dialog.locator('#video-clip-editor-3 [data-restore-clip-launch]').click();
 assert.equal(await dialog.locator('[name="model"]').inputValue(),'second');assert.equal(await dialog.locator('[name="seed"]').inputValue(),'20');
 assert.equal(await dialog.locator('[data-video-lora-weight]').inputValue(),'0.8');
 await dialog.locator('[data-focus="2"]').locator('..').locator('[data-enabled]').uncheck();
 await dialog.locator('[name="seed"]').fill('33');await dialog.locator('[type="submit"]').click();await dialog.waitFor({state:'detached'});
 const writes=await page.evaluate(()=>launchWrites);assert.equal(writes.length,2);assert.match(writes[0].path,/video-editor-draft/);assert.match(writes[1].path,/video-edit$/);
 assert.equal(writes[1].body.parameters.cfg,3);assert.equal(writes[1].body.parameters.shift_video,9);assert.equal(writes[1].body.parameters.veda_sparsity,80);assert.equal(writes[1].body.parameters.seed,33);
 assert.equal(writes[0].body.state.clip_launches['2'].parameters.seed,10);assert.equal(writes[0].body.state.clip_launches['3'].parameters.seed,33);
 assert.equal(writes[1].body.patches.length,1);assert.equal(writes[1].body.patches[0].clip,3);assert.equal(writes[1].body.patches[0].audio_guide,true);
 assert.equal(writes[1].body.versions['2'],'done-2');
 await open();assert.equal(await dialog.locator('[name="seed"]').inputValue(),'33');
 await dialog.locator('[data-focus="2"]').click();await dialog.locator('#video-clip-editor-2 [data-restore-clip-launch]').click();
 assert.equal(await dialog.locator('[name="seed"]').inputValue(),'10');assert.equal(await dialog.locator('[name="megapixels"]').inputValue(),'0.7');
 await dialog.locator('[data-close]').click();assert.deepEqual(errors,[]);
 console.log('PASS frozen launch defaults, independent per-clip settings, deliberate changes preserved, explicit restore, LoRA/attention/seed/guide, auto-save before queue and generated footage retained.');
}catch(e){await page.screenshot({path:folder+'/error.png'});console.error(diagnostics);throw e;}finally{await browser.close();child.kill();}
