import assert from 'node:assert/strict';
import {test} from 'node:test';
import {memoryPatch,endFramePatch} from '../ui/video-edit-memory.js';
import {remapEditorDraft} from '../ui/video-editor-draft.js';
import {reloadEditDraft} from '../ui/video-edit-reload.js';

test('memory is sent only for whole reference clips and supported servers',()=>{
 const item={clip:2,mode:'reference',range:false,recover_memory:true};
 assert.deepEqual(memoryPatch(item,true),{recover_memory:true});
 for(const change of [{clip:1},{mode:'i2v'},{mode:'video'},{range:true}])assert.deepEqual(memoryPatch({...item,...change},true),{recover_memory:false});
 assert.deepEqual(memoryPatch(item,false),{});
});

test('final anchors coexist with memory and follow image identity across reload',()=>{
 const item={clip:2,mode:'reference',range:false,recover_memory:true,end_frame:2};
 assert.deepEqual({...memoryPatch(item,true),...endFramePatch(item,true)},{recover_memory:true,end_frame:2});
 assert.deepEqual(endFramePatch({...item,range:true},true),{end_frame:'none'});
 assert.deepEqual(endFramePatch(item,false),{});
 const state={image_ids:['face','ending'],common_prompt:'',clips:[{prompt:'Continue',images:[1],end_frame:2,anchor_images:{}}]};
 assert.equal(remapEditorDraft(state,[{id:'ending',index:1},{id:'face',index:2}]).clips[0].end_frame,1);
});

test('last launch reload preserves the memory choice without changing legacy drafts',()=>{
 const data={memory_recovery:true,images:[],clips:[{clip:2,start:15,end:30}]};
 const edit={patches:[{clip:2,prompt:'Continue','mode':'reference',images:[],recover_memory:true}],image_ids:[]};
 const options={parameters:{},references:[],assistant:false};
 assert.equal(reloadEditDraft(data,edit,options).state.clips[0].recover_memory,true);
 assert.equal(reloadEditDraft({...data,memory_recovery:false},edit,options).state.clips[0].recover_memory,undefined);
});
