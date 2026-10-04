import test from 'node:test';
import assert from 'node:assert/strict';
import {validateChart} from '../ui/chart-schema.js';
import {chartData} from '../ui/pptx-chart-data.js';
import {validateDesign} from '../ui/slide-design.js';
import {parseColor,composite,contrastRatio,readableColor,colorHex} from '../ui/color-contrast.js';
import {uploadProjectDocument,projectUploadLimits} from '../ui/project-upload.js';
test('preserves quantitative coordinates and discards executable options',()=>{
 const spec=validateChart({type:'scatter',datasets:[{label:'x²',data:[{x:-2,y:4},{x:0,y:0},{x:2,y:4}],onclick:'alert(1)'}],options:{plugins:'evil'}});
 assert.deepEqual(spec.datasets[0].data,[{x:-2,y:4},{x:0,y:0},{x:2,y:4}]);assert.equal(spec.options,undefined);assert.equal(spec.datasets[0].onclick,undefined);
});
test('PowerPoint scatter preserves distinct X coordinates, duplicates and zero values',()=>{
 const result=chartData('scatter',[{label:'A',data:[{x:-2,y:4},{x:0,y:0},{x:0,y:2},{x:2,y:4}]},{label:'B',data:[{x:-1,y:1},{x:1,y:1}]}],[]);
 assert.deepEqual(result[0].values,[-2,-1,0,0,1,2]);assert.deepEqual(result[1].values,[4,null,0,2,null,4]);assert.deepEqual(result[2].values,[null,1,null,null,1,null]);
});
test('graphical slide edits accept bounded design values and reject executable styles',()=>{
 const deck={theme:'indigo',pages:[{nodes:[{id:'n1'}],overrides:{n1:{x:30,width:600,font_size:30,color:'#123456',font:'Manrope'}}}]};validateDesign(deck);
 for(const value of [{width:Infinity},{x:9000},{color:'url(evil)'},{font:'javascript'},{unknown:1}])assert.throws(()=>validateDesign({...deck,pages:[{nodes:[{id:'n1'}],overrides:{n1:value}}]}));
});
test('rejects fabricated or mismatched series and nonfinite values',()=>{
 for(const data of [[1,'2'],[1,NaN],[1,Infinity]])assert.throws(()=>validateChart({type:'line',labels:['A','B'],datasets:[{data}]}));
 assert.throws(()=>validateChart({type:'bar',labels:['A'],datasets:[{data:[1,2]}]}));
 assert.throws(()=>validateChart({type:'pie',labels:['A'],datasets:[{data:[-1]}]}));
});
test('slide style and full text controls reject malformed metadata',()=>{
 const deck={design:'comic',detail:'full',pages:[{nodes:[]}]};validateDesign(deck);
 for(const value of [{design:['comic']},{theme:['lagoon']},{detail:true},{pages:[{nodes:[],overrides:null}]}])assert.throws(()=>validateDesign({...deck,...value}));
});
test('contrast measures sRGB luminance, alpha and foreground opacity',()=>{
 assert.equal(contrastRatio(parseColor('#000'),parseColor('#fff')),21);
 const percent=parseColor('rgb(100% 0% 0% / 50%)');assert.ok(Math.abs(percent[0]-255)<1e-9);assert.deepEqual(percent.slice(1),[0,0,.5]);
 assert.deepEqual(composite(parseColor('#ffffff80'),parseColor('#000')), [128,128,128,1]);
 assert.ok(contrastRatio(parseColor('#fff'),parseColor('#000'),.5)<21);
 const source=parseColor('#163e48');assert.equal(readableColor(source,parseColor('#fff')),source);
});
test('automatic foreground correction preserves hue and fixes unsafe combinations',()=>{
 for(const [fg,bg,alpha] of [['#fff','#fff',1],['#000','#000',1],['#fff','#d7ef92',1],['#888','#edf1f5',1],['#b84944','#492a43',1],['#163e48','#fff',.65]]){
   const corrected=readableColor(parseColor(fg),parseColor(bg),alpha);
   assert.ok(contrastRatio(parseColor(colorHex(corrected)),parseColor(bg),alpha)>=4.5,`${fg} on ${bg}`);
 }
 const teal=readableColor(parseColor('#087f8c'),parseColor('#143c45'));assert.ok(teal[1]>teal[0]);
});

test('a book larger than 25 MB is sent as bounded raw blocks with token and progress',async()=>{
 const size=26*1024**2+37,id='1'.repeat(32),calls=[],progress=[];
 const file={name:'book.pdf',size,slice:(start,end)=>new Blob([new Uint8Array(end-start)])};
 const api=async(path,body,method)=>{calls.push({path,body,method});return path.endsWith('/start')?{id,chunk_bytes:projectUploadLimits.upload_chunk_bytes}:{id:'source'};};
 let received=0,count=0;
 const fetcher=async(path,options)=>{
  assert.equal(path,'/api/projects/project/import/'+id);assert.equal(options.method,'PATCH');
  assert.equal(options.headers['X-H3-Offset'],String(received));assert.equal(options.headers['X-H3-Token'],'session');
  assert.equal(options.headers['Content-Type'],'application/octet-stream');assert.ok(options.body instanceof Blob);
  assert.ok(options.body.size<=2*1024**2);received+=options.body.size;count++;
  return {ok:true,json:async()=>({received})};
 };
 const result=await uploadProjectDocument(file,{project:'project',relativePath:'Books/book.pdf',api,getToken:()=> 'session',fetcher,onProgress:(bytes,total)=>progress.push([bytes,total])});
 assert.equal(received,size);assert.equal(count,14);assert.deepEqual(progress.at(-1),[size,size]);
 assert.deepEqual(calls.map(c=>c.path),['/projects/project/import/start','/projects/project/import/'+id+'/finish']);
 assert.equal(calls[0].body.relative_path,'Books/book.pdf');assert.equal(calls[0].body.defer,true);assert.equal(result.id,'source');
});

test('failed or incomplete book blocks are cancelled without publishing a document',async()=>{
 for(const failure of ['response','offset']){
  const id='2'.repeat(32),calls=[];
  const api=async(path,body,method)=>{calls.push({path,method});return {id,chunk_bytes:1024};};
  const file={name:'book.pdf',size:1024,slice:()=>new Blob(['PDF'])};
  await assert.rejects(uploadProjectDocument(file,{project:'project',api,getToken:()=> 'session',fetcher:async()=>({ok:failure!=='response',json:async()=>({error:'Upload failed',received:512})})}));
  assert.equal(calls.length,2);assert.equal(calls[1].method,'DELETE');assert.ok(calls[1].path.endsWith('/'+id));
 }
});

test('book size is checked before creating a transfer',async()=>{
 for(const size of [0,projectUploadLimits.file_bytes+1]){
  let called=false;
  await assert.rejects(uploadProjectDocument({name:'book.pdf',size},{project:'project',api:()=>{called=true;},getToken:()=>''}));
  assert.equal(called,false);
 }
});
