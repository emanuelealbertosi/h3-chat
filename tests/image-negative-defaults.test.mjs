import test from 'node:test';
import assert from 'node:assert/strict';
import {migrateMossNegativeDefaults} from '../ui/image-negative-defaults.js';
import {imageRequestValues,imageRequestParameters} from '../ui/image-request.js';

test('MOSS blank legacy controls adopt default once; custom and later empty negatives survive',()=>{
 const state={models:[{id:'moss-int8',architecture:'moss'},{id:'moss-bf16',architecture:'moss'},{id:'qwen',architecture:'qwen-edit'}],
  image_options:{moss_negative_prompt:'general negative'},settings:{width:1024,height:1024,steps:30,image_cfg:3,image_sampler:'euler',image_scheduler:'simple',seed:42,strength:.65,negative_prompt:''}};
 const before={image_model:'moss-int8',image_presets:{'moss-int8':{negative_prompt:'',steps:24},'moss-bf16':{negative_prompt:'custom'},qwen:{negative_prompt:''}}};
 const value=migrateMossNegativeDefaults(before,state);
 assert.equal(before.image_presets['moss-int8'].negative_prompt,'');
 assert.equal(imageRequestValues(state,value).negative_prompt,'general negative');
 assert.equal(imageRequestParameters(state,value).negative_prompt,'general negative');
 assert.equal(value.image_presets['moss-int8'].steps,24);
 assert.equal(value.image_presets['moss-bf16'].negative_prompt,'custom');
 assert.equal(value.image_presets.qwen.negative_prompt,'');
 const cleared={...value,image_presets:{...value.image_presets,'moss-int8':{...value.image_presets['moss-int8'],negative_prompt:''}}};
 assert.equal(migrateMossNegativeDefaults(cleared,state),cleared);
 assert.equal(imageRequestParameters(state,cleared).negative_prompt,'');
 assert.equal(imageRequestValues(state,{image_model:'qwen'}).negative_prompt,'');
});
