import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import '../static/infographic-scene.js';
const {validate,evaluateSceneAt}=globalThis.H3SceneGraph;
const fixture=()=>JSON.parse(readFileSync(new URL('./fixtures/motion-scene-v2.json',import.meta.url),'utf8'));

test('absolute scene time has identical state after forward, backward and repeated seeks',()=>{
 const scene=fixture(),before=structuredClone(scene),reference=evaluateSceneAt(scene,4.5);
 evaluateSceneAt(scene,0);assert.deepEqual(evaluateSceneAt(scene,4.5),reference);
 evaluateSceneAt(scene,9);assert.deepEqual(evaluateSceneAt(scene,4.5),reference);
 assert.deepEqual(evaluateSceneAt(JSON.parse(JSON.stringify(scene)),4.5),reference);
 assert.deepEqual(evaluateSceneAt(scene,4.5),reference);assert.deepEqual(scene,before);
 assert.equal(reference.objects[0].x,440);assert.equal(reference.objects[1].rotation,81);
 assert.equal(reference.camera.x,1005);assert.equal(reference.camera.zoom,1.025);
});
test('interpolation, base values and hold endpoints remain independent of scene length',()=>{
 const scene=fixture();const state=evaluateSceneAt(scene,.6);
 assert.equal(state.objects[0].x,255);assert.equal(state.objects[0].y,610);
 assert.equal(evaluateSceneAt(scene,-3).time,0);assert.equal(evaluateSceneAt(scene,30).time,10);
 const extended=fixture();extended.duration=100;assert.deepEqual(evaluateSceneAt(extended,4.5),evaluateSceneAt(scene,4.5));
});
test('bad IDs, active properties, nonfinite values and invalid timestamps are rejected',()=>{
 for(const change of [s=>s.objects[0].transform.x=NaN,s=>s.objects[0].onclick='alert(1)',s=>s.objects[1].id='rack',s=>s.objects[0].parentId='missing',s=>s.objects[0].tracks[0].keyframes[1].t=11,s=>s.objects[0].fill='url(https://example.invalid)']){
  const scene=fixture();change(scene);assert.throws(()=>validate(scene),/Motion Graphics/);
 }
 assert.throws(()=>evaluateSceneAt(fixture(),Infinity),/time/);
});
test('new scenes preserve all 200 objects beyond the legacy animation node cap',()=>{
 const scene=fixture(),object=scene.objects[0];scene.objects=Array.from({length:200},(_,i)=>({...structuredClone(object),id:'rack_'+i}));
 assert.equal(evaluateSceneAt(scene,4.5).objects.length,200);
});
