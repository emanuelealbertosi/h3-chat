import {spawn} from 'node:child_process';import {once} from 'node:events';import {createInterface} from 'node:readline';import {createRequire} from 'node:module';import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_chat_stream_fixture.py'],{stdio:['ignore','pipe','pipe']});let log='';child.stderr.on('data',x=>log+=x);const lines=createInterface({input:child.stdout});const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(log);})]);lines.close();const fixture=JSON.parse(line);let browser;
try{
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});const page=await browser.newPage({viewport:{width:1280,height:900},reducedMotion:'no-preference'}),errors=[];page.on('pageerror',e=>errors.push(e.message));let live=0;page.on('request',request=>{if(request.url().endsWith('/live'))live++;});
 await page.goto(fixture.url);await page.click(`[data-chat="${fixture.chat_id}"]`);
 const samples=await page.evaluate(async id=>{const values=[];for(let n=0;n<100;n++){values.push(document.querySelector('#msg-'+id+' .message-text')?.innerText?.length||0);await new Promise(resolve=>setTimeout(resolve,25));}return values;},fixture.message_id);
 assert.ok(live>=3,'Dedicated small live updates must be used');assert.ok(samples.some(n=>n>10&&n<90),'A received block must appear progressively');
 await page.waitForFunction(({id,text})=>document.querySelector('#msg-'+id+' .message-text')?.innerText===text,{id:fixture.message_id,text:fixture.final});
 assert.deepEqual(errors,[]);console.log('Normal chat shows partial characters, uses lightweight updates, preserves final emoji and completes without delayed replay.');
}catch(error){console.error(log);throw error;}finally{await browser?.close();child.kill();}
