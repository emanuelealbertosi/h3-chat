import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});
let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);
const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);lines.close();
const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']}),page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(fixture.url);await page.evaluate(async()=>{const {token}=await(await fetch('/api/state')).json();const r=await fetch('/fixture/motion-continuous',{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':token},body:'{}'});if(!r.ok)throw Error(await r.text());});
 await page.click(`[data-chat="${fixture.chat}"]`);
 await page.click('#canvas-toggle');
 await page.locator('[data-continuous-preview]').click();
 const dialog=page.locator('.motion-continuous-preview');
 await dialog.locator('[data-note]').filter({hasText:'voce e narrazione non vengono rigenerate'}).waitFor();
 const slider=dialog.locator('[data-total-time]');
 await slider.evaluate(el=>{el.value='10.5';el.dispatchEvent(new Event('input',{bubbles:true}));});
 const frames=await dialog.locator('iframe[data-h3-scene]').evaluateAll(nodes=>nodes.map(n=>({opacity:+n.style.opacity,transform:n.style.transform,visible:n.style.visibility,box:n.getBoundingClientRect().toJSON()})));
 assert.equal(frames.length,2);assert.equal(frames[1].opacity,.5);assert.match(frames[1].transform,/scale\(1\.04\)/);assert.ok(frames.every(f=>f.box.width>100));
 await dialog.locator('[data-play]').click();await dialog.locator('[data-close]').click();await dialog.waitFor({state:'detached'});
 assert.deepEqual(errors,[]);console.log('PASS: continuous Motion preview, two rendered scenes, timed zoom transition, seek, playback and cleanup; CPU only.');
}catch(e){console.error(diagnostics);throw e;}finally{await browser.close();child.kill();}
