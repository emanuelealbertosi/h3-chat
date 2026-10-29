import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,readFile} from 'node:fs/promises';
import {build} from 'esbuild';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const folder='work/gallery-library-qa';await mkdir(folder,{recursive:true});
await build({entryPoints:['tests/gallery-browser-entry.js'],outfile:folder+'/harness.js',bundle:true,format:'iife',platform:'browser',target:'es2022'});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_canvas_fixture.py'],{stdio:['ignore','pipe','pipe']});
let diagnostics='';child.stderr.on('data',x=>diagnostics+=x);const lines=createInterface({input:child.stdout});
const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(diagnostics);})]);lines.close();
const fixture=JSON.parse(line),browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']});
const page=await browser.newPage({viewport:{width:1380,height:950}}),errors=[],calls=[];page.on('pageerror',e=>errors.push(e.message));
const items=Array.from({length:65},(_,n)=>({id:(n+1).toString(16).padStart(32,'0'),name:'Film '+String(n+1).padStart(2,'0'),path:'uploads/video-'+n+'.mp4',mime:'video/mp4',size:1024,origin:'generated',url:'/gallery-file/'+(n+1).toString(16).padStart(32,'0'),created:1700000000+n,modified:1700001000-n,video_kind:n===0?'timeline':n===1?'clip':'',clip_count:n===0?64:n===1?3:0}));
let sorting=true;const deletions=[];
await page.exposeFunction('galleryApi',async(path,body)=>{
 if(path==='/gallery/delete-plan')return {count:body.ids.length,bytes:1024*body.ids.length,snapshot:'fixture',can_delete_files:body.ids.every(id=>!items.find(i=>i.id===id)?.timeline_only),items:body.ids.map(id=>({id,file_deletion_allowed:!items.find(i=>i.id===id)?.timeline_only,reason:'La timeline salvata viene conservata.'}))};
 if(path==='/gallery/delete'){deletions.push(body);for(const id of body.ids){const index=items.findIndex(i=>i.id===id);if(index>=0)items.splice(index,1);}return {removed:body.ids,files_preserved:!body.delete_files,files_deleted:body.delete_files?body.ids.length:0,errors:[]};}
 assert(!body,'Browsing/sorting must not submit any changes');calls.push(path);
 const p=new URLSearchParams(path.split('?')[1]),offset=Number(p.get('offset')),sort=p.get('sort');
 let found=items.filter(i=>i.name.toLowerCase().includes((p.get('q')||'').toLowerCase()));
 if(p.get('project_id'))found=p.get('project_id')==='b'.repeat(32)?found.slice(-10):found.slice(0,10);
 found.sort((a,b)=>sort==='added_asc'?a.created-b.created:sort==='added_desc'?b.created-a.created:sort==='name_desc'?b.name.localeCompare(a.name):sort==='modified_asc'?a.modified-b.modified:b.modified-a.modified);
 if(offset)await new Promise(r=>setTimeout(r,150));
 return {items:found.slice(offset,offset+48),offset:offset+48,more:found.length>offset+48,total:found.length,manage:true,sorting,projects:[{id:'a'.repeat(32),name:'Progetto collaudo'},{id:'b'.repeat(32),name:'Altro progetto'}]};
});
try{
 await page.goto(fixture.url);await page.route('**/static/gallery-test.js',async route=>route.fulfill({contentType:'application/javascript',body:await readFile(folder+'/harness.js','utf8')}));await page.addScriptTag({url:fixture.url+'/static/gallery-test.js'});
 const open=()=>page.evaluate(()=>window.galleryFixture.openGallery({api:window.galleryApi,browse:true}));
 // Both gallery entry points and every picker use the current project on
 // opening; a manual project/All selection must survive subsequent loads.
 await page.evaluate(()=>{
  window.galleryProject='a'.repeat(32);
  window.galleryFixture.initGallery({api:window.galleryApi,getAttachments:()=>[],setAttachments:()=>{},notify:()=>{},
   getProjectId:()=>window.galleryProject,getProjects:()=>[{id:'a'.repeat(32),name:'Progetto collaudo'},{id:'b'.repeat(32),name:'Altro progetto'}]});
 });
 await page.locator('#gallery-open').first().click();let scoped=page.locator('.gallery-dialog');await scoped.locator('.gallery-card').first().waitFor();
 assert.equal(new URLSearchParams(calls.at(-1).split('?')[1]).get('project_id'),'a'.repeat(32));
 assert.equal(await scoped.getByLabel('Filtra per progetto').inputValue(),'a'.repeat(32));assert.equal(await scoped.locator('.gallery-card').count(),10);
 await scoped.getByLabel('Filtra per progetto').selectOption('b'.repeat(32));await page.waitForFunction(()=>document.querySelector('.gallery-pick strong')?.textContent==='Film 56');
 await scoped.getByLabel('Ordina la galleria').selectOption('added_desc');await page.waitForFunction(()=>document.querySelector('.gallery-pick strong')?.textContent==='Film 65');
 assert.equal(await scoped.getByLabel('Filtra per progetto').inputValue(),'b'.repeat(32));assert.equal(await scoped.locator('.gallery-card').count(),10);
 await scoped.getByLabel('Filtra per progetto').selectOption('');await page.waitForFunction(()=>document.querySelectorAll('.gallery-card').length===48);
 assert.equal(await scoped.getByLabel('Filtra per progetto').inputValue(),'');await scoped.getByLabel('Chiudi galleria').click();
 await page.evaluate(()=>{window.galleryProject='b'.repeat(32);});await page.locator('#gallery-nav').last().click();scoped=page.locator('.gallery-dialog');await scoped.locator('.gallery-card').first().waitFor();
 assert.equal(await scoped.getByLabel('Filtra per progetto').inputValue(),'b'.repeat(32));assert.equal(await scoped.locator('.gallery-card').count(),10);await scoped.getByLabel('Chiudi galleria').click();
 await page.evaluate(()=>{window.galleryProject='';});
 let eagerVideo=0;page.on('request',r=>{if(r.url().includes('/gallery-file/'))eagerVideo++;});
 await open();let gallery=page.locator('.gallery-dialog');await gallery.locator('.gallery-card').first().waitFor();
 assert.equal(await gallery.locator('.gallery-card').count(),48);assert.equal(eagerVideo,0);
 await gallery.getByLabel('Filtra per progetto').selectOption('a'.repeat(32));await page.waitForFunction(()=>document.querySelectorAll('.gallery-card').length===10);assert(calls.at(-1).includes('project_id='+'a'.repeat(32)));
 await gallery.getByLabel('Filtra per progetto').selectOption('');await page.waitForFunction(()=>document.querySelectorAll('.gallery-card').length===48);
 const timeline=gallery.locator('.gallery-card').first();assert.equal(await timeline.locator('.gallery-video-kind').textContent(),'Timeline · 64 clip');
 assert.match(await timeline.locator('time').textContent(),/^Ultima modifica: /);assert.equal(await timeline.locator('time').getAttribute('datetime'),new Date(items[0].modified*1000).toISOString());
 assert.equal(await gallery.locator('.gallery-card').nth(1).locator('.gallery-video-kind').textContent(),'Spezzone · timeline collegata');
 assert.equal(await gallery.locator('.gallery-card').nth(2).locator('.gallery-video-kind').textContent(),'Video');
 await gallery.getByRole('button',{name:'Altri file',exact:true}).evaluate(b=>{b.click();b.click();});await page.waitForFunction(()=>document.querySelectorAll('.gallery-card').length===65);
 assert.equal(calls.filter(p=>p.includes('offset=48')).length,1);
 await gallery.getByLabel('Ordina la galleria').selectOption('added_desc');await page.waitForFunction(()=>document.querySelector('.gallery-pick strong')?.textContent==='Film 65');
 assert.equal(await gallery.locator('.gallery-card').count(),48);assert(calls.at(-1).includes('sort=added_desc'));assert(calls.at(-1).includes('offset=0'));
 await gallery.getByLabel('Cerca nella galleria').fill('Film 01');await page.waitForFunction(()=>document.querySelectorAll('.gallery-card').length===1);assert(calls.at(-1).includes('sort=added_desc'));
 await gallery.getByRole('button',{name:'Apri Film 01',exact:true}).click();let player=page.locator('.gallery-player');assert.equal(await player.locator('.gallery-video-kind').textContent(),'Timeline · 64 clip');assert.equal(await player.locator('time').count(),1);await player.getByLabel('Chiudi anteprima').click();
 await gallery.getByLabel('Cerca nella galleria').fill('');await gallery.getByLabel('Ordina la galleria').selectOption('modified_desc');await page.waitForFunction(()=>document.querySelectorAll('.gallery-card').length===48);
 await gallery.screenshot({path:folder+'/desktop.png'});
 await page.setViewportSize({width:390,height:844});assert(await gallery.evaluate(e=>e.scrollWidth<=e.clientWidth+2));await gallery.screenshot({path:folder+'/mobile.png'});
 await gallery.getByLabel('Chiudi galleria').click();sorting=false;await open();gallery=page.locator('.gallery-dialog');await gallery.locator('.gallery-card').first().waitFor();assert(await gallery.getByLabel('Ordina la galleria').isDisabled());
 await gallery.getByLabel('Chiudi galleria').click();assert.deepEqual(errors,[]);
 // A stopped timeline is a saved editor resource, never a fake playable MP4.
 sorting=true;items[0]={...items[0],timeline_only:true,timeline_status:'cancelled',completed_clips:20,requested_clips:64,timeline_id:items[0].id,chat_id:'owned-chat',url:null};
 await page.evaluate(()=>{window.timelineOpened=null;window.galleryFixture.openGallery({api:window.galleryApi,onSelect:()=>{throw Error('A timeline cannot be attached as a movie');},actions:{edit:(media,item)=>{window.timelineOpened={media,item};}}});});
 gallery=page.locator('.gallery-dialog');await gallery.locator('.gallery-card').first().waitFor();
 assert.equal(await gallery.locator('.gallery-card').first().locator('.gallery-video-kind').textContent(),'Timeline interrotta · 64 clip');
 assert.equal(await gallery.locator('.gallery-card').first().locator('.gallery-timeline-progress').textContent(),'20 / 64 modifiche completate');
 await gallery.getByRole('button',{name:'Apri Film 01',exact:true}).click();player=page.locator('.gallery-player');
 assert.equal(await player.locator('video').count(),0);assert(await player.locator('[data-download]').isHidden());assert.equal(await player.getByRole('button',{name:'Usa questo file',exact:true}).count(),0);
 assert(await gallery.locator('[data-select]').isDisabled());await page.screenshot({path:folder+'/stopped-timeline.png',fullPage:true});
 await player.getByRole('button',{name:'Apri timeline salvata',exact:true}).click();await page.waitForFunction(()=>window.timelineOpened!==null);
 const opened=await page.evaluate(()=>window.timelineOpened);assert.equal(opened.media.id,items[0].id);assert.equal(opened.item.chat_id,'owned-chat');assert.equal(await page.locator('.gallery-dialog').count(),0);
 assert.deepEqual(errors,[]);
 // Browse mode supports a separate multi-delete selection without attaching assets.
 await open();gallery=page.locator('.gallery-dialog');await gallery.locator('.gallery-card').first().waitFor();
 await gallery.getByLabel('Seleziona per eliminare Film 03',{exact:true}).check();await gallery.getByLabel('Seleziona per eliminare Film 04',{exact:true}).check();
 await gallery.getByRole('button',{name:'Elimina selezionati',exact:true}).click();let confirmation=page.getByRole('dialog',{name:'Elimina asset',exact:true});
 await confirmation.getByRole('button',{name:'Rimuovi dalla galleria',exact:true}).waitFor({state:'visible'});assert(await confirmation.locator('input[value=gallery]').isChecked());
 await confirmation.getByRole('button',{name:'Annulla',exact:true}).click();assert.equal(deletions.length,0);
 await gallery.getByRole('button',{name:'Elimina selezionati',exact:true}).click();confirmation=page.getByRole('dialog',{name:'Elimina asset',exact:true});await confirmation.locator('input[value=files]').check();
 assert.match(await confirmation.locator('[data-warning]').textContent(),/definitivamente/);await confirmation.getByRole('button',{name:'Elimina anche dal disco',exact:true}).click();await confirmation.waitFor({state:'detached'});
 assert.equal(deletions.length,1);assert.equal(deletions[0].ids.length,2);assert.equal(deletions[0].delete_files,true);assert.equal(deletions[0].confirmed,true);assert(await gallery.getByRole('button',{name:'Elimina selezionati',exact:true}).isDisabled());
 await gallery.getByLabel('Seleziona per eliminare Film 01',{exact:true}).check();await gallery.getByRole('button',{name:'Elimina selezionati',exact:true}).click();confirmation=page.getByRole('dialog',{name:'Elimina asset',exact:true});
 await confirmation.getByRole('button',{name:'Rimuovi dalla galleria',exact:true}).waitFor();assert(await confirmation.locator('input[value=files]').isDisabled());await confirmation.getByRole('button',{name:'Annulla',exact:true}).click();
 await page.setViewportSize({width:390,height:844});assert(await gallery.evaluate(e=>e.scrollWidth<=e.clientWidth+2));await gallery.screenshot({path:folder+'/bulk-delete-mobile.png'});
 await gallery.getByLabel('Chiudi galleria').click();assert.deepEqual(errors,[]);
 console.log('PASS: labels/dates/global sorting, pagination/filtering, lazy videos, desktop/mobile, old server, stopped timeline counts and direct open without attachments/exports/generation.');
}finally{await browser.close();child.kill();}
