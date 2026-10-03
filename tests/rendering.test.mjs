import test from 'node:test';
import assert from 'node:assert/strict';
import {validateChart} from '../ui/chart-schema.js';
import {chartData} from '../ui/pptx-chart-data.js';
import {validateDesign} from '../ui/slide-design.js';
import {parseColor,composite,contrastRatio,readableColor,colorHex} from '../ui/color-contrast.js';
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
