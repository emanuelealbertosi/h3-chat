import test from 'node:test';import assert from 'node:assert/strict';
import {workItems,recoveryAdvice} from '../ui/work-center.js';
import {reviewRows} from '../ui/request-review.js';
test('work panel combines only supplied account data, prioritizing active work',()=>{
 const state={chats:[{id:'a',title:'Scuola'}],jobs:[{id:'old',chat_id:'a',status:'running',created:1},{id:'new',chat_id:'a',status:'done',created:30}],downloads:[{id:'rag',status:'running',received:5,total:10,file:'models/embed.bin'}]};
 const items=workItems(state);assert.equal(items[0].id,'old');assert.equal(items[1].kind,'download');assert.equal(items[2].id,'new');assert.equal(items[0].title,'Scuola');assert.equal(items[1].title,'Download · embed.bin');assert.equal(state.jobs[0].kind,undefined);assert.deepEqual(workItems(null),[]);
});
test('review distinguishes no selected sources, all sources and disabled RAG',()=>{
 const source=value=>reviewRows(value).find(([k])=>k==='Fonti RAG')[1];assert.match(source({rag:true,project:'Scuola',rag_sources:[],rag_top_k:9}),/0 documenti selezionati.*9 estratti/);assert.match(source({rag:true,project:'Scuola'}),/tutti i documenti/);assert.equal(source({rag:false,project:'Scuola',rag_sources:['x']}),'Disattivate');assert.equal(source({rag:true}),'Nessun progetto selezionato');
});
test('review exposes requested settings and references without inventing routing',()=>{
 const rows=reviewRows({mode:'Video',models:['Modello A'],media:[{name:'Clip.mp4'}],parameters:[['Durata','3 × 15 s'],['Seed',0]],loras:[{name:'Swap',weight:1}],assistant:false});assert(rows.some(([k,v])=>k==='Seed'&&v===0));assert(rows.some(([k,v])=>k==='Assistant'&&v==='Off'));assert(rows.some(([k,v])=>k==='Allegati'&&v.includes('Clip.mp4')));assert.equal(reviewRows()[1][1],'Automatici · dal prompt');
});
test('recovery recommends checking, without asserting an invented cause or retrying',()=>{
 assert.match(recoveryAdvice('Timeout'),/tempo massimo/);assert.match(recoveryAdvice('out of memory'),/memoria/);assert.match(recoveryAdvice('Formato JSON richiesto'),/formato/);assert.match(recoveryAdvice('Failed to fetch'),/controlla Lavori/);assert.match(recoveryAdvice('Altro errore'),/bozza/);
});
