import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const code=await build({stdin:{contents:"import {initInterfaceMode} from './ui/interface-mode.js'; window.mode=initInterfaceMode({onBasic:()=>{window.basicCalls=(window.basicCalls||0)+1;}});",resolveDir:process.cwd()},bundle:true,write:false,format:'iife'});
const css=await readFile('static/composer.css','utf8');
const html='<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div class="top-actions"></div><button id="settings-open">Settings</button><button id="prompt-agent">Agent</button><button id="prompt-options-open">Technical</button><button id="attach">Attach</button><button id="send">Send</button><button id="prompt-slides">Slides</button><textarea id="prompt">Draft</textarea><script src="/app.js"></script><link rel="stylesheet" href="/style.css">';
const server=createServer((req,res)=>{res.setHeader('Content-Type',req.url==='/app.js'?'application/javascript':req.url==='/style.css'?'text/css':'text/html');res.end(req.url==='/app.js'?code.outputFiles[0].text:req.url==='/style.css'?css:html);});server.listen(0,'127.0.0.1');await once(server,'listening');
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
try{
 const page=await browser.newPage();await page.goto('http://127.0.0.1:'+server.address().port);
 assert.equal(await page.locator('#prompt-agent').isVisible(),true);
 await page.locator('[data-interface-mode="basic"]').click();
 for(const id of ['prompt-agent','settings-open','prompt-options-open'])assert.equal(await page.locator('#'+id).isVisible(),false);
 for(const id of ['attach','send','prompt-slides','prompt'])assert.equal(await page.locator('#'+id).isVisible(),true);
 assert.equal(await page.locator('#prompt').inputValue(),'Draft');
 await page.reload();assert.equal(await page.locator('#prompt-agent').isVisible(),false);
 assert.equal(await page.evaluate(()=>window.basicCalls),1);
 await page.locator('[data-interface-mode="advanced"]').click();assert.equal(await page.locator('#prompt-agent').isVisible(),true);
 await page.reload();assert.equal(await page.evaluate(()=>window.mode.getMode()),'advanced');
 await page.setViewportSize({width:390,height:844});assert.equal(await page.locator('#interface-mode').isVisible(),true);
 console.log('Passed: Basic/Advanced visibility, draft preserved, reload persistence, mobile and essential actions.');
}finally{await browser.close();server.close();}
