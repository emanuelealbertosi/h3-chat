export function chartData(type,series,labels){
  if(type!=='scatter')return series.map(s=>({name:s.label||'Serie',labels:labels.map(String),values:s.data.map(v=>v===null?null:Number(v))}));
  // Share an ordered X column without changing any coordinates. Empty values
  // represent missing points; duplicate X coordinates get distinct rows.
  const maximum=new Map(),points=series.map(s=>{
    const map=new Map();for(const p of s.data){const values=map.get(p.x)||[];values.push(p.y);map.set(p.x,values);}
    for(const [x,values] of map)maximum.set(x,Math.max(maximum.get(x)||0,values.length));return map;
  });
  const rows=[...maximum.keys()].sort((a,b)=>a-b).flatMap(x=>Array.from({length:maximum.get(x)},(_,i)=>({x,i})));
  const names=rows.map(r=>String(r.x));
  return [{name:'X',labels:names,values:rows.map(r=>r.x)},...series.map((s,index)=>({name:s.label||'Serie',labels:[...names],values:rows.map(r=>points[index].get(r.x)?.[r.i]??null)}))];
}
