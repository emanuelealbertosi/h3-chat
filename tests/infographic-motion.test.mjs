import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const context={};vm.runInNewContext(readFileSync(new URL('../static/infographic-motion.js',import.meta.url),'utf8'),context);
function scene(start,duration){const style={values:{},setProperty(k,v){this.values[k]=v;}};const element={dataset:{motion:'fade',start:String(start),duration:String(duration)},style};return {element,doc:{querySelectorAll:()=>[element],defaultView:{getComputedStyle:()=>({opacity:'1',transform:'none',filter:'none',clipPath:'none'})}}};}
test('late entrances fit the measured scene and finish before its cut',()=>{const {element,doc}=scene(5,1);context.H3Motion.apply(doc,1.9,2);assert.equal(element.style.values.opacity,'1');context.H3Motion.apply(doc,0,2);assert.equal(element.style.values.opacity,'0');});
test('valid choreography keeps its original timing',()=>{const {element,doc}=scene(.3,1);context.H3Motion.apply(doc,.2,4);assert.equal(element.style.values.opacity,'0');context.H3Motion.apply(doc,.8,4);assert.ok(Math.abs(Number(element.style.values.opacity)-.5)<.001);context.H3Motion.apply(doc,1.4,4);assert.equal(element.style.values.opacity,'1');});
