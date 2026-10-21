export function imageModelOptions(model,options){
 if(model?.architecture==='fibo2')return {grid:16,max:2048,samplers:['auto','euler'],schedulers:['auto','simple']};
 return {grid:model?.architecture==='moss'?1:64,max:model?.architecture==='moss'?4096:1536,
  samplers:model?.engine==='vision'?options.vision_samplers:options.samplers,
  schedulers:model?.engine==='vision'?options.vision_schedulers:options.schedulers};
}
