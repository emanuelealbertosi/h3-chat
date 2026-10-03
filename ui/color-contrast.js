// sRGB relative luminance; translucent foregrounds are composited before testing.
export function parseColor(value){
  if(value==='transparent')return [0,0,0,0];
  const hex=/^#([\da-f]{3}|[\da-f]{6}|[\da-f]{8})$/i.exec(value||'');
  if(hex){let s=hex[1];if(s.length===3)s=[...s].map(c=>c+c).join('');return [0,2,4].map(i=>parseInt(s.slice(i,i+2),16)).concat(s.length===8?parseInt(s.slice(6),16)/255:1);}
  if(!/^rgba?\(/i.test(value||''))return null;
  const parts=value.match(/[\d.]+%?/g);if(!parts||parts.length<3)return null;
  return parts.map((s,i)=>s.endsWith('%')?parseFloat(s)*(i===3?.01:2.55):Number(s)).slice(0,4).concat(parts.length===3?[1]:[]);
}
export function composite(foreground,background,opacity=1){
  const alpha=(foreground[3]??1)*opacity;
  return foreground.slice(0,3).map((c,i)=>c*alpha+background[i]*(1-alpha)).concat(1);
}
export function luminance(rgb){return rgb.slice(0,3).map(c=>{const s=c/255;return s<=.04045?s/12.92:((s+.055)/1.055)**2.4;}).reduce((sum,c,i)=>sum+c*[.2126,.7152,.0722][i],0);}
export function contrastRatio(foreground,background,opacity=1){const a=luminance(composite(foreground,background,opacity)),b=luminance(background);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);}
export const colorHex=rgb=>'#'+rgb.slice(0,3).map(c=>Math.max(0,Math.min(255,Math.round(c))).toString(16).padStart(2,'0')).join('');
export function readableColor(foreground,background,opacity=1,minimum=4.5){
  if(contrastRatio(foreground,background,opacity)>=minimum)return foreground;
  const black=[0,0,0,1],white=[255,255,255,1],end=contrastRatio(black,background,opacity)>contrastRatio(white,background,opacity)?black:white;
  if(contrastRatio(end,background,opacity)<minimum)return end;
  let low=0,high=1;
  for(let i=0;i<24;i++){const mid=(low+high)/2,c=foreground.slice(0,3).map((v,j)=>Math.round(v+(end[j]-v)*mid)).concat(1);if(contrastRatio(c,background,opacity)>=minimum)high=mid;else low=mid;}
  return foreground.slice(0,3).map((v,i)=>Math.round(v+(end[i]-v)*high)).concat(1);
}
