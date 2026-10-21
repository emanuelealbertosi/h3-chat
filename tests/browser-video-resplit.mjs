import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import {build} from 'esbuild';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
await mkdir('work/video-resplit-qa',{recursive:true});
await build({entryPoints:['tests/video-steps-browser-entry.js'],outfile:'work/video-resplit-qa/harness.js',bundle:true,format:'iife',platform:'browser',target:'es2022'});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});
let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);lines.close();
const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']});
const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[],calls=[];let fail=false;
page.on('pageerror',e=>errors.push(e.message));
await page.exposeFunction('resplitApi',async(path,body,method)=>{
 calls.push({path,body,method});if(path.includes('video-import-progress'))return {updated_at:Date.now()/1000,stage:'Preparazione audio originale',percent:42,status:'running'};if(body)return {ok:true};
 if(fail&&path.includes('original?')){await new Promise(r=>setTimeout(r,1800));throw Error('Video originale non disponibile');}
 const original=path.includes('/original'),seconds=path.includes('segment_seconds=10')?10:15;
 return {source:original?'original':'edited',resplit_source:'original',imported:original,working_timeline:!original,segment_seconds:seconds,draft_supported:true,editor_draft:null,
  model_id:'model-a',models:[{id:'model-a',name:'Model A',parameters:{steps:12,megapixels:.7,attention:'sage'}}],images:[],partial_edit:true,duration:30,
  clips:Array.from({length:30/seconds},(_,i)=>({clip:i+1,start:i*seconds,end:(i+1)*seconds,url:'/media/outputs/fixture.mp4',preview_start:0,prompt:'Original direction',images:[],lip_sync:false,
   selected_version:original?'original-'+i:'edited-'+i,versions:[{id:'original-'+i,label:'Originale',url:'/media/outputs/fixture.mp4',preview_start:0,prompt:'Original direction'},...(!original?[{id:'edited-'+i,label:'Versione 1',url:'/media/outputs/fixture.mp4',preview_start:0,prompt:'Edited direction'}]:[])]}))};
});
try{
 await page.goto(fixture.url);await page.route('**/static/resplit-test.js',async route=>route.fulfill({contentType:'application/javascript',body:await readFile('work/video-resplit-qa/harness.js','utf8')}));
 await page.addScriptTag({url:fixture.url+'/static/resplit-test.js'});
 await page.evaluate(()=>window.videoStepFixture.openVideoEdit({chatId:'chat',source:'edited',initialPrompt:'Old change that must be discarded',initialParameters:{megapixels:.98},api:window.resplitApi}));
 let dialog=page.locator('.video-clip-dialog');assert.equal(await dialog.locator('[data-focus]').count(),2);
 assert.match(await dialog.locator('[data-resplit]').textContent(),/modifiche.*non verranno mantenuti/);
 await dialog.locator('[data-resplit-seconds]').selectOption('10');
 page.once('dialog',d=>{assert.match(d.message(),/modifiche.*tagli.*versioni selezionate/s);d.dismiss();});
 await dialog.locator('[data-resplit-video]').click();assert.equal(calls.filter(c=>!c.path.includes('video-import-progress')).length,1);assert.equal(await dialog.locator('[data-common-prompt]').inputValue(),'Old change that must be discarded');
 fail=true;page.once('dialog',d=>d.accept());await dialog.locator('[data-resplit-video]').click();
 await page.waitForFunction(()=>document.querySelector('.video-conversion-progress progress')?.value===42);
 assert.match(await dialog.locator('.video-conversion-progress').textContent(),/Preparazione audio originale.*42% della fase.*Tempo trascorso/);
 await page.screenshot({path:'work/video-resplit-qa/conversion-progress.png'});
 await page.waitForFunction(()=>document.querySelector('[data-error]').textContent.includes('Video originale non disponibile'));
 assert.equal(await dialog.count(),1);assert.equal(await dialog.locator('[data-common-prompt]').inputValue(),'Old change that must be discarded');assert.equal(await dialog.locator('[data-resplit-video]').isEnabled(),true);
 fail=false;page.once('dialog',d=>d.accept());await dialog.locator('[data-resplit-video]').click();
 await page.waitForFunction(()=>document.querySelectorAll('.video-clip-dialog').length===1&&document.querySelectorAll('[data-focus]').length===3);
 dialog=page.locator('.video-clip-dialog');assert.equal(await dialog.locator('[data-common-prompt]').inputValue(),'');assert.equal(await dialog.locator('[name="megapixels"]').inputValue(),'0.98');
 assert.equal(await dialog.locator('[type="submit"]').isDisabled(),true);
 assert.equal(calls.filter(c=>c.path.includes('/video-edit/')).at(-1).path,'/chats/chat/video-edit/original?segment_seconds=10');
 assert.equal(calls.filter(c=>c.body).every(c=>c.method==='DELETE'&&c.body.segment_seconds===10),true);
 assert.deepEqual(errors,[]);await page.screenshot({path:'work/video-resplit-qa/resplit-10s.png'});
 console.log('PASS: edited timeline can be split again; cancel preserves changes, failure keeps editor open, confirmed reset discards clip edits without generation.');
}finally{await browser.close();child.kill();}
