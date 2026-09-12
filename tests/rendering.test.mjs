import test from 'node:test';
import assert from 'node:assert/strict';
import {validateChart} from '../ui/chart-schema.js';
test('preserves quantitative coordinates and discards executable options',()=>{
 const spec=validateChart({type:'scatter',datasets:[{label:'x²',data:[{x:-2,y:4},{x:0,y:0},{x:2,y:4}],onclick:'alert(1)'}],options:{plugins:'evil'}});
 assert.deepEqual(spec.datasets[0].data,[{x:-2,y:4},{x:0,y:0},{x:2,y:4}]);assert.equal(spec.options,undefined);assert.equal(spec.datasets[0].onclick,undefined);
});
test('rejects fabricated or mismatched series and nonfinite values',()=>{
 for(const data of [[1,'2'],[1,NaN],[1,Infinity]])assert.throws(()=>validateChart({type:'line',labels:['A','B'],datasets:[{data}]}));
 assert.throws(()=>validateChart({type:'bar',labels:['A'],datasets:[{data:[1,2]}]}));
 assert.throws(()=>validateChart({type:'pie',labels:['A'],datasets:[{data:[-1]}]}));
});
