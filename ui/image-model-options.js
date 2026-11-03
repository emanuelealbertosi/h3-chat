export function imageModelOptions(model,options){
 return {grid:model?.architecture==='ph3'?32:model?.architecture==='moss'?1:64,max:model?.architecture==='ph3'?8192:model?.architecture==='moss'?4096:1536,maxMP:model?.architecture==='ph3'?16:4,
  samplers:model?.architecture==='ph3'?['euler']:model?.engine==='vision'?options.vision_samplers:options.samplers,
  schedulers:model?.architecture==='ph3'?['ph3_image']:model?.engine==='vision'?options.vision_schedulers.filter(s=>s!=='ph3_image'):options.schedulers};
}
