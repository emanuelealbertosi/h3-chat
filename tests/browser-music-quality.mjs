import {createRequire} from 'node:module';
import {build} from 'esbuild';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage();
const result=await build({entryPoints:['ui/music-settings.js','ui/music-quality.js'],bundle:true,write:false,outdir:'work/music-quality-ui-test',format:'iife',globalName:'MusicUI'});
try{
 await page.setContent('<div id="preferences"></div><section id="music-inputs"></section>');
 await page.evaluate(result.outputFiles.find(f=>f.path.endsWith('music-settings.js')).text);
 await page.evaluate(()=>{
  globalThis.state={models:[{id:'q8',name:'YuE2 Q8',capabilities:['music'],ready:true},{id:'bf16',name:'YuE2 BF16',capabilities:['music'],ready:true}],music_options:{defaults:{cot:'full',seed:83601,cfg_scale:1,num_inference_steps:32},numbers:{num_inference_steps:[1,128,32]},integers:['num_inference_steps']}};
  globalThis.draft={music_model:'q8',music_backend:'cuda',music_threads:8,music_auto:true,music_advanced:true,music_overrides:{},music_quality:'model',music_quality_profiles:{high:{model:'bf16',steps:60},low:{model:'q8',steps:32}}};
  MusicUI.renderMusicSettings(document.querySelector('#preferences'),{state,draft,link(){},edit(){},install(){},download(){},changed(){}});
 });
 await page.locator('[data-music-default-quality="high"]').click();
 assert.equal(await page.locator('[data-setting="music_model"]').inputValue(),'bf16');
 assert.equal(await page.locator('#music-settings-model').inputValue(),'bf16');
 assert.equal(await page.locator('[data-music-setting="num_inference_steps"]').inputValue(),'60');
 await page.locator('[data-music-setting="num_inference_steps"]').fill('96');
 assert.equal(await page.evaluate(()=>draft.music_quality_profiles.high.steps),96);
 await page.locator('[data-music-default-quality="low"]').click();
 assert.equal(await page.locator('[data-setting="music_model"]').inputValue(),'q8');
 assert.equal(await page.locator('[data-music-setting="num_inference_steps"]').inputValue(),'32');
 await page.locator('[data-setting="music_model"]').selectOption('bf16');
 assert.equal(await page.evaluate(()=>draft.music_quality),'model');
 await page.evaluate(result.outputFiles.find(f=>f.path.endsWith('music-quality.js')).text);
 await page.evaluate(()=>{state.settings=draft;globalThis.choice={};globalThis.controls=MusicUI.initMusicQuality({getState:()=>state,read:()=>choice,save:value=>{choice=value;controls.render();}});controls.render();});
 await page.locator('button[data-music-quality="high"]').click();
 assert.equal(await page.evaluate(()=>choice.music_quality),'high');
 assert.match(await page.locator('[data-music-quality-summary]').innerText(),/BF16.*96 passi/);
 await page.locator('button[data-music-quality="low"]').click();
 assert.match(await page.locator('[data-music-quality-summary]').innerText(),/Q8.*32 passi/);
 await page.evaluate(()=>{state.settings.music_quality_profiles.high.model='';controls.render();});
 assert.equal(await page.locator('button[data-music-quality="high"]').isDisabled(),true);
 console.log('PASS: high/low select their real models, adjustable per-profile steps, manual-model compatibility, chat buttons and clear unconfigured presets.');
}finally{await browser.close();}
