import assert from 'node:assert/strict';
import {test} from 'node:test';
import {draftSignature,remapEditorDraft} from '../ui/video-editor-draft.js';

test('saved references keep their identity when later versions add and reorder images',()=>{
 const state={image_ids:['face','outfit'],common_prompt:'Use <Picture 2>',clips:[{prompt:'Keep <Picture 1>, wear <Picture 2>',images:[2],start_image:1,anchor_image:null,anchor_images:{first:2,last:1}}]};
 const actual=remapEditorDraft(state,[{id:'new',index:1},{id:'outfit',index:2},{id:'face',index:3}]);
 assert.equal(actual.clips[0].prompt,'Keep <Picture 3>, wear <Picture 2>');assert.deepEqual(actual.clips[0].images,[2]);
 assert.equal(actual.clips[0].start_image,3);assert.deepEqual(actual.clips[0].anchor_images,{first:2,last:3});
 assert.equal(state.clips[0].start_image,1);assert.throws(()=>remapEditorDraft(state,[{id:'face',index:1}]),/non è più disponibile/);
});

test('drafts bind to exact frame intervals rather than merely the number of clips',()=>{
 assert.deepEqual(draftSignature([{start:315,end:330},{start:330,end:335.125}]),[[7560,360],[7920,123]]);
 assert.notDeepEqual(draftSignature([{start:0,end:10},{start:10,end:20}]),draftSignature([{start:0,end:15},{start:15,end:20}]));
});
