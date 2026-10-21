export const IMAGE_FORMATS=[
 ['auto','Automatico · dimensioni o immagine di riferimento'],
 ['1:1','1:1 · Quadrato'],['16:9','16:9 · Orizzontale'],['9:16','9:16 · Verticale'],
 ['4:3','4:3 · Orizzontale'],['3:4','3:4 · Verticale'],
 ['3:2','3:2 · Orizzontale'],['2:3','2:3 · Verticale'],
];
export const imageFormatLabel=value=>IMAGE_FORMATS.find(([key])=>key===value)?.[1]||value;
