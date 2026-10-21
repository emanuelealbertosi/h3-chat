export function videoGuideFields(item){
 if(item.mode!=='video'||item.anchors==='none')return {};
 if(item.auto_anchors)return {anchors:item.anchors,auto_anchors:true,anchor_edit_model:item.anchor_edit_model};
 return {anchors:item.anchors,anchor_images:Object.fromEntries(Object.entries(item.anchor_images).filter(([key])=>key==='first'||item.anchors==='three'||(key==='last'&&item.anchors==='ends')))};
}
