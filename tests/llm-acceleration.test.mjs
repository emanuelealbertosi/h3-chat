import test from 'node:test';
import assert from 'node:assert/strict';
import {acceleratedPreset,acceleratorAvailable} from '../ui/llm-acceleration.js';
test('accelerator preset is explicit and preserves unrelated output and sampling',()=>{
 const initial={context:50000,max_tokens:4096,temperature:.3,mtp_draft_tokens:1,think_level:'low',llm_timeout:7200};
 const chosen=acceleratedPreset(initial);
 assert.equal(initial.context,50000);assert.equal(initial.mtp_draft_tokens,1);
 assert.equal(chosen.context,131072);assert.equal(chosen.mtp_draft_tokens,2);
 assert.equal(chosen.llm_acceleration,'qwen27');assert.equal(chosen.max_tokens,4096);
 assert.equal(chosen.temperature,.3);assert.equal(chosen.llm_timeout,7200);
 assert.equal(acceleratedPreset({...initial,max_tokens:100000}).max_tokens,65536);
});
test('availability does not enable CPU, Vulkan, uninstalled or unverified models',()=>{
 const model={acceleration:{supported:true,installed:true}},settings={backend:'cuda',profile:'balanced'};
 assert.equal(acceleratorAvailable(model,settings),true);
 for(const patch of [{backend:'vulkan'},{profile:'cpu'},{llm_device:'cpu'}])assert.equal(acceleratorAvailable(model,{...settings,...patch}),false);
 assert.equal(acceleratorAvailable({acceleration:{supported:true,installed:false}},settings),false);
 assert.equal(acceleratorAvailable({api:true},settings),false);
});
test('Orca explicit preset uses MTP4 without changing ISTA or saved settings',()=>{
 const initial={context:50000,max_tokens:4096,temperature:.4,mtp_draft_tokens:1,llm_timeout:7200};
 const orca={acceleration:{supported:true,installed:true,draft_tokens:4}};
 const chosen=acceleratedPreset(initial,orca);
 assert.equal(chosen.context,131072);assert.equal(chosen.mtp_draft_tokens,4);
 assert.equal(chosen.max_tokens,4096);assert.equal(chosen.temperature,.4);
 assert.equal(initial.context,50000);assert.equal(initial.mtp_draft_tokens,1);
 assert.equal(acceleratedPreset(initial,{acceleration:{draft_tokens:2}}).mtp_draft_tokens,2);
 assert.throws(()=>acceleratedPreset(initial,{acceleration:{draft_tokens:8}}));
});
