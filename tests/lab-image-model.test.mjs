import assert from 'node:assert/strict';
import {labImageDefault} from '../ui/lab-image-model.js';
const model=(id,architecture,profile,ready=true)=>({id,name:id,architecture,external_config:{profile},ready,capabilities:['create']});
const state={settings:{create_model:'moss'},models:[model('moss','moss','moss'),model('turbo','qwen21','qwen21-turbo'),model('qwen','qwen21','qwen21')]};
assert.equal(labImageDefault(state).id,'qwen');
assert.equal(state.settings.create_model,'moss');
state.models[2].ready=false;assert.equal(labImageDefault(state).id,'moss');
state.models[2].ready=true;state.settings.create_model='qwen';assert.equal(labImageDefault(state).id,'qwen');
console.log('Qwen standard default, unavailable fallback and separate chat preference passed.');
