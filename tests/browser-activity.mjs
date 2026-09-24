import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const cfg=JSON.parse(await readFile(new URL('../work/qa-v09-activity.json',import.meta.url),'utf8'));
const python=fileURLToPath(new URL('../runtime/python/python.exe',import.meta.url)),db=fileURLToPath(new URL('../work/qa-v09/chat.sqlite',import.meta.url));
const change=(job,stage,done=false)=>execFileSync(python,['-c',"import sqlite3,sys; db=sqlite3.connect(sys.argv[1]); db.execute('UPDATE jobs SET stage=?,status=? WHERE id=?',(sys.argv[3],'done' if sys.argv[4]=='1' else 'running',sys.argv[2])); db.execute('UPDATE messages SET status=? WHERE id=(SELECT message_id FROM jobs WHERE id=?)',('done' if sys.argv[4]=='1' else 'running',sys.argv[2])); db.commit()",db,job,stage,done?'1':'0']);
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:900}});
try{
 await page.goto(process.env.H3_TEST_URL||'http://127.0.0.1:8789');
 for(const [intent,label] of Object.entries({create:'Creazione immagine',edit:'Modifica immagine',music:'Generazione musica',chat:'Scrittura nel canvas'})){
  await page.click('[data-chat="'+cfg[intent].chat+'"]');const article=page.locator('#msg-'+cfg[intent].message);
  await page.waitForFunction(id=>!!document.querySelector('#msg-'+id+' .generation-activity'),cfg[intent].message);
  assert.equal(await article.locator('.generation-activity strong').innerText(),label);
  assert.match(await article.locator('.activity-stage').innerText(),/Caricamento modello/);
  assert.match(await article.locator('.activity-elapsed').innerText(),/Tempo trascorso/);
  change(cfg[intent].job,intent==='music'?'Composizione musicale e sintesi YuE2':'Generazione immagine · 3/25 passi');
  await page.waitForFunction(({id,text})=>document.querySelector('#msg-'+id+' .activity-stage')?.textContent.includes(text),{id:cfg[intent].message,text:intent==='music'?'YuE2':'3/25'});
  if(intent==='music')await page.screenshot({path:new URL('../work/qa-v09/music-wait.png',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1')});
  change(cfg[intent].job,'Completato',true);await page.waitForFunction(id=>!document.querySelector('#msg-'+id+' .generation-activity'),cfg[intent].message);
 }
 console.log('Activity UI passed: image/edit/music/canvas labels, live phase and step updates, elapsed time and indicator removed after completion.');
}finally{await browser.close();}
