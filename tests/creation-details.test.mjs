import {test} from 'node:test';
import assert from 'node:assert/strict';
import {imageRecipeParameters,imageRecipePrompt} from '../ui/creation-details.js';

test('reuse takes the selected image seed including zero and only sampling controls',()=>{
 const p=imageRecipeParameters({kind:'image',reusable:true,parameters:{seed:0,width:1024,height:576,steps:25,cfg:1,sampler:'euler',scheduler:'simple',negative_prompt:'',model_file:'weights',seconds:10}});
 assert.equal(p.seed,0);assert.equal(p.width,1024);assert.equal(p.negative_prompt,'');assert.equal(p.seconds,undefined);assert.equal(p.model_file,undefined);
});
test('unavailable recipes and unknown effective seeds do not silently use defaults',()=>{
 assert.throws(()=>imageRecipeParameters({kind:'image',reusable:false,warnings:['Modello non disponibile']}),/Modello non disponibile/);
 assert.throws(()=>imageRecipeParameters({kind:'image',reusable:true,parameters:{seed:-1}}),/Seed effettivo/);
});
test('the historical random directive cannot override the recovered fixed seed',()=>{
 const r={kind:'image',reusable:true,parameters:{seed:0}};
 for(const prompt of ['Una pera, seed casuale','Una pera, seed -1','Una pera, seed randomico'])assert.equal(imageRecipePrompt({...r,prompt}),'Una pera, seed 0');
 assert.equal(imageRecipePrompt({...r,prompt:'Una pera, seed: 0'}),'Una pera, seed: 0');
});
