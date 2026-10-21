import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {readFile} from 'node:fs/promises';
import {once} from 'node:events';
import assert from 'node:assert/strict';
import {build} from 'esbuild';

const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const bundle=await build({stdin:{contents:"import {appendVideoResume} from './ui/video-resume.js'; window.resumeFixture={appendVideoResume};",resolveDir:process.cwd()},bundle:true,write:false,format:'iife',platform:'browser',target:'es2022'});
const html='<!doctype html><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="/static/style.css"><link rel="stylesheet" href="/static/composer.css"><link rel="stylesheet" href="/static/workspace.css"><body><div id="actions"></div><script src="/fixture.js"></script>';
const server=createServer(async(req,res)=>{
 if(req.url==='/fixture.js'){res.setHeader('Content-Type','application/javascript');return res.end(bundle.outputFiles[0].text);}
 if(['/static/style.css','/static/composer.css','/static/workspace.css'].includes(req.url)){res.setHeader('Content-Type','text/css');return res.end(await readFile('.'+req.url));}
 res.setHeader('Content-Type','text/html');res.end(html);
});server.listen(0,'127.0.0.1');await once(server,'listening');
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']});
const page=await browser.newPage({viewport:{width:1000,height:800}}),errors=[],calls=[];
page.on('pageerror',e=>errors.push(e.message));
let assembly=false,reject=false,timeline=false;
await page.exposeFunction('resumeApi',({path,body})=>{
 calls.push({path,body});
 if(reject)throw Error('Una clip salvata non è più disponibile.');
 if(path.includes('/video-edit/'))return {images:[],working_timeline:true,clips:[{clip:1,start:0,end:2,url:'/clip.mp4',prompt:'Saved direction',images:[]}]};
 if(body)return {job_id:'b'.repeat(32),status:'queued'};
 return {job_id:'a'.repeat(32),checkpoint_job_id:'c'.repeat(32),timeline_available:timeline,missing_clips:assembly?[]:[20,21,22,23,24,25],completed:assembly?25:19,total:25,remaining:assembly?0:6,assembly_only:assembly};
});
const mount=()=>page.evaluate(()=>{
 document.querySelector('#actions').innerHTML='';window.notices=[];
 window.resumeFixture.appendVideoResume(document.querySelector('#actions'),{
  chatId:'owned-chat',message:{id:'old-message',role:'assistant',status:'interrupted',meta:{intent:'video'}},
  api:(path,body)=>window.resumeApi({path,body}),busy:()=>!!window.busy,
  onQueued:result=>{window.queued=result;},notify:text=>window.notices.push(text)
 });
});
try{
 await page.goto('http://127.0.0.1:'+server.address().port);await mount();
 await page.getByRole('button',{name:'Riprendi clip mancanti'}).click();
 const dialog=page.locator('.video-resume-dialog');await dialog.waitFor({state:'visible'});
 assert.match(await dialog.locator('[data-summary]').textContent(),/19 clip già salvate · 6 da generare/);
 assert.match(await dialog.locator('[data-missing]').textContent(),/20, 21, 22, 23, 24, 25/);
 assert.equal(calls[0].path,'/chats/owned-chat/video-resume/old-message');
 await page.evaluate(()=>window.busy=true);await page.waitForFunction(()=>document.querySelector('[data-submit]').disabled);
 assert(await dialog.locator('[data-busy]').isVisible());
 await dialog.getByRole('button',{name:'Annulla',exact:true}).click();assert(!calls.some(x=>x.body));
 await page.evaluate(()=>window.busy=false);await page.getByRole('button',{name:'Riprendi clip mancanti'}).click();
 await dialog.getByRole('button',{name:'Riprendi generazione'}).click();await dialog.waitFor({state:'detached'});
 assert.deepEqual(calls.find(x=>x.body),{path:'/chats/owned-chat/video-resume',body:{job_id:'a'.repeat(32)}});
 assert.equal(await page.evaluate(()=>window.queued.status),'queued');
 assembly=true;await mount();await page.setViewportSize({width:430,height:850});
 await page.getByRole('button',{name:'Riprendi clip mancanti'}).click();await dialog.waitFor({state:'visible'});
 assert.match(await dialog.locator('[data-summary]').textContent(),/soltanto il montaggio/);
 assert(await dialog.getByRole('button',{name:'Completa montaggio'}).isVisible());
 assert(await dialog.evaluate(d=>d.scrollWidth<=d.clientWidth+2));
 await dialog.getByRole('button',{name:'Annulla',exact:true}).click();
 timeline=true;const postsBefore=calls.filter(x=>x.body).length;await page.getByRole('button',{name:'Riprendi clip mancanti'}).click();
 await dialog.getByRole('button',{name:'Apri timeline salvata'}).click();await page.locator('.video-clip-dialog').waitFor({state:'visible'});
 assert.equal(calls.filter(x=>x.body).length,postsBefore);assert(calls.some(x=>x.path.endsWith('/video-edit/'+'c'.repeat(32))));await page.locator('.video-clip-dialog [data-close]').click();
 reject=true;await page.getByRole('button',{name:'Riprendi clip mancanti'}).click();
 await page.waitForFunction(()=>window.notices.some(x=>x.includes('non è più disponibile')));
 assert.equal(await page.locator('.video-resume-dialog').count(),0);
 assert.deepEqual(errors,[]);
 console.log('PASS: exact interrupted message/job, saved/missing counts, busy handling, explicit confirmation, assembly-only and mobile layout');
}finally{await browser.close();server.close();}
