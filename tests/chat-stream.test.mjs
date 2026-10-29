import test from 'node:test';import assert from 'node:assert/strict';
import {createChatStream} from '../ui/chat-stream.js';

function fixture({read=async()=>({content:'',status:'running'}),reduced=false}={}){
 let stamp=0,next=0;const frames=new Map(),timers=new Map(),painted=[];const container={isConnected:true};
 const stream=createChatStream({read,render:(target,text)=>{painted.push(text);target.text=text;},now:()=>stamp,frame:fn=>{frames.set(++next,fn);return next;},cancelFrame:id=>frames.delete(id),timer:fn=>{timers.set(++next,fn);return next;},cancelTimer:id=>timers.delete(id),reducedMotion:()=>reduced});
 const bind=(text,live=false)=>stream.bind({chat:'chat',id:'message',container,text,live});
 async function step(){stamp+=16;const ready=[...frames.values()];frames.clear();for(const fn of ready)fn(stamp);await Promise.resolve();await Promise.resolve();}
 return {stream,bind,container,painted,frames,timers,step};
}

test('reveals only received text progressively, without rollback from an older poll',async()=>{
 const f=fixture();f.bind('');await f.step();f.bind('abcdefghi');await f.step();assert.ok(f.container.text.length>0&&f.container.text.length<9);assert.ok('abcdefghi'.startsWith(f.container.text));
 f.bind('abc');for(let i=0;i<20;i++)await f.step();assert.equal(f.container.text,'abcdefghi');f.stream.clear();
});
test('final status flushes the received answer without a long typewriter backlog',async()=>{
 const text='A'.repeat(20000),f=fixture({read:async()=>({content:text,status:'done'})});f.bind('',true);for(let i=0;i<4;i++)await f.step();assert.equal(f.container.text,text);assert.equal(f.timers.size,0);f.stream.clear();
});
test('switching chats cancels frames and ignores late network results',async()=>{
 let resolve;const f=fixture({read:()=>new Promise(r=>resolve=r)});f.bind('',true);f.bind('pending');f.stream.retain(new Set());resolve({content:'must not appear',status:'done'});await f.step();assert.notEqual(f.container.text,'must not appear');assert.equal(f.frames.size,0);assert.equal(f.timers.size,0);
});
test('respects reduced motion and keeps emoji surrogate pairs intact',async()=>{
 const f=fixture({reduced:true});f.bind('');await f.step();f.bind('x😀z');await f.step();assert.equal(f.container.text,'x😀z');f.stream.clear();
 const normal=fixture();normal.bind('');await normal.step();normal.bind('x😀z');for(let i=0;i<8;i++){await normal.step();assert.ok(!/[\uD800-\uDBFF]$/.test(normal.container.text));}normal.stream.clear();
});
