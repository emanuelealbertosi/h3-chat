import {createRequire} from 'node:module';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{build}=require('esbuild'),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright'),JSZip=require('jszip');
const built=await build({stdin:{contents:`import {htmlPage,flattenHtml} from './ui/slide-html.js';import {exportPowerPoint} from './ui/slide-pptx.js';window.h3Test={htmlPage,flattenHtml,exportPowerPoint};`,resolveDir:process.cwd()},bundle:true,write:false,format:'iife',loader:{'.woff':'dataurl','.woff2':'dataurl','.ttf':'dataurl'}});
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
try{
 const page=await browser.newPage({viewport:{width:1280,height:720}});
 await page.setContent('<style>body{margin:0}</style><div id="mount"></div>');await page.addScriptTag({content:built.outputFiles[0].text});
 const folder=process.env.H3_PPTX_PROOF||'work/pptx-fidelity';mkdirSync(folder,{recursive:true});
 await page.evaluate(async()=>{
  const html='<style>main{width:1280px;height:720px;box-sizing:border-box;background:linear-gradient(135deg,#f4f9fc,#d0eeee);padding:50px;display:grid;grid-template-columns:2fr 1fr;gap:30px;font:24px Arial}h1{font-size:64px;color:#185267}h1:before{content:"✦ ";color:#df8540}aside{transform:rotate(-5deg);background:#ffe9ab;border:3px solid #21546a;border-radius:30px;padding:40px}svg{width:250px;height:180px}</style><main><section><h1>AI locale</h1><p>Un testo lungo, con <b>grassetto</b> e parole allineate.</p><svg viewBox="0 0 250 180"><circle cx="110" cy="90" r="70" fill="#008c99"/><path d="M50 90L110 20L200 130" fill="none" stroke="#f07947" stroke-width="12"/></svg></section><aside><h2>Ricerca</h2><p>Grafica ricca, font e sovrapposizioni intenzionali.</p></aside></main>';
  window.deck={engine:'llm',format:'16:9',title:'AI',pages:[{title:'AI',html,status:'ready',notes:'Nota conservata'}],references:[]};window.frame=await h3Test.htmlPage(deck,deck.pages[0],0,[],document.querySelector('#mount'));h3Test.flattenHtml(frame);
 });
 await page.screenshot({path:folder+'/html.png'});
 const wait=page.waitForEvent('download');await page.evaluate(()=>h3Test.exportPowerPoint(document.querySelector('#mount'),deck,'AI'));const file=await wait;await file.saveAs(folder+'/faithful.pptx');
 const zip=await JSZip.loadAsync(readFileSync(folder+'/faithful.pptx')),xml=await zip.file('ppt/slides/slide1.xml').async('string');
 assert.equal((xml.match(/<p:pic>/g)||[]).length,1);assert.equal((xml.match(/<p:sp>/g)||[]).length,0);assert.match(xml,/cx="12192000" cy="6858000"/);
 const name=Object.keys(zip.files).find(n=>/^ppt\/media\/image.*png$/.test(n));assert.ok(name);writeFileSync(folder+'/embedded.png',await zip.file(name).async('nodebuffer'));
 assert.match(await zip.file('ppt/notesSlides/notesSlide1.xml').async('string'),/Nota conservata/);
 writeFileSync(folder+'/proof.json',JSON.stringify({passed:true,faithful_single_fullpage_image:true,notes_preserved:true,html:'html.png',image:'embedded.png',pptx:'faithful.pptx'},null,2));
 console.log('PASS faithful PPT: full-page 16:9 image, no reconstructed text boxes, source notes preserved.');
}finally{await browser.close();}
