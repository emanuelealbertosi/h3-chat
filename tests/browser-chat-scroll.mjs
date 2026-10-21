import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});
let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);lines.close();const fixture=JSON.parse(line);
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--mute-audio']}),page=await browser.newPage({viewport:{width:1380,height:900}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));let release;const gate=new Promise(resolve=>release=resolve);
const bottom=()=>page.waitForFunction(()=>{const e=document.querySelector('#scroll-area');return e.scrollHeight-e.scrollTop-e.clientHeight<3;});
try{
 await page.route('**/api/chats/'+fixture.chat,async route=>{
  const response=await route.fetch(),chat=await response.json();
  chat.messages=Array.from({length:40},(_,i)=>({id:'scroll-'+i,role:'assistant',content:'Messaggio di prova '+i+'\n\n'+('Contenuto della conversazione. '.repeat(20)),status:'done',created:i,meta:{},media:[]}));
  chat.messages.at(-1).media=[{id:'c'.repeat(32),name:'Immagine ritardata',mime:'image/png',path:'outputs/scroll-delayed.png'}];
  await route.fulfill({response,json:chat});
 });
 await page.route('**/media/outputs/scroll-delayed.png',async route=>{await gate;await route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1600"><rect width="800" height="1600" fill="#087f8c"/></svg>'});});
 await page.goto(fixture.url);await page.locator('[data-chat="'+fixture.chat+'"]').click();await page.locator('#msg-scroll-39').waitFor();await bottom();
 const before=await page.locator('#scroll-area').evaluate(e=>e.scrollHeight);release();
 await page.locator('#msg-scroll-39 img[loading=lazy]').evaluate(image=>image.decode());await bottom();
 assert(await page.locator('#scroll-area').evaluate((e,before)=>e.scrollHeight>before,before));
 await page.locator('#scroll-area').hover();await page.mouse.wheel(0,-4);
 await page.waitForFunction(()=>{const e=document.querySelector('#scroll-area');return e.scrollHeight-e.scrollTop-e.clientHeight>1;});
 const tinyAway=await page.locator('#scroll-area').evaluate(e=>e.scrollTop);
 await page.locator('#messages').evaluate(e=>{const late=document.createElement('div');late.style.height='100px';e.append(late);});
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 assert(Math.abs(await page.locator('#scroll-area').evaluate(e=>e.scrollTop)-tinyAway)<2);
 await page.mouse.wheel(0,1000);await bottom();
 // A reader moving upward must not be dragged back by later layout changes.
 await page.locator('#scroll-area').hover();await page.mouse.wheel(0,-750);await page.waitForFunction(()=>{const e=document.querySelector('#scroll-area');return e.scrollHeight-e.scrollTop-e.clientHeight>300;});
 const away=await page.locator('#scroll-area').evaluate(e=>e.scrollTop);
 await page.locator('#messages').evaluate(e=>{const late=document.createElement('div');late.style.height='650px';e.append(late);});
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 assert(Math.abs(await page.locator('#scroll-area').evaluate(e=>e.scrollTop)-away)<4);
 await page.waitForResponse(response=>response.url().endsWith('/api/chats/'+fixture.chat));
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 assert(Math.abs(await page.locator('#scroll-area').evaluate(e=>e.scrollTop)-away)<4);
 // A different chat starts at its end, even after leaving the old one scrolled up.
 await page.locator('[data-chat="'+fixture.other+'"]').click();await page.locator('[data-chat="'+fixture.chat+'"]').click();await page.locator('#msg-scroll-39').waitFor();await bottom();
 await page.setViewportSize({width:700,height:720});await bottom();assert.deepEqual(errors,[]);
 console.log('PASS: old chat opens at last message; delayed image and viewport resize stay at bottom; manual upward scroll is preserved; switching chats resets following. No inference.');
}finally{release();await browser.close();child.kill();}
