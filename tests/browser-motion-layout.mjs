import {createRequire} from 'node:module';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
try{
 const page=await browser.newPage({viewport:{width:1280,height:720}});await page.setContent('<div data-h3-motion-root></div>');await page.addScriptTag({content:await readFile('static/infographic-scene.js','utf8')});
 const result=await page.evaluate(async()=>{
  const scene={version:2,id:'layout',width:1280,height:720,duration:10,background:'#FFFFFF',objects:[
   {id:'heading',type:'group',width:900,height:90,parallax:0,anchor:{x:.5,y:.5},transform:{x:640,y:65}},
   {id:'title',parentId:'heading',type:'text',width:900,height:70,anchor:{x:.5,y:.5},transform:{x:450,y:45},text:'Un titolo leggibile',fontSize:40},
   {id:'count',type:'counter',width:400,height:80,parallax:0,transform:{x:70,y:300},text:'Carico {value}',unit:'%',value:0,maxValue:100,fontSize:40,tracks:[{property:'barValue',keyframes:[{t:0,value:0},{t:5,value:42},{t:10,value:84}]}]},
   {id:'decor',type:'ellipse',width:200,height:200,transform:{x:-80,y:450},fill:'#DDEEFF'}],camera:{keyframes:[{t:0,x:640,y:360,zoom:1},{t:10,x:700,y:360,zoom:1.3}]}};
  await H3SceneGraph.prepare(document,scene);H3SceneGraph.checkTextBounds(document,5);
  const counter=document.querySelector('[data-h3-motion-object="count"] text').textContent;
  const box=()=>{const r=document.querySelector('[data-h3-motion-object="title"] text').getBoundingClientRect();return [r.x,r.y,r.width,r.height];};
  H3SceneGraph.apply(document,0);const before=box();H3SceneGraph.apply(document,10);const after=box();
  const broken=structuredClone(scene);broken.objects[1].transform={x:0,y:0};await H3SceneGraph.prepare(document,broken);let error='';try{H3SceneGraph.checkTextBounds(document,5);}catch(e){error=e.message;}
  const overlap=structuredClone(scene);overlap.objects.push({...structuredClone(overlap.objects[2]),id:'duplicate'});await H3SceneGraph.prepare(document,overlap);let overlapError='';try{H3SceneGraph.checkTextBounds(document,5);}catch(e){overlapError=e.message;}
  return {counter,before,after,error,overlapError};
 });
 assert.equal(result.counter,'Carico 42%');assert.match(result.error,/title.*testo fuori dal viewport/);assert.match(result.overlapError,/testi sovrapposti/);for(let i=0;i<4;i++)assert.ok(Math.abs(result.before[i]-result.after[i])<.1,JSON.stringify(result));
 console.log('PASS: rendered counter template, stable HUD under camera zoom, clipped nested title rejected; offscreen decoration allowed.');
}finally{await browser.close();}
