import {createRequire} from 'node:module';
import {spawnSync} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']}),page=await browser.newPage({viewport:{width:640,height:360}});
const folder=await mkdtemp(tmpdir()+'/h3-clean-blend-');
try{
 await page.setContent('<style>html,body{margin:0;width:100%;height:100%;background:white;overflow:hidden}#host{position:relative;width:640px;height:360px;overflow:hidden}iframe{position:absolute;inset:0;border:0;width:100%;height:100%}</style><div id="host"></div>');
 await page.evaluate(()=>{
  for(const [i,color] of ['#ff0000','#0000ff'].entries()){
   const frame=document.createElement('iframe');frame.dataset.h3Scene='';
   const image='data:image/svg+xml,'+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" fill="${color}"/></svg>`);
   frame.srcdoc=`<style>html,body{margin:0;width:100%;height:100%;overflow:hidden}main{position:relative;width:640px;height:360px}.p{position:absolute;inset:0}.photo img{width:100%;height:100%;object-fit:cover}</style><main><div class="p vector" data-depth=".35" ${i===0?'data-layer-role="background-vector"':''} style="z-index:999"><svg width="640" height="360" viewBox="0 0 640 360"><rect width="640" height="360" fill="#777777"/></svg></div><div class="p photo" data-depth=".5" ${i===0?'data-layer-role="background-image"':''} style="z-index:1"><img data-asset-id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" src="${image}"></div><div class="p foreground" data-depth="1.65"><svg width="20" height="80" style="position:absolute;right:40px;top:100px"><rect width="20" height="80" fill="#00ff00"/></svg></div><div class="p hud" data-depth="0"><h1 style="position:absolute;top:20px;left:50px;font:26px sans-serif;color:white">HUD</h1></div></main>`;
   document.querySelector('#host').append(frame);
  }
  window.H3Motion={apply(){}};
 });
 await page.waitForFunction(()=>[...document.querySelectorAll('iframe')].every(f=>f.contentDocument?.querySelector('img')?.complete));
 await page.addScriptTag({path:'static/infographic-cinema.js'});
 const seek=t=>page.evaluate(t=>{const host=document.querySelector('#host');window.H3Cinema.render(host,{durations:[4,4],options:{transition_seconds:.9}},t);return [...host.querySelectorAll('iframe')].map(f=>({opacity:f.style.opacity,transform:f.style.transform,z:[...f.contentDocument.querySelectorAll('[data-depth]')].map(e=>e.style.zIndex),hud:f.contentDocument.querySelector('.hud').style.transform}));},t);
 const reference=await seek(2);assert.deepEqual(reference[0].z,['0','10','28','40']);assert.ok(reference[0].hud.includes('translateX(0px) scale(1)'));
 await seek(6);assert.deepEqual(await seek(2),reference);
 const middle=await seek(4);assert.equal(middle[0].opacity,'1');assert.ok(Math.abs(Number(middle[1].opacity)-.5)<1e-8);assert.equal(middle[0].transform,'none');assert.deepEqual(middle[1].z,['0','10','28','40']);
 assert.equal(await page.locator('[data-h3-camera-occluder]').count(),0);
 await page.screenshot({path:folder+'/middle.png'});
 const check=spawnSync('runtime/python/python.exe',['-X','utf8','-c',`import sys;sys.path.insert(0,'F:/H3-Chat/runtime/tools/documents');from PIL import Image;i=Image.open(sys.argv[1]).convert('RGB');pixels=[i.getpixel(p) for p in [(2,2),(320,180),(638,358)]];assert all(110<=r<=145 and g<8 and 110<=b<=145 for r,g,b in pixels),pixels;print(pixels)`,folder+'/middle.png'],{encoding:'utf8'});assert.equal(check.status,0,check.stderr);
 await page.evaluate(()=>window.H3Cinema.reset(document.querySelector('#host')));
 assert.equal(await page.locator('iframe').first().evaluate(f=>f.contentDocument.querySelector('.vector').style.zIndex),'999');
 console.log('PASS: no occluder, full-frame opaque-base blend has no gray edge or stage-color leak; explicit and legacy SVG backdrops stay below images; small foreground and HUD stay above; deterministic seek and reset. '+check.stdout.trim());
}finally{await browser.close();await rm(folder,{recursive:true,force:true});}
