import {Marked} from 'marked';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js';
import katex from 'katex';
import mermaid from 'mermaid';
import Chart from 'chart.js/auto';
import {validateChart} from './chart-schema.js';

export const escape = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function saveBlob(blob,name){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}
const markdown = new Marked({gfm:true,breaks:false,renderer:{html(){return '';}}});
markdown.use({extensions:[
  {name:'mathBlock',level:'block',start:src=>src.indexOf('$$'),tokenizer(src){const m=/^\$\$([\s\S]+?)\$\$(?:\n|$)/.exec(src);if(m)return {type:'mathBlock',raw:m[0],text:m[1]};},renderer(t){return `<div class="math-block">${katex.renderToString(t.text,{displayMode:true,throwOnError:false,trust:false,strict:'warn'})}</div>`;}},
  {name:'mathInline',level:'inline',start:src=>src.indexOf('$'),tokenizer(src){const m=/^\$(?!\s)([^$\n]+?)\$/.exec(src);if(m)return {type:'mathInline',raw:m[0],text:m[1]};},renderer(t){return katex.renderToString(t.text,{throwOnError:false,trust:false,strict:'warn'});}}
]});
mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'base',htmlLabels:false,fontFamily:'Manrope, sans-serif',
  themeVariables:{primaryColor:'#eaf0e9',primaryTextColor:'#153d40',primaryBorderColor:'#88a190',lineColor:'#537c70',secondaryColor:'#f3ead9',tertiaryColor:'#fffefa'},
  flowchart:{htmlLabels:false},maxTextSize:30000});
let diagramId=0;
const palette=['#24605b','#c09958','#72917d','#577b98','#ad716b','#7b72a0'];

export async function renderRich(target,text,{final=true}={}) {
  for(const canvas of target.querySelectorAll('canvas')) Chart.getChart(canvas)?.destroy();
  const html = markdown.parse(String(text||''));
  target.innerHTML = DOMPurify.sanitize(html,{USE_PROFILES:{html:true,svg:true,mathMl:true},FORBID_TAGS:['style','iframe','form','input']});
  for(const a of target.querySelectorAll('a')){a.target='_blank';a.rel='noopener noreferrer';}
  for(const img of target.querySelectorAll('img')) {if(!img.getAttribute('src')?.startsWith('/media/'))img.remove();}
  for(const code of target.querySelectorAll('pre > code')) {
    const lang=code.className.replace('language-','');
    if(final && lang==='mermaid') {
      const pre=code.parentElement; const source=code.textContent;
      try {
        const id=`h3diagram${++diagramId}`;
        const {svg}=await mermaid.render(id,source);
        if(!pre.isConnected)continue;
        const figure=document.createElement('figure');figure.className='visual diagram';
        const clean=DOMPurify.sanitize(svg,{USE_PROFILES:{svg:true,svgFilters:true}});
        figure.innerHTML=`<div class="visual-label">DIAGRAMMA <button class="text-button no-export">Scarica SVG</button></div><div class="render-body">${clean}</div>`;
        figure.querySelector('button').onclick=()=>saveBlob(new Blob([clean],{type:'image/svg+xml'}),'diagramma.svg');
        pre.replaceWith(figure);
      }catch(err){document.getElementById('dh3diagram'+diagramId)?.remove();pre.insertAdjacentHTML('afterend',`<p class="render-error">Diagramma da correggere: ${escape(String(err.message).slice(0,250))}</p>`);}
    } else if(final && lang==='chart') {
      try {
        const spec=validateChart(JSON.parse(code.textContent));
        const figure=document.createElement('figure');figure.className='visual chart';
        figure.innerHTML=`<div class="visual-label">${escape(spec.title)} <button class="text-button no-export">Scarica PNG</button></div><div class="chart-box render-body"><canvas></canvas></div><details class="chart-data no-export"><summary>Dati del grafico</summary><pre></pre></details>`;
        code.parentElement.replaceWith(figure);
        const canvas=figure.querySelector('canvas');
        new Chart(canvas,{type:spec.type,data:{labels:spec.labels,datasets:spec.datasets.map((s,i)=>({...s,borderColor:palette[i%palette.length],backgroundColor:['pie','doughnut'].includes(spec.type)?palette:palette[i%palette.length]+'b0',tension:0,pointRadius:3,borderWidth:2}))},options:{responsive:true,maintainAspectRatio:false,animation:false,devicePixelRatio:2,plugins:{legend:{position:'bottom'}},scales:['pie','doughnut'].includes(spec.type)?{}:{x:{type:spec.type==='scatter'?'linear':'category',title:{display:!!spec.xLabel,text:spec.xLabel}},y:{beginAtZero:spec.type==='bar',title:{display:!!spec.yLabel,text:spec.yLabel}}}}});
        figure.querySelector('pre').textContent=JSON.stringify(spec,null,2);
        figure.querySelector('button').onclick=()=>canvas.toBlob(b=>saveBlob(b,'grafico.png'));
      }catch(err){code.parentElement.insertAdjacentHTML('afterend',`<p class="render-error">Dati da correggere: ${escape(err.message)}</p>`);}
    } else {
      if(hljs.getLanguage(lang)){try{code.innerHTML=hljs.highlight(code.textContent,{language:lang}).value;}catch{}}
      const bar=document.createElement('div');bar.className='code-bar no-export';
      bar.innerHTML=`<span>${escape(lang||'testo')}</span><button class="text-button">Copia</button>`;
      bar.querySelector('button').onclick=async()=>{await navigator.clipboard.writeText(code.textContent);bar.querySelector('button').textContent='Copiato';};
      code.parentElement.prepend(bar);
    }
  }
}

export function appendMedia(target,media) {
  for(const m of media||[]){
    const figure=document.createElement('figure'),url='/media/'+escape(m.path);
    if(m.mime?.startsWith('audio/')){figure.className='audio-output';figure.innerHTML=`<div class="audio-title">♫ ${escape(m.name)}</div><audio class="no-export" controls preload="metadata" src="${url}" aria-label="${escape(m.name)}"></audio><figcaption class="no-export"><a href="${url}" download="${escape(m.name)}">Scarica WAV originale</a></figcaption>`;}
    else{figure.className='image-output';figure.innerHTML=`<a href="${url}" target="_blank" rel="noopener"><img src="${url}" alt="${escape(m.name)}" loading="lazy"></a><figcaption class="no-export">${escape(m.name)} <a href="${url}" download>Scarica originale</a></figcaption>`;}
    target.append(figure);
  }
}
