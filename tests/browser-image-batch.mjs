import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir} from 'node:fs/promises';
import {build} from 'esbuild';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const folder='work/image-batch-2026-10-19';await mkdir(folder,{recursive:true});
const bundled=await build({stdin:{contents:`export {appendMedia} from './ui/render.js';`,resolveDir:process.cwd()},bundle:true,write:false,format:'iife',globalName:'batchFixture',platform:'browser',target:'es2022'});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let logs='';child.stderr.on('data',v=>logs+=v);const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(logs);})]);lines.close();const fixture=JSON.parse(line);
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--mute-audio']}),page=await browser.newPage({viewport:{width:1280,height:950}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.route('**/static/app.js*',r=>r.fulfill({contentType:'application/javascript',body:''}));
 await page.goto(fixture.url);await page.route('**/static/batch-test.js',r=>r.fulfill({contentType:'application/javascript',body:bundled.outputFiles[0].text}));
 await page.addScriptTag({url:fixture.url+'/static/batch-test.js'});
 await page.evaluate(()=>{
  document.body.replaceChildren();const style=document.createElement('style');style.textContent='body{display:block;padding:12px;overflow:auto}main{display:grid;grid-template-columns:1fr 1fr;gap:20px}.image-output img{max-height:300px}';document.head.append(style);
  const main=document.createElement('main');document.body.append(main);
  const media=Array.from({length:4},(_,i)=>({id:String(i).padStart(32,'0'),path:'outputs/fixture.png',name:'Immagine '+(i+1)+' · '+(i%2?'MOSS':'Qwen 2.1'),mime:'image/png',batch_id:'batch-fixture',batch_index:i+1,batch_total:4,generation:{seed:i+42,width:i%2?576:1024,height:i%2?1024:576,steps:10}}));
  for(const id of ['chat-batch','canvas-batch']){const host=document.createElement('section');host.id=id;const label=document.createElement('h2');label.textContent=id==='chat-batch'?'Chat · lotto immagini':'Canvas · lotto immagini';host.append(label);main.append(host);window.batchFixture.appendMedia(host,media);}
 });
 assert.equal(await page.locator('.image-batch').count(),2);assert.equal(await page.locator('#chat-batch .image-batch-thumbnail').count(),4);
 await page.locator('#chat-batch [aria-label="Mostra immagine 3"]').click();
 assert.match(await page.locator('#canvas-batch figcaption').textContent(),/3\/4/);assert.match(await page.locator('#chat-batch .image-batch-details').textContent(),/Seed 44/);
 await page.locator('#canvas-batch [aria-label="Mostra immagine 2"]').click();assert.match(await page.locator('#chat-batch figcaption').textContent(),/2\/4/);
 await page.locator('#chat-batch .image-zoom-trigger').click();assert(await page.locator('.image-zoom-dialog').isVisible());await page.keyboard.press('Escape');
 await page.screenshot({path:folder+'/batch-desktop.png'});
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>document.querySelector('main').style.gridTemplateColumns='1fr');
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2),false);await page.screenshot({path:folder+'/batch-mobile.png'});
 assert.deepEqual(errors,[]);console.log('PASS: one main image and thumbnail strip in chat/canvas, synchronized selection, seed display, zoom, mobile. No real generation.');
}finally{await browser.close();child.kill();}
