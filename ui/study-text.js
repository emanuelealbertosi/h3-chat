import {Marked} from 'marked';
import DOMPurify from 'dompurify';
import renderMath from 'katex/contrib/auto-render';

const markdown=new Marked({gfm:true,breaks:true,renderer:{html(){return '';}}});
// Model/imported text may contain Markdown and formulae, never executable HTML
// or external images. Sources and their exact quotes are rendered separately.
export function studyText(host,text){
 const marker='H3STUDYMATH'+crypto.randomUUID().replaceAll('-','')+'X',fragments=[],prepared=String(text).replace(/\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$(?!\s)[^$\n]+?\$/g,formula=>{const id=fragments.push(formula)-1;return marker+id+'END';});
 const html=markdown.parse(prepared).replace(new RegExp(marker+'(\\d+)END','g'),(_,id)=>fragments[Number(id)].replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'));
 host.innerHTML=DOMPurify.sanitize(html,{USE_PROFILES:{html:true},FORBID_TAGS:['img','style','script','iframe','object','embed','form','input','button','audio','video'],FORBID_ATTR:['style','id','name','href','src']});
 renderMath(host,{delimiters:[{left:'$$',right:'$$',display:true},{left:'\\[',right:'\\]',display:true},{left:'\\(',right:'\\)',display:false},{left:'$',right:'$',display:false}],throwOnError:false,trust:false,strict:'warn'});
}
