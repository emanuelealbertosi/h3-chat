import {createRequire} from 'node:module';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']}),page=await browser.newPage({viewport:{width:1280,height:2276}});
const code=(await readFile('ui/infographic-layout.js','utf8')).replace('export function portraitLayout','globalThis.portraitLayout=function');
async function measure(html,height=2276,options={}){await page.setContent('<style>html,body{margin:0;width:1280px;height:'+height+'px;box-sizing:border-box}*{box-sizing:border-box}</style>'+html);await page.evaluate(code);return page.evaluate(({height,options})=>portraitLayout(document,height,options),{height,options});}
try{
 const top='<h1 style="position:absolute;top:90px;font-size:80px">Titolo</h1><div style="position:absolute;top:300px;font-size:40px">Contenuti</div><footer style="position:absolute;top:2150px">Fonte</footer>';
 const sparse=await measure('<div style="position:absolute;inset:0;background:navy"></div>'+top);assert.equal(sparse.issue,true);assert.ok(sparse.gap_ratio>.7);
 const balanced=await measure('<h1 style="position:absolute;top:70px">Titolo</h1>'+[400,900,1400,1850,2160].map(y=>'<p style="position:absolute;top:'+y+'px;font-size:40px">Contenuto distribuito</p>').join(''));assert.equal(balanced.issue,false);
 const wrong=await measure('<style>body{height:720px}</style>'+top);assert.equal(wrong.wrong_size,true);
 const hero=await measure('<svg width="1280" height="2276"><rect width="1280" height="2276" fill="navy"/></svg><h1 style="position:absolute;top:80px">Copertina illustrata</h1>');assert.equal(hero.issue,false);
 assert.equal((await measure(top,720)).issue,false);assert.equal((await measure(top,2276,{layout:'columns3'})).issue,false);
 console.log('PASS: real DOM detects sparse portrait and wrong size, ignores empty backgrounds, preserves balanced, illustrated, split and landscape compositions.');
}finally{await browser.close();}
