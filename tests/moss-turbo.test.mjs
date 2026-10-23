import test from 'node:test';
import assert from 'node:assert/strict';
import {toggleMossTurbo,mossTurboValues,MOSS_TURBO_RECIPE} from '../ui/moss-turbo.js';

test('Turbo persists across reload and restores prior recipe while keeping new seed and canvas',()=>{
 const normal={steps:30,cfg:4,sampler:'res_multistep',scheduler:'simple',megapixels:2.25,aspect:'16:9',seed:42,negative_prompt:'blurry'};
 const turbo=toggleMossTurbo(normal,true);
 assert.deepEqual(Object.fromEntries(Object.keys(MOSS_TURBO_RECIPE).map(k=>[k,turbo[k]])),MOSS_TURBO_RECIPE);
 assert.equal(normal.steps,30);
 const reloaded=JSON.parse(JSON.stringify({...turbo,seed:73,aspect:'9:16'}));
 const off=toggleMossTurbo(reloaded,false);
 assert.deepEqual(off,{...normal,seed:73,aspect:'9:16',moss_turbo:false});
 assert(!('moss_turbo_previous' in off));
 assert.deepEqual(mossTurboValues({...turbo,steps:99}).steps,8);
 assert.deepEqual(toggleMossTurbo(turbo,true).moss_turbo_previous,turbo.moss_turbo_previous);
});
