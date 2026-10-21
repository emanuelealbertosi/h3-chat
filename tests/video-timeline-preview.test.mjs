import test from 'node:test';
import assert from 'node:assert/strict';
import {previewTime,previewPosition} from '../ui/video-timeline-preview.js';

test('global times map to the chosen clip and its source-local offset',()=>{
 const clips=[{clip:21,start:300,end:315,preview_start:300,url:'original.mp4'},
              {clip:22,start:315,end:330,preview_start:0,url:'edited.mp4'}];
 assert.equal(previewPosition(clips,314.5).mediaTime,314.5);
 const cut=previewPosition(clips,315);assert.equal(cut.clip.clip,22);assert.equal(cut.mediaTime,0);
 assert.equal(previewPosition(clips,320).mediaTime,5);
 clips[1].preview_start=315;clips[1].url='original.mp4';
 assert.equal(previewPosition(clips,320).mediaTime,320);
 assert.equal(previewPosition(clips,999).time,330);
});
test('preview range accepts clock values, including long uploaded films',()=>{
 assert.equal(previewTime('1:30'),90);assert.equal(previewTime('1:02:03.5'),3723.5);
 assert.equal(previewTime('0:15,25'),15.25);assert.equal(previewTime('75'),75);
 for(const bad of ['', '-1','1:60','1:99:00','x','NaN','Infinity'])assert.throws(()=>previewTime(bad));
});
