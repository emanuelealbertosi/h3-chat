import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostic='';child.stderr.on('data',x=>diagnostic+=x);
const lines=createInterface({input:child.stdout}),timer=setTimeout(()=>child.kill(),30000);
const first=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostic);})]);clearTimeout(timer);const fixture=JSON.parse(first[0]);lines.close();
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage();const errors=[],chunks=[];
page.on('pageerror',error=>errors.push(error.message));page.on('request',r=>{if(r.url().endsWith('/chunk'))chunks.push(JSON.parse(r.postData()));});
try{
 await page.goto(fixture.url);await page.waitForSelector('#attach');
 assert.equal(await page.locator('#file-input').getAttribute('accept'),null);
 const buffer=Buffer.alloc(3*1024**2,7);
 await page.locator('#file-input').setInputFiles({name:'original.custom',mimeType:'application/octet-stream',buffer});
 await page.waitForFunction(()=>document.querySelectorAll('#attachments .attachment').length===1);
 assert.equal(chunks.length,2);assert.deepEqual(chunks.map(c=>c.offset),[0,2*1024**2]);
 const listing=await page.evaluate(async()=>await(await fetch('/api/gallery?q=original.custom')).json());
 assert.equal(listing.items.length,1);assert.equal(listing.items[0].size,buffer.length);
 const response=await page.request.get(new URL('/media/'+listing.items[0].path,fixture.url).href);assert.deepEqual(await response.body(),buffer);
 const source=Buffer.from('{"preserved":"yes"}');
 await page.locator('#file-input').setInputFiles({name:'source.json',mimeType:'application/json',buffer:source});
 await page.waitForFunction(()=>document.querySelectorAll('#attachments .attachment').length===2);
 const second=await page.evaluate(async()=>await(await fetch('/api/gallery?q=source.json')).json());
 assert.deepEqual(await(await page.request.get(new URL('/media/'+second.items[0].path,fixture.url).href)).body(),source);
 const privateMetadata=await page.request.get(new URL('/media/uploads/'+second.items[0].id+'.json',fixture.url).href);assert.equal(privateMetadata.status(),403);
 assert.deepEqual(errors,[]);console.log('PC chooser without format filter, multi-block upload, arbitrary format, gallery download and JSON payload preservation passed.');
}finally{await browser.close();child.kill();}
