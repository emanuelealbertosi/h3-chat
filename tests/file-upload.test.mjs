import test from 'node:test';
import assert from 'node:assert/strict';
import {uploadFile} from '../ui/file-upload.js';

globalThis.FileReader=class{
 readAsDataURL(blob){blob.arrayBuffer().then(bytes=>{this.result='data:application/octet-stream;base64,'+Buffer.from(bytes).toString('base64');this.onload();});}
};

test('large arbitrary-format uploads send only bounded sequential pieces',async()=>{
 const unit=new Blob([new Uint8Array(1024**2)]),file=new Blob(Array(65).fill(unit));file.name='sample.unusual';
 let received=0,parts=0;const id='a'.repeat(32),progress=[];
 const api=async(path,body)=>{
  if(path==='/uploads/start'){assert.equal(body.size,65*1024**2);assert.equal(body.name,file.name);assert.equal(body.data,undefined);return {id,chunk_bytes:2*1024**2};}
  if(path.endsWith('/chunk')){assert.equal(body.offset,received);const raw=Buffer.from(body.data,'base64');assert.ok(raw.length<=2*1024**2);received+=raw.length;parts++;return {received};}
  assert.ok(path.endsWith('/finish'));assert.equal(received,file.size);return {id,mime:'application/octet-stream'};
 };
 const result=await uploadFile(file,{api,onProgress:bytes=>progress.push(bytes)});
 assert.equal(result.id,id);assert.equal(parts,33);assert.equal(progress.at(-1),file.size);
});

test('a failed piece cancels staging and does not finish',async()=>{
 const calls=[],id='b'.repeat(32);let sliceSize;
 const file={name:'terabyte.bin',size:1024**4,slice:(start,end)=>{sliceSize=end-start;return new Blob(['x']);}};
 await assert.rejects(uploadFile(file,{api:async(path,body,method)=>{
  calls.push([path,method]);if(path==='/uploads/start')return {id,chunk_bytes:2*1024**2};
  if(path.endsWith('/chunk'))throw Error('Disco pieno');return {ok:true};
 }}),/Disco pieno/);
 assert.equal(sliceSize,2*1024**2);assert.deepEqual(calls.at(-1),['/uploads/'+id,'DELETE']);assert.ok(!calls.some(([p])=>p.endsWith('/finish')));
});
