import assert from 'node:assert/strict';
import {chatActivities,chatActivityIcon} from '../ui/chat-activity.js';
const jobs=[{chat_id:'a',status:'queued'},{chat_id:'a',status:'running'},{chat_id:'b',status:'queued'},{chat_id:'c',status:'done'},{chat_id:'d',status:'failed'}];
assert.deepEqual([...chatActivities(jobs)],[['a','running'],['b','queued']]);
assert.match(chatActivityIcon('running'),/Generazione in corso/);assert.match(chatActivityIcon('queued'),/Richiesta in coda/);
assert.equal(chatActivityIcon('failed'),'');assert.deepEqual([...chatActivities([])],[]);
console.log('Sidebar activity prioritizes running, distinguishes queued and clears finished jobs.');
