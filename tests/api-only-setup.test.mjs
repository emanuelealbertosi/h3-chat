import {test} from 'node:test';
import assert from 'node:assert/strict';
import {apiOnlySettings,apiOnlyCard} from '../ui/api-only-setup.js';

test('API setup on a PC without GPU keeps only ready API providers and forces CPU for RAG',()=>{
 const models=[{id:'local-chat',ready:true,capabilities:['chat']},{id:'local-image',ready:true,capabilities:['create','edit']},{id:'api-chat',api:true,ready:true,capabilities:['chat']},{id:'remote-image',remote_media:true,ready:true,capabilities:['create','edit']},{id:'remote-video',remote_media:true,ready:true,capabilities:['video']},{id:'unready',remote_media:true,ready:false,capabilities:['music']}];
 const draft={chat_model:'local-chat',create_model:'local-image',music_model:'yue2-q8',music_quality:'high',profile:'balanced',backend:'cuda',rag_device:'gpu',rag_embedding_model:'X:/rag/model'};
 const patch=apiOnlySettings(draft,models);
 assert.equal(patch.profile,'cpu');assert.equal(patch.backend,'cpu');assert.equal(patch.rag_device,'cpu');
 assert.equal(patch.chat_model,'api-chat');assert.equal(patch.create_model,'remote-image');assert.equal(patch.edit_model,'remote-image');assert.equal(patch.video_model,'remote-video');assert.equal(patch.music_model,'');assert.equal(patch.diagram_model,'');
 assert.equal(patch.music_quality,'model');assert.equal(patch.memory_policy,'on_demand');assert.equal(patch.transcribe_auto,false);assert.equal(patch.voice_auto,false);
 assert.equal(draft.profile,'balanced');assert.equal(draft.rag_embedding_model,'X:/rag/model');assert.ok(!('rag_embedding_model' in patch));
});

test('API shortcut preserves chosen provider and never fabricates an available model',()=>{
 const models=['first','selected'].map(id=>({id,api:true,ready:true,capabilities:['chat']}));
 assert.equal(apiOnlySettings({chat_model:'selected'},models).chat_model,'selected');
 assert.equal(apiOnlySettings({},[]).chat_model,'');
 assert.match(apiOnlyCard,/id="setup-api-only"/);assert.match(apiOnlyCard,/RAG reste? local|RAG resta locale/);
});
