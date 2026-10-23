import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {canvasFingerprint,revisionDraft,slideProgress,savedCanvasArtifact} from '../ui/slide-generation-state.js';
import {logoutAccount} from '../ui/account-session.js';

test('canvas controls refresh when the same HTML changes from busy to terminal or progress changes',()=>{
 const value={id:'artifact',title:'Slide',content:'same HTML',media:[]},job={id:'job',chat_id:'chat',status:'running',stage:'Pagina 2 · 40 caratteri'};
 const busy=canvasFingerprint(value,[job],'chat');
 assert.notEqual(busy,canvasFingerprint(value,[{...job,stage:'Pagina 2 · 200 caratteri'}],'chat'));
 assert.notEqual(busy,canvasFingerprint(value,[{...job,status:'done'}],'chat'));
 assert.equal(canvasFingerprint(value,[{...job,status:'done'}],'chat'),canvasFingerprint(value,[],'chat'));
 assert.notEqual(busy,canvasFingerprint(value,[{...job,status:'cancelling'}],'chat'));
});

test('slide progress counts missing pages and exposes progressive HTML size honestly',()=>{
 const deck={pages:[{status:'ready',html:'<h1>Ready</h1>'},{status:'writing',html:'<h1>Growing'},{status:'pending',html:''}]};
 assert.deepEqual(slideProgress(deck,1,null),{missing:2,text:'Generazione interrotta · 1/3 slide complete. Le pagine già pronte restano salvate.'});
 const progress=slideProgress(deck,1,{stage:'Slide 2 · generazione'});assert.equal(progress.missing,2);assert.match(progress.text,/pagina 2 · 11 caratteri in anteprima/);
 assert.equal(slideProgress({pages:[{status:'ready',html:'done'}]},0,null).text,'');
});

test('resume and revision use the saved working copy when persisting changes creates a new artifact',async()=>{
 let current={artifactId:'generated',chatId:'chat',selection:3};
 const id=await savedCanvasArtifact('generated',()=>({...current}),async()=>{current.artifactId='saved-working-copy';});
 assert.equal(id,'saved-working-copy');
});
test('changing canvas selection or chat during save never targets the newly selected deck',async()=>{
 for(const update of [{artifactId:'another',selection:4},{chatId:'other-chat'}]){
  let current={artifactId:'generated',chatId:'chat',selection:3};
  await assert.rejects(savedCanvasArtifact('generated',()=>({...current}),async()=>{current={...current,...update};}),/selezione è cambiata/);
 }
 let persisted=false;await assert.rejects(savedCanvasArtifact('old',()=>({artifactId:'new'}),async()=>persisted=true),/presentazione è cambiata/);assert.equal(persisted,false);
 let current={artifactId:'generated',chatId:'chat',selection:3};
 await assert.rejects(savedCanvasArtifact('generated',()=>({...current}),async()=>persisted=true,async()=>{current.selection++;}),/selezione è cambiata/);assert.equal(persisted,false);
});

class Element{
 constructor(tag){this.tag=tag;this.children=[];this.disabled=false;this.hidden=false;this.value='';}
 append(...elements){this.children.push(...elements);}
}
const document={createElement:tag=>new Element(tag)};
const source=(await readFile(new URL('../ui/slide-ai.js',import.meta.url),'utf8')).replace(/^import .*;\r?$/gm,'').replace(/export function /g,'function ');
const mount=vm.runInNewContext(source+';mountSlideRevision',{document,revisionDraft});
const find=(element,tag)=>element.tag===tag?element:element.children.map(child=>typeof child==='object'?find(child,tag):null).find(Boolean);
function panel(selected,callback,editable=true,status='ready'){
 const target=new Element('div');mount(target,selected,{status},{editable,onRegenerate:callback});
 return {target,input:find(target,'textarea'),button:find(target,'button'),form:find(target,'form'),error:find(target,'p')};
}
test('revision prompts stay attached to their own page when switching freely',()=>{
 const selected={index:0};const first=panel(selected,async()=>{});first.input.value='Two columns';first.input.oninput();
 selected.index=1;const second=panel(selected,async()=>{});assert.equal(second.input.value,'');second.input.value='Blue background';second.input.oninput();
 selected.index=0;assert.equal(panel(selected,async()=>{}).input.value,'Two columns');selected.index=1;assert.equal(panel(selected,async()=>{}).input.value,'Blue background');
});
test('revision submission captures its original page and resets controls after success',async()=>{
 const selected={index:0};revisionDraft(selected,1).prompt='Keep page two';let finish,captured;
 const view=panel(selected,(index,prompt)=>{captured={index,prompt};return new Promise(resolve=>finish=resolve);});view.input.value='Fix page one';view.input.oninput();
 const pending=view.form.onsubmit({preventDefault(){}});assert.equal(view.button.disabled,true);assert.equal(view.input.disabled,true);assert.equal(selected.follow,true);
 selected.index=1;finish();await pending;assert.deepEqual(captured,{index:0,prompt:'Fix page one'});
 assert.equal(view.button.disabled,false);assert.equal(view.input.disabled,false);assert.equal(revisionDraft(selected,0).prompt,'');assert.equal(revisionDraft(selected,1).prompt,'Keep page two');
});
test('revision failure preserves page instructions and reenables retry; terminal writing pages can be fixed',async()=>{
 const selected={index:0},view=panel(selected,async()=>{throw Error('Provider unavailable');},true,'writing');
 assert.equal(view.button.disabled,false);view.input.value='Rework layout';view.input.oninput();await view.form.onsubmit({preventDefault(){}});
 assert.equal(view.error.hidden,false);assert.equal(view.error.textContent,'Provider unavailable');assert.equal(view.button.disabled,false);assert.equal(revisionDraft(selected).prompt,'Rework layout');
 assert.equal(panel(selected,async()=>{},false).button.disabled,true);
});

test('logout preserves changes then revokes the authenticated session with its exact CSRF token',async()=>{
 const events=[],request=async(path,options)=>{events.push(path);if(path.endsWith('/me'))return{ok:true,json:async()=>({configured:true,user:{id:'owner'},csrf:'correct-session'})};assert.equal(options.headers['X-H3-Token'],'correct-session');assert.equal(options.method,'POST');return{ok:true,json:async()=>({ok:true})};};
 await logoutAccount({request,before:async()=>events.push('save'),clear:()=>events.push('clear'),navigate:path=>events.push(path)});
 assert.deepEqual(events,['save','/api/auth/me','/api/auth/logout','clear','/login']);
});
test('failed logout keeps the current page/session data; unconfigured account goes to setup',async()=>{
 const events=[];await assert.rejects(logoutAccount({request:async path=>({ok:path.endsWith('/me'),json:async()=>path.endsWith('/me')?{configured:true,user:{},csrf:'token'}:{error:'Not logged out'}}),clear:()=>events.push('clear'),navigate:path=>events.push(path)}),/Not logged out/);assert.deepEqual(events,[]);
 await logoutAccount({request:async()=>({ok:true,json:async()=>({configured:false,user:null})}),navigate:path=>events.push(path)});assert.deepEqual(events,['/access']);
});
