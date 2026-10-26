// Lightweight vector ornament: no images, external URLs, labels or GPU work.
export function slideDecoration(doc,deck,height,accent){
 const ns='http://www.w3.org/2000/svg',svg=doc.createElementNS(ns,'svg');svg.setAttribute('viewBox',`0 0 1280 ${height}`);svg.setAttribute('aria-hidden','true');svg.dataset.h3Decoration='';
 const design=deck.design||'professional',palette={pastel:[accent,'#e4a9bb','#78bcb5'],natural:[accent,'#b59c64','#8eb48b'],neon:[accent,'#20bfc8','#e85cba'],vivid:[accent,'#ef9957','#8472ce'],monochrome:[accent,accent,accent]}[deck.palette]||[accent,'#76a8a1','#d6ac73'];
 const topic=String(deck.title||'').toLocaleLowerCase(),motif=/logic|informat|circuit|digit|computer|program|algoritm|robot/.test(topic)?'circuit':/botan|natur|piant|ecolog|ambient|flor/.test(topic)?'leaves':/spazi|astro|cosmo|pianet|univers/.test(topic)?'stars':design==='comic'?'comic':design==='playful'?'confetti':'geometry';svg.dataset.h3DecorationMotif=motif;
 const ornament=doc.createElementNS(ns,'g');svg.append(ornament);
 const put=(tag,attrs,parent=ornament)=>{const e=doc.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));parent.append(e);return e;};
 const line=(d,color=palette[0],width=2,opacity=.65,parent=svg)=>put('path',{d,fill:'none',stroke:color,'stroke-width':width,'stroke-linecap':'round','stroke-linejoin':'round',opacity},parent);
 put('rect',{x:18,y:18,width:1244,height:height-36,rx:design==='comic'?5:24,fill:'none',stroke:palette[0],'stroke-width':design==='comic'?3:2,opacity:.48});
 // Ornaments live in the outer 40 px; the central reading area is clear.
 for(const [x,y,sx,sy] of [[0,0,1,1],[1280,0,-1,1],[0,height,1,-1],[1280,height,-1,-1]]){
  const g=put('g',{transform:`translate(${x} ${y}) scale(${sx} ${sy})`});
  line('M 8 82 V 28 Q 8 8 28 8 H 142',palette[0],design==='comic'?4:2,.7,g);
  put('path',{d:'M 0 0 H 112 Q 62 22 34 34 Q 18 54 0 106 Z',fill:palette[1],opacity:design==='playful'?.13:.08},g);
  if(motif==='circuit'){
   line('M 31 92 V 50 L 44 33 H 178',palette[1],2.5,.85,g);line('M 50 16 H 112 L 127 31 H 218',palette[2],2,.75,g);
   for(const [cx,cy,c] of [[31,92,1],[178,33,1],[218,31,2],[50,16,2]])put('circle',{cx,cy,r:3.5,fill:palette[c],opacity:.85},g);
   put('rect',{x:64,y:14,width:26,height:17,rx:3,fill:palette[0],opacity:.16},g);
   for(const n of [68,76,84]){line(`M ${n} 10 V 14`,palette[0],1.5,.8,g);line(`M ${n} 31 V 36`,palette[0],1.5,.8,g);}
  }else if(motif==='leaves'){
   line('M 24 118 V 52 Q 24 24 56 24 H 150',palette[0],2,.7,g);
   for(const b of [72,104]){put('path',{d:`M 24 ${b} Q 6 ${b-14} 10 ${b-20} Q 22 ${b-20} 24 ${b} Z`,fill:palette[1],opacity:.45},g);put('path',{d:`M 24 ${b} Q 38 ${b-20} 38 ${b-8} Q 36 ${b-2} 24 ${b} Z`,fill:palette[0],opacity:.3},g);}
   for(const a of [76,110])put('path',{d:`M ${a} 24 Q ${a+8} 6 ${a+18} 12 Q ${a+18} 24 ${a} 24 Z`,fill:palette[1],opacity:.45},g);
  }else if(motif==='stars'){
   line('M 22 94 L 32 46 L 84 22 H 148',palette[1],1.5,.6,g);
   for(const [cx,cy,r] of [[22,94,3],[32,46,4],[84,22,3],[148,22,2]])put('circle',{cx,cy,r,fill:palette[1],opacity:.85},g);
   put('path',{d:'M 52 12 L 55 21 L 64 24 L 55 27 L 52 36 L 49 27 L 40 24 L 49 21 Z',fill:palette[2],opacity:.75},g);
  }else if(motif==='confetti'){
   line('M 20 112 Q 8 86 24 70 Q 40 54 22 36 Q 8 22 40 20 H 144',palette[1],3,.7,g);
   for(const [cx,cy,r] of [[64,23,6],[91,27,3],[125,23,4],[23,54,5],[24,100,3]])put('circle',{cx,cy,r,fill:palette[2],opacity:.65},g);
   line('M 72 12 L 79 20 M 106 25 L 111 15 M 12 66 L 20 70',palette[0],3,.75,g);
  }else if(motif==='comic'){
   line('M 12 94 L 29 71 L 20 52 L 40 31 L 72 20 L 104 28 L 148 13',palette[0],3,.8,g);
   for(let row=0;row<3;row++)for(let col=0;col<6-row;col++)put('circle',{cx:47+col*10,cy:10+row*9,r:1.8,fill:palette[2],opacity:.55},g);
   line('M 12 38 L 24 30 M 12 48 L 28 36',palette[1],3,.75,g);
  }else{
   line('M 29 105 V 48 Q 29 29 48 29 H 182',palette[1],2,.8,g);
   line('M 48 11 H 93 M 102 11 H 126',palette[0],3,.7,g);
   for(const [cx,cy] of [[148,29],[162,29],[176,29]])put('circle',{cx,cy,r:2.5,fill:palette[2],opacity:.8},g);
   put('path',{d:'M 30 12 L 38 20 L 30 28 L 22 20 Z',fill:palette[2],opacity:.5},g);
  }
 }
 return svg;
}
