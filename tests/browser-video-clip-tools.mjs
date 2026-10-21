import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import {build} from 'esbuild';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
await mkdir('work/clip-tools-qa',{recursive:true});
await build({entryPoints:['tests/video-steps-browser-entry.js'],outfile:'work/clip-tools-qa/harness.js',bundle:true,format:'iife',platform:'browser',target:'es2022'});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe'],env:{...process.env,H3_TIMELINE_PREVIEW_FIXTURE:'1'}});
let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);lines.close();
const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']});
const page=await browser.newPage({viewport:{width:1450,height:1000}}),errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));
const video={id:'a'.repeat(32),name:'Post production.mp4',mime:'video/mp4',path:'outputs/preview-edit.mp4',url:'/media/outputs/preview-edit.mp4',origin:'generated',size:1000};
await page.exposeFunction('clipToolsApi',async({path,body})=>{
 if(path==='/gallery/select')return [video];
 if(path.startsWith('/gallery?'))return {items:[video],offset:1,more:false,total:1};
 if(body){writes.push({path,body});return {job_id:'synthetic',canvas:body.action==='infographic'};}
 return {model_id:'m',models:[{id:'m',name:'Synthetic H3',parameters:{steps:12,megapixels:.7,attention:'veda'}}],clip_tools:true,partial_edit:true,working_timeline:true,
  duration:6,images:[],preview_audio:{url:'/media/outputs/preview-audio.wav',start:0},
  clips:[1,2,3].map(n=>({clip:n,start:(n-1)*2,end:n*2,url:'/media/outputs/preview-source.mp4',preview_start:n-1,prompt:'Original',images:[],
   selected_version:'original-'+n,versions:[{id:'original-'+n,label:'Originale',url:'/media/outputs/preview-source.mp4',preview_start:n-1,prompt:'Original'},
    {id:'edited-'+n,label:'Versione 1',url:'/media/outputs/preview-edit.mp4',preview_start:0,prompt:'Edited'}]}))};
});
const open=()=>page.evaluate(()=>window.videoStepFixture.openVideoEdit({chatId:'owned-chat',source:'owned-video',busy:()=>!!window.syntheticBusy,
 api:(path,body)=>window.clipToolsApi({path,body})}));
try{
 await page.goto(fixture.url);await page.route('**/static/clip-tools-test.js',async route=>route.fulfill({contentType:'application/javascript',body:await readFile('work/clip-tools-qa/harness.js','utf8')}));
 await page.addScriptTag({url:fixture.url+'/static/clip-tools-test.js'});
 await open();let dialog=page.locator('.video-clip-dialog');await dialog.locator('[data-focus="2"]').click();
 let card=dialog.locator('#video-clip-editor-2');await dialog.locator('[data-version-id="edited-2"]').click();
 await card.locator('[data-part]').click();await card.locator('[data-start]').fill('0.25');await card.locator('[data-start]').dispatchEvent('change');
 await card.locator('[data-end]').fill('1.75');await card.locator('[data-end]').dispatchEvent('change');
 await card.locator('[data-clip-infographic]').click();const modal=page.locator('.video-post-dialog');
 await modal.locator('[data-prompt]').fill('Split screen, neon title at 0.5 seconds');
 await modal.getByRole('button',{name:'2 affiancati',exact:true}).click();await modal.getByRole('button',{name:'Neon',exact:true}).click();
 await page.screenshot({path:'work/clip-tools-qa/desktop.png',fullPage:true});await modal.locator('[data-create]').click();
 await page.waitForFunction(()=>!document.querySelector('.video-clip-dialog'));
 assert.equal(writes[0].path,'/chats/owned-chat/video-clip');assert.equal(writes[0].body.clip,2);
 assert.deepEqual([writes[0].body.start,writes[0].body.end],[.25,1.75]);assert.equal(writes[0].body.versions['2'],'edited-2');
 assert.equal(writes[0].body.infographic.layout,'columns2');assert.equal(writes[0].body.infographic.palette,'neon');
 await open();dialog=page.locator('.video-clip-dialog');await dialog.locator('[data-focus="3"]').click();
 await dialog.locator('#video-clip-editor-3 [data-clip-export]').click();await page.waitForFunction(()=>!document.querySelector('.video-clip-dialog'));
 assert.equal(writes[1].body.action,'export');assert.equal(writes[1].body.clip,3);assert.equal(writes[1].body.start,undefined);
 await open();dialog=page.locator('.video-clip-dialog');await dialog.locator('[data-focus="1"]').click();
 await dialog.locator('#video-clip-editor-1 [data-clip-replace]').click();await page.locator('.video-post-dialog [data-gallery]').click();
 await page.locator('.gallery-pick').click();await page.locator('.gallery-dialog [data-select]').click();await page.waitForFunction(()=>!document.querySelector('.video-clip-dialog'));
 assert.equal(writes[2].body.action,'replace');assert.equal(writes[2].body.media_id,video.id);assert.equal(writes[2].body.clip,1);
 await page.setViewportSize({width:430,height:900});await open();dialog=page.locator('.video-clip-dialog');
 await dialog.locator('[data-focus="2"]').click();await dialog.locator('#video-clip-editor-2 [data-clip-infographic]').click();
 await page.screenshot({path:'work/clip-tools-qa/mobile.png',fullPage:true});
 assert(await page.locator('.video-post-dialog').evaluate(d=>d.scrollWidth<=d.clientWidth+2));
 await page.locator('.video-post-dialog [data-close]').click();await dialog.locator('[data-close]').click();
 await page.evaluate(()=>window.syntheticBusy=true);await open();dialog=page.locator('.video-clip-dialog');
 await dialog.locator('[data-focus="1"]').click();assert(await dialog.locator('#video-clip-editor-1 [data-clip-export]').isDisabled());
 await page.evaluate(()=>window.syntheticBusy=false);await page.waitForFunction(()=>!document.querySelector('#video-clip-editor-1 [data-clip-export]').disabled);
 await dialog.locator('#video-clip-editor-1 [data-clip-delete]').click();
 await page.locator('.video-post-dialog [data-confirm-delete]').click();
 await page.waitForFunction(()=>!document.querySelector('.video-clip-dialog'));
 assert.equal(writes.at(-1).path,'/chats/owned-chat/video-assemble');assert.deepEqual(writes.at(-1).body.remove_clips,[1]);
 assert.deepEqual(errors,[]);console.log('PASS: selected version/range, infographic, export, gallery replacement, busy state and mobile layout');
}finally{await browser.close();child.kill();}
