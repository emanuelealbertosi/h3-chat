import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import {build} from 'esbuild';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
await mkdir('work/video-activity-qa',{recursive:true});await build({entryPoints:['tests/video-activity-browser-entry.js'],outfile:'work/video-activity-qa/harness.js',bundle:true,format:'iife',platform:'browser'});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);lines.close();
const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']}),page=await browser.newPage({viewport:{width:1200,height:900}}),errors=[];let reads=0;
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(fixture.url);await page.route('**/static/activity-test.js',async route=>route.fulfill({contentType:'application/javascript',body:await readFile('work/video-activity-qa/harness.js','utf8')}));await page.addScriptTag({url:fixture.url+'/static/activity-test.js'});
 await page.exposeFunction('activityApi',()=>{reads++;return {status:'running',stage:reads===1?'Preparazione istruzioni · clip 49 di 64':'Generazione · clip 2 di 64',detail:'3/12 passi',phase:reads===1?'instructions':'generation',clips_total:64,clips_completed:reads===1?0:1,created_at:Date.now()/1000-120,last_signal_at:Date.now()/1000,events:[{time:'21:24:18',label:'Post-produzione · istruzioni clip 49 · 64 selezionati'},{time:'21:24:19',label:'<script>window.h3ActivityInjectedByLabel=true</script>'}]};});
 await page.evaluate(()=>window.activityFixture.openVideoActivity({id:'a'.repeat(32),chatId:'chat',api:window.activityApi}));
 await page.waitForFunction(()=>document.querySelector('[data-stage]').textContent.includes('49 di 64'));assert.equal(await page.locator('[data-progress]').getAttribute('value'),null);await page.screenshot({path:'work/video-activity-qa/activity.png'});
 await page.waitForFunction(()=>document.querySelector('[data-stage]').textContent.includes('clip 2'));assert.match(await page.locator('[data-count]').textContent(),/1 \/ 64/);assert.equal(await page.evaluate(()=>window.h3ActivityInjectedByLabel),undefined);
 await page.getByRole('button',{name:'Chiudi',exact:true}).click();const stopped=reads;await page.waitForTimeout(1700);assert.equal(reads,stopped);assert.deepEqual(errors,[]);
 console.log('PASS: live activity preserves clip number, distinguishes instructions from generation, updates progress, renders log safely, stops polling on close.');
}finally{await browser.close();child.kill();}
