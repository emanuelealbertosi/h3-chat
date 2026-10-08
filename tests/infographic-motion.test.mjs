import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const context={};vm.runInNewContext(readFileSync(new URL('../static/infographic-motion.js',import.meta.url),'utf8'),context);
function scene(start,duration){const style={values:{},setProperty(k,v){this.values[k]=v;}};const element={dataset:{motion:'fade',start:String(start),duration:String(duration)},style};return {element,doc:{querySelectorAll:()=>[element],defaultView:{getComputedStyle:()=>({opacity:'1',transform:'none',filter:'none',clipPath:'none'})}}};}
test('late entrances fit the measured scene and finish before its cut',()=>{const {element,doc}=scene(5,1);context.H3Motion.apply(doc,1.9,2);assert.equal(element.style.values.opacity,'1');context.H3Motion.apply(doc,0,2);assert.equal(element.style.values.opacity,'0');});
test('valid choreography keeps its original timing',()=>{const {element,doc}=scene(.3,1);context.H3Motion.apply(doc,.2,4);assert.equal(element.style.values.opacity,'0');context.H3Motion.apply(doc,.8,4);assert.ok(Math.abs(Number(element.style.values.opacity)-.5)<.001);context.H3Motion.apply(doc,1.4,4);assert.equal(element.style.values.opacity,'1');});

function panels(count=3){
 const elements='123456'.slice(0,count).split('').map(panel=>({dataset:{panel,motion:'zoom'},tagName:'SECTION',style:{values:{},setProperty(k,v){this.values[k]=v;}},querySelectorAll:()=>[]}));
 const body={children:[...elements],style:{setProperty(){}},append(e){this.children=this.children.filter(x=>x!==e);this.children.push(e);}};
 const doc={body,querySelectorAll:()=>elements,defaultView:{innerWidth:1280,innerHeight:720,getComputedStyle:e=>({opacity:e.style.values.opacity||'1',transform:'none',filter:'none',clipPath:'none'})}};
 return {elements,doc};
}
test('three panels preserve physical positions for every entrance order',()=>{
 for(const order of ['123','132','213','231','312','321']){
  const {elements,doc}=panels();context.H3Motion.screen(doc,{layout:'columns3',panel_appearance:'sequence',panel_order:order,panel_interval:.8},5);
  assert.deepEqual(elements.map(e=>Number.parseFloat(e.style.values.left)),[0,1280/3,2560/3]);
  context.H3Motion.apply(doc,.2,5);for(const e of elements)assert.equal(Number(e.style.values.opacity)>0,e.dataset.panel===order[0]);
  context.H3Motion.apply(doc,1,5);for(const e of elements)assert.equal(Number(e.style.values.opacity)>0,order.slice(0,2).includes(e.dataset.panel));
  context.H3Motion.apply(doc,2.8,5);for(const e of elements)assert.equal(e.style.values.opacity,'1');
 }
});
test('short scenes compress panel gaps but retain the chosen order',()=>{
 const {elements,doc}=panels();context.H3Motion.screen(doc,{layout:'rows3',panel_appearance:'sequence',panel_order:'321',panel_interval:5},1);
 assert.deepEqual(elements.map(e=>e.dataset.start),['0.75','0.375','0']);assert.deepEqual(elements.map(e=>e.style.values.top),['0px','240px','480px']);
 context.H3Motion.apply(doc,.95,1);for(const e of elements)assert.equal(e.style.values.opacity,'1');
});
test('requested panel gaps stay intact when all entrances fit the scene',()=>{
 const {elements,doc}=panels();context.H3Motion.screen(doc,{layout:'rows3',panel_appearance:'sequence',panel_order:'123',panel_interval:5},15);
 assert.deepEqual(elements.map(e=>e.dataset.start),['0','5','10']);
});
test('four and six panel grids tile the viewport and honor arbitrary entrance orders',()=>{
 for(const [layout,cols,rows,order] of [['grid2x2',2,2,'2413'],['grid3x2',3,2,'362514'],['grid2x3',2,3,'654321']]){
  const count=cols*rows,{elements,doc}=panels(count);context.H3Motion.screen(doc,{layout,panel_appearance:'sequence',panel_order:order,panel_interval:1},10);
  assert.equal(context.H3Motion.panelCount(layout),count);
  for(let i=0;i<count;i++){const css=elements[i].style.values;assert.equal(parseFloat(css.left),i%cols*1280/cols);assert.equal(parseFloat(css.top),Math.floor(i/cols)*720/rows);assert.equal(parseFloat(css.width),1280/cols);assert.equal(parseFloat(css.height),720/rows);}
  context.H3Motion.apply(doc,.2,10);assert.deepEqual(elements.filter(e=>Number(e.style.values.opacity)>0).map(e=>e.dataset.panel),[order[0]]);
  context.H3Motion.apply(doc,8,10);assert.ok(elements.every(e=>e.style.values.opacity==='1'));
 }
});
test('panel entrances remain active even when early panels contain many animated decorations',()=>{
 const {elements,doc}=panels(6),children=Array.from({length:180},()=>scene(0,.3).element);doc.querySelectorAll=selector=>selector==='[data-panel]'?elements:[elements[0],...children,...elements.slice(1)];
 context.H3Motion.screen(doc,{layout:'grid3x2',panel_appearance:'sequence',panel_order:'654321',panel_interval:.4},5);context.H3Motion.apply(doc,.2,5);
 assert.equal(Number(elements[5].style.values.opacity)>0,true);assert.equal(elements[0].style.values.opacity,'0');
});

function clockScene(ids){
 const {elements,doc}=panels(),slots=ids.filter(Boolean).map((id,i)=>({dataset:{videoAssetId:id},closest:()=>elements[i]}));
 doc.querySelectorAll=selector=>selector==='[data-panel]'?elements:selector==='[data-motion]'?doc.body.children:slots;
 return doc;
}
test('delayed clocks distinguish one clip in different panels and continue across scenes',()=>{
 const docs=[clockScene(['same','same',null]),clockScene(['same','same','later'])];
 const motion={durations:[4,4],options:{layout:'columns3',panel_appearance:'sequence',panel_order:'231',panel_interval:.8,video_start:'panel'},videos:[{asset_id:'same'},{asset_id:'later'}]};
 const clocks=Array.from(context.H3Motion.videoTracks(docs,motion));
 assert.deepEqual(clocks.map(c=>[c.asset_id,c.start]),[['same',1.6],['same',0],['later',4.8]]);assert.notEqual(clocks[0].key,clocks[1].key);
 motion.options.video_start='together';assert.deepEqual(Array.from(context.H3Motion.videoTracks(docs,motion)).map(c=>[c.asset_id,c.start]),[['same',0],['later',0]]);
});
