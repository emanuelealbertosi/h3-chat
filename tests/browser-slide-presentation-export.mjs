import {createRequire} from 'node:module';
import {mkdirSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{build}=require('esbuild'),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const built=await build({stdin:{contents:`import {presentationHtml} from './ui/slide-presentation-export.js';window.makeDeck=presentationHtml;`,resolveDir:process.cwd()},bundle:true,write:false,format:'iife',loader:{'.woff':'dataurl','.woff2':'dataurl','.ttf':'dataurl'}});
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
try{
 const builder=await browser.newPage();await builder.setContent('<h1>Fixture</h1>');await builder.addScriptTag({content:built.outputFiles[0].text});
 const html=await builder.evaluate(()=>makeDeck({width:1280,height:720,styles:['html,body{margin:0;background:white}#dot{width:80px;height:80px;background:red;animation:move 2s linear infinite alternate}@keyframes move{from{transform:translateX(0)}to{transform:translateX(200px)}}'],pages:[
  {title:'Animazione',html:'<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; script-src \'none\'"><style data-h3-shared-style="0"></style><h1>Prima pagina</h1><div id="dot"></div><img id="embedded" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="><script>parent.h3Injected=true</script>'},
  {title:'Seconda',html:'<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; script-src \'none\'"><h1>Seconda pagina</h1>'}]},'Titolo </script><script>window.h3Injected=true</script>'));
 mkdirSync('work/slide-html-presentation-qa',{recursive:true});const path=resolve('work/slide-html-presentation-qa/presentation.html');writeFileSync(path,html);
 const context=await browser.newContext({offline:true,viewport:{width:1280,height:900}}),page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(pathToFileURL(path).href);
 const frame=()=>page.frameLocator('#slide');await frame().locator('#dot').waitFor();assert.equal(await page.locator('#counter').innerText(),'1 / 2');assert.equal(await page.evaluate(()=>window.h3Injected),undefined);assert.equal(await page.locator('#slide').getAttribute('sandbox'),'');
 await frame().locator('#embedded').evaluate(e=>e.decode());assert.equal(await frame().locator('#embedded').evaluate(e=>e.naturalWidth),1);
 const first=await frame().locator('#dot').evaluate(e=>e.getBoundingClientRect().x);await page.waitForTimeout(220);const second=await frame().locator('#dot').evaluate(e=>e.getBoundingClientRect().x);assert.ok(Math.abs(second-first)>5,'Authored CSS animation must run offline');
 await page.getByRole('button',{name:'Slide successiva',exact:true}).click();await frame().getByText('Seconda pagina').waitFor();assert.equal(await page.locator('#counter').innerText(),'2 / 2');assert.equal(await page.locator('#next').isDisabled(),true);
 await page.keyboard.press('ArrowLeft');await frame().locator('#dot').waitFor();await page.getByRole('button',{name:'Ripeti animazioni'}).click();await frame().locator('#dot').waitFor();assert.equal(await page.locator('#counter').innerText(),'1 / 2');
 // Use the real fullscreen API on the offline exported file.
 await page.setViewportSize({width:1280,height:720});
 await page.getByRole('button',{name:'Schermo intero',exact:true}).click();await page.waitForFunction(()=>!!document.fullscreenElement);
 await page.mouse.move(640,450);await page.waitForTimeout(1900);
 const full=await page.evaluate(()=>{const r=document.getElementById('stage').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,viewport:[innerWidth,innerHeight],header:getComputedStyle(document.querySelector('header')).visibility,footer:getComputedStyle(document.querySelector('footer')).visibility};});
 assert.equal(full.x,0);assert.equal(full.y,0);assert.deepEqual([full.width,full.height],full.viewport);assert.equal(full.header,'hidden');assert.equal(full.footer,'hidden');
 await page.keyboard.press('ArrowRight');await frame().getByText('Seconda pagina').waitFor();assert.equal(await page.locator('#counter').textContent(),'2 / 2');
 await page.mouse.move(640,full.height-8);await page.locator('#previous').waitFor();
 const overlay=await page.locator('#stage').boundingBox();assert.deepEqual([overlay.width,overlay.height],full.viewport);
 await page.locator('#previous').click();await frame().locator('#dot').waitFor();await page.mouse.move(640,450);await page.waitForTimeout(1900);assert.equal(await page.locator('footer').isVisible(),false);
 await page.screenshot({path:'work/slide-html-presentation-qa/fullscreen.png'});
 await page.keyboard.press('Tab');await page.locator('footer').waitFor();
 await page.evaluate(()=>document.exitFullscreen());await page.waitForFunction(()=>!document.fullscreenElement);assert.equal(await page.locator('header').isVisible(),true);assert.equal(await page.locator('footer').isVisible(),true);
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(100);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);await page.screenshot({path:'work/slide-html-presentation-qa/mobile.png'});assert.deepEqual(errors,[]);
 console.log('Offline paged HTML: true fullscreen without reserved chrome space, controls reveal/autohide, fullscreen keyboard navigation, exit restoration, CSS motion, replay, sandbox isolation and mobile passed.');
}finally{await browser.close();}
