import {spawn} from 'node:child_process';import {createRequire} from 'node:module';import {once} from 'node:events';import {createInterface} from 'node:readline';import {mkdir,readFile,writeFile} from 'node:fs/promises';import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');const folder='work/poster-type-qa';await mkdir(folder,{recursive:true});
const child=spawn('runtime/python/python.exe',['-X','utf8','tests/serve_posters_fixture.py'],{stdio:['ignore','pipe','pipe'],env:process.env});let logs='';child.stderr.on('data',x=>logs+=x);
const lines=createInterface({input:child.stdout});const [line]=await Promise.race([once(lines,'line'),once(child,'exit').then(()=>{throw Error(logs);})]);lines.close();const fixture=JSON.parse(line);
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});const page=await browser.newPage({viewport:{width:1500,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
page.on('console',m=>{if(m.type()==='error')logs+='\n'+m.text();});page.on('requestfailed',r=>logs+='\nrequest failed: '+r.url().split('?')[0]+' '+r.failure()?.errorText);
const post=(path,body={})=>page.evaluate(async({path,body})=>{const state=await fetch('/api/state').then(r=>r.json());const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':state.token},body:JSON.stringify(body)});const v=await r.json();if(!r.ok)throw Error(v.error);return v;},{path,body});
try{
 await page.goto(fixture.url);await page.click(`[data-chat="${fixture.chat}"]`);
 for(const [style,font] of [['editorial','Cormorant'],['playful','Baloo2'],['cinematic','BebasNeue'],['handwritten','Caveat'],['comic','Bangers'],['neon','BebasNeue']]){
  if(await page.locator('#lab-tool').inputValue()!=='poster')await page.locator('#prompt-posters').click();await page.locator('[data-mode-settings="posters-options"]').click();const modal=page.locator('#prompt-mode-settings');
  await modal.locator('[data-poster="format"]').selectOption('16:9');await modal.locator('[data-poster="lettering"]').selectOption(style);await modal.locator('[data-poster="images"]').selectOption('none');await modal.locator('[data-poster="count"]').fill('1');await modal.locator('footer .primary').click();
  await page.fill('#prompt','Crea una locandina TYPE SPECIMEN, senza immagini.');const ticket=page.waitForResponse(r=>r.url().endsWith('/messages')&&r.request().method()==='POST');await page.click('#send');const result=await (await ticket).json();assert.ok(result.job_id,JSON.stringify(result));await post('/fixture/execute',{job:result.job_id});await page.reload();await page.locator(`[data-chat="${fixture.chat}"]`).click();if(!await page.locator('#canvas-panel').isVisible())await page.locator('#canvas-toggle').click();
  const frame=page.frameLocator('#canvas-preview .h3-html-page iframe'),title=frame.locator('[data-poster-zone="title"]');await title.waitFor();
  await page.waitForFunction(expected=>{const e=document.querySelector('#canvas-preview iframe')?.contentDocument?.querySelector('[data-poster-zone="title"]');return e&&e.ownerDocument.defaultView.getComputedStyle(e).fontFamily.includes(expected);},font);
  await page.waitForFunction(()=>document.querySelector('#stop')?.hidden===true);
  await title.evaluate(async()=>{await document.fonts.ready;});assert.equal(await title.evaluate((e,font)=>e.ownerDocument.fonts.check('40px '+font),font),true);
  if(style==='cinematic')assert.equal(await title.locator('span').first().evaluate(e=>e.hasAttribute('data-contrast-adjusted')),false,'Gradient ink must not be overwritten by contrast repair');
  await page.locator('#canvas-preview iframe').screenshot({path:`${folder}/${style}.png`});
  const wait=page.waitForEvent('download');await page.locator('#canvas-panel [data-export="png"]').click();await (await wait).saveAs(`${folder}/${style}-export.png`);assert.ok((await readFile(`${folder}/${style}-export.png`)).length>15000);
  const png='data:image/png;base64,'+(await readFile(`${folder}/${style}-export.png`)).toString('base64');
  const painted=await page.evaluate(async src=>{const image=new Image();image.src=src;await image.decode();const c=document.createElement('canvas');c.width=image.width;c.height=image.height;const x=c.getContext('2d');x.drawImage(image,0,0);const p=x.getImageData(80,100,c.width-160,Math.floor(c.height*.4)).data,colors=new Set();let bright=0;for(let i=0;i<p.length;i+=16){colors.add((p[i]>>3)+','+(p[i+1]>>3)+','+(p[i+2]>>3));if(p[i]+p[i+1]+p[i+2]>360)bright++;}return{colors:colors.size,bright};},png);
  assert.ok(painted.colors>30&&painted.bright>1000,style+' PNG lacks painted lettering: '+JSON.stringify(painted));
  if(style==='cinematic'){
   const htmlWait=page.waitForEvent('download');await page.locator('#canvas-panel [data-export="html"]').click();await (await htmlWait).saveAs(`${folder}/cinematic.html`);assert.match(await readFile(`${folder}/cinematic.html`,'utf8'),/BebasNeue/);
   const pdfWait=page.waitForEvent('download');await page.locator('#canvas-panel [data-export="pdf"]').click();await (await pdfWait).saveAs(`${folder}/cinematic.pdf`);
  }
 }
 assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,styles:6,fonts_loaded:true,png_exports:6,html:true,pdf:true,gpu_models:0}));
}catch(e){await page.screenshot({path:folder+'/error.png',fullPage:true});await writeFile(folder+'/export-probe.json',JSON.stringify(await page.evaluate(()=>window.exportProbe)||{},null,2));console.error(logs);console.error('Last notification: '+await page.locator('#toast').textContent());throw e;}finally{await browser.close();child.kill();}
