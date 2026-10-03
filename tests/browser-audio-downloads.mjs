import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostic='';child.stderr.on('data',x=>diagnostic+=x);
const lines=createInterface({input:child.stdout}),timer=setTimeout(()=>child.kill(),30000),first=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostic);})]);clearTimeout(timer);const fixture=JSON.parse(first[0]);lines.close();
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
  await mkdir('work/audio-download-qa',{recursive:true});await page.goto(fixture.url);await page.click(`[data-chat="${fixture.chat}"]`);
  await page.evaluate(async()=>{const {token}=await(await fetch('/api/state')).json();const response=await fetch('/fixture/audio',{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':token},body:'{}'});if(!response.ok)throw Error(await response.text());});
  await page.waitForSelector('.audio-output');
  for(const [host,label] of [['#messages','chat'],['#canvas-preview','canvas']]){
    if(label==='canvas')await page.click('#canvas-toggle');
    const output=page.locator(host+' .audio-output').last();await output.waitFor();
    let download=page.waitForEvent('download');await output.getByText('Scarica WAV',{exact:true}).click();await(await download).saveAs(`work/audio-download-qa/${label}.wav`);
    download=page.waitForEvent('download');await output.getByText('Scarica MP3',{exact:true}).click();await(await download).saveAs(`work/audio-download-qa/${label}.mp3`);
    const wav=await readFile(`work/audio-download-qa/${label}.wav`),mp3=await readFile(`work/audio-download-qa/${label}.mp3`);assert.equal(wav.subarray(0,4).toString(),'RIFF');assert.ok(mp3.length>1000&&mp3.length<wav.length);assert.equal(await output.locator('.audio-export-error').count(),0);
  }
  assert.deepEqual(await readFile('work/audio-download-qa/chat.mp3'),await readFile('work/audio-download-qa/canvas.mp3'));
  assert.deepEqual(await readFile('work/audio-download-qa/chat.wav'),await readFile('work/audio-download-qa/canvas.wav'));
  await page.reload();await page.click(`[data-chat="${fixture.chat}"]`);await page.waitForSelector('.audio-output [data-audio-format="mp3"]');
  // The real HTTP endpoint must validate the session and media identity.
  const result=await page.evaluate(async()=>{
    const send=(headers,body)=>fetch('/api/export/audio',{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify(body)});
    const {token}=await(await fetch('/api/state')).json();return [(await send({},{})).status,(await send({'X-H3-Token':token},{id:'../private',format:'mp3'})).status];
  });assert.deepEqual(result,[403,400]);assert.deepEqual(errors,[]);
  await page.evaluate(async()=>{const {token}=await(await fetch('/api/state')).json();const response=await fetch('/fixture/manim-duration',{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':token},body:'{}'});if(!response.ok)throw Error(await response.text());});
  await page.getByText('Recupera animazione',{exact:true}).click();await page.getByText('Durata effettiva: 28.0 s · richiesta: 20 s.',{exact:true}).waitFor();
  await page.getByText('Apri canvas',{exact:true}).last().click();await page.waitForSelector('#canvas-preview video');
  await page.waitForFunction(()=>document.querySelector('#canvas-preview video')?.duration===28);
  assert.ok((await page.locator('#messages').innerText()).includes('Durata effettiva: 28.0 s'));
  assert.equal(await page.locator('#messages .message-error').count(),0);assert.deepEqual(errors,[]);
  console.log('WAV originals and actual MP3 downloads passed in chat and canvas, including cache, reload and HTTP session/media validation.');
  console.log('Legacy Manim duration error: recovered the real 28-second MP4 into the canvas without a new render.');
}finally{await browser.close();child.kill();}
