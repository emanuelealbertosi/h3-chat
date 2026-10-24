import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import {writeFileSync,mkdirSync} from 'node:fs';
const require=createRequire(import.meta.url),{build}=require('esbuild'),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const built=await build({stdin:{contents:`import {htmlPage,flattenHtml} from './ui/slide-html.js';window.h3Test={htmlPage,flattenHtml};`,resolveDir:process.cwd()},bundle:true,write:false,format:'iife',loader:{'.woff':'dataurl','.woff2':'dataurl','.ttf':'dataurl'}});
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
try{
 const page=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});
 await page.setContent('<style>body{margin:0}</style><div id="mount"></div>');await page.addScriptTag({content:built.outputFiles[0].text});
 const originalBytes=await page.evaluate(async()=>{
  const html='<style>main{width:1280px;height:720px;padding:36px;background:linear-gradient(135deg,#ecf8fd,#fff4da);font:20px Arial;display:flex;gap:24px}section{background:white;border:2px solid #224455;border-radius:12px;padding:20px;width:560px}h1{font-size:36px;color:#123456}h1:before{content:"● ";color:#ee8833}p{line-height:1.6}svg{width:160px;height:100px}</style><main><section><h1>Una slide ricca</h1><p>Testo con <b>grassetto</b> e dettagli.</p><svg viewBox="0 0 160 100"><rect width="100" height="80" fill="#22aa77"/></svg></section><section><h1>Confronto</h1>'+Array.from({length:7},(_,i)=>'<p>Voce '+i+' • esempio leggibile</p>').join('')+'</section></main>';
  window.frame=await h3Test.htmlPage({format:'16:9'}, {title:'Fixture',html},0,[],document.querySelector('#mount'));
  const doc=frame.querySelector('iframe').contentDocument;let bytes=0;for(const n of [doc.body,...doc.body.querySelectorAll('*')]){const css=doc.defaultView.getComputedStyle(n);for(const p of css)bytes+=p.length+css.getPropertyValue(p).length+2;}return bytes;
 });
 const before=await page.screenshot();
 const compactBytes=await page.evaluate(()=>{h3Test.flattenHtml(frame);return frame.outerHTML.length;});
 const after=await page.screenshot();
 mkdirSync('work/slide-export-2026-10-24',{recursive:true});writeFileSync('work/slide-export-2026-10-24/before.png',before);writeFileSync('work/slide-export-2026-10-24/after.png',after);
 assert.deepEqual(after,before,'Static slide appearance must remain pixel-identical');assert.ok(compactBytes<originalBytes*.35,{compactBytes,originalBytes});
 console.log(JSON.stringify({visual:'pixel-identical',originalBytes,compactBytes,reduction:1-compactBytes/originalBytes}));
}finally{await browser.close();}

