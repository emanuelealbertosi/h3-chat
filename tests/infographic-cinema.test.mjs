import test from 'node:test';import assert from 'node:assert/strict';
import '../static/infographic-cinema.js';
const {cameraAt,blendAt}=globalThis.H3Cinema;

test('full-frame transition is smooth, short and never fades both layers to the stage color',()=>{
 assert.deepEqual(blendAt([4,4],2),{from:0,to:0,alpha:1});
 assert.deepEqual(blendAt([4,4],6),{from:1,to:1,alpha:1});
 assert.ok(Math.abs(blendAt([4,4],4).alpha-.5)<1e-10);
 let previous=-1;
 for(let t=3.55;t<=4.45;t+=.001){const b=blendAt([4,4],t);assert.equal(b.from,0);assert.equal(b.to,1);assert.ok(b.alpha>=previous);previous=b.alpha;}
 const reference=blendAt([4,4],4.1);blendAt([4,4],1);assert.deepEqual(blendAt([4,4],4.1),reference);
});
test('one camera remains monotonic, continuous in position and velocity, and seekable',()=>{
 const durations=[6,8,5];let last=-Infinity;
 for(let t=0;t<=19;t+=.01){const v=cameraAt(durations,t);assert.ok(v.x>=last-1e-10);last=v.x;assert.ok(v.zoom>=1.025&&v.zoom<=1.05);}
 for(const t of [4.85,6,7.15,12.85,14,15.15]){const h=.00001,l=cameraAt(durations,t-h).x,c=cameraAt(durations,t).x,r=cameraAt(durations,t+h).x;assert.ok(Math.abs((c-l)/h-(r-c)/h)<.001);}
 const reference=cameraAt(durations,6.2);cameraAt(durations,18);assert.deepEqual(cameraAt(durations,6.2),reference);
});
test('short scenes keep a bounded valid continuous camera path',()=>{
 for(const durations of [[.1],[.1,.2],[5,1,3]])for(let t=0;t<durations.reduce((a,b)=>a+b,0);t+=.01){const camera=cameraAt(durations,t);assert.ok(Number.isFinite(camera.x));assert.ok(camera.x>=-.07-1e-9&&camera.x<=durations.length-1+.07+1e-9);}
});
