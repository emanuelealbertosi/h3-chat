export const themes={lagoon:'Petrolio · lime · azzurro',indigo:'Indaco · lilla · corallo',sunset:'Corallo · prugna · oro'};
export const typography={modern:'Moderno',editorial:'Editoriale'};
export const designs={professional:'Serio / professionale',playful:'Giocoso / colorato',comic:'Fumettoso'};
export function validateDesign(deck){
  for(const [key,values,fallback] of [['theme',themes,'lagoon'],['typography',typography,'modern'],['design',designs,'professional']]){const value=deck[key]??fallback;if(typeof value!=='string'||!Object.hasOwn(values,value))throw Error('Tema o stile slide non valido.');}
  if(!['concise','full'].includes(deck.detail??'concise'))throw Error('Dettaglio slide non valido.');
  const height=deck.format==='9:16'?1280*16/9:1280;
  for(const page of deck.pages){
    const overrides=Object.hasOwn(page,'overrides')?page.overrides:{},ids=new Set(page.nodes.map(n=>n.id));
    if(!overrides||typeof overrides!=='object'||Array.isArray(overrides)||Object.keys(overrides).length>40)throw Error('Modifiche grafiche non valide.');
    for(const [id,values] of Object.entries(overrides)){
      if(!ids.has(id)||!values||typeof values!=='object'||Array.isArray(values))throw Error('Elemento slide modificato non valido.');
      for(const [key,value] of Object.entries(values)){
        if(['color','background'].includes(key)){if(typeof value!=='string'||!/^#[\da-f]{6}$/i.test(value))throw Error('Colore slide non valido.');}
        else if(key==='align'){if(!['left','center','right'].includes(value))throw Error('Allineamento non valido.');}
        else if(key==='font'){if(!['Manrope','Cormorant','Consolas','Comic Sans MS'].includes(value))throw Error('Carattere non valido.');}
        else {const limits={x:[-1280,1280],y:[-height,height],width:[40,1164],height:[20,Math.max(1164,height-116)],font_size:[16,88]}[key];if(!limits||typeof value!=='number'||!Number.isFinite(value)||value<limits[0]||value>limits[1])throw Error('Dimensione o posizione slide non valida.');}
      }
    }
  }
}
export function applyOverride(element,value={}){
  if(Object.hasOwn(value,'x')||Object.hasOwn(value,'y'))element.style.transform=`translate(${value.x||0}px,${value.y||0}px)`;
  if(value.width)element.style.width=value.width+'px';
  if(value.height)element.style.minHeight=value.height+'px';
  if(value.font_size)element.style.setProperty('--node-font-size',value.font_size+'px');
  if(value.font)element.style.setProperty('--node-font',value.font);
  if(value.color)element.style.color=value.color;
  if(value.background){element.style.backgroundColor=value.background;element.style.padding='18px';element.style.borderRadius='12px';}
  if(value.align)element.style.textAlign=value.align;
}
export const encodeDeck=deck=>'```h3-slides\n'+JSON.stringify(deck)+'\n```';
