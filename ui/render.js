import {Marked} from 'marked';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js';
import katex from 'katex';
import mermaid from 'mermaid';
import Chart from 'chart.js/auto';
import {validateChart} from './chart-schema.js';
import {addVideoAudioControl} from './video-playback.js';

export const escape = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function saveBlob(blob,name){document.dispatchEvent(new CustomEvent('h3-export',{detail:{blob,name}}));const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}
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

export async function renderRich(target,text,{final=true,sources=[],onCitation=null,onExecute=null}={}) {
  for(const canvas of target.querySelectorAll('canvas')) Chart.getChart(canvas)?.destroy();
  const html = markdown.parse(String(text||''));
  target.innerHTML = DOMPurify.sanitize(html,{USE_PROFILES:{html:true,svg:true,mathMl:true},FORBID_TAGS:['style','iframe','form','input']});
  for(const a of target.querySelectorAll('a')){a.target='_blank';a.rel='noopener noreferrer';}
  for(const a of target.querySelectorAll('a[href^="#rag-"]')){
    const source=sources.find(s=>'#rag-'+s.citation===a.getAttribute('href'));
    if(source&&onCitation){a.className='rag-citation';a.removeAttribute('target');a.title=source.name+' · '+source.location;a.onclick=e=>{e.preventDefault();onCitation(source,sources);};}
    else{a.replaceWith(document.createTextNode(a.textContent+' (fonte non disponibile)'));}
  }
  for(const quote of target.querySelectorAll('blockquote')){
    const first=quote.querySelector('p');const match=/^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION|QUOTE|RESULT|DEFINITION)\]\s*/i.exec(first?.textContent||'');
    if(match){quote.classList.add('callout','callout-'+match[1].toLowerCase());const label=document.createElement('strong');label.className='callout-label';label.textContent=({NOTE:'Nota',TIP:'Suggerimento',IMPORTANT:'Importante',WARNING:'Attenzione',CAUTION:'Avvertenza',QUOTE:'Citazione',RESULT:'Risultato',DEFINITION:'Definizione'})[match[1].toUpperCase()];quote.prepend(label);const walker=document.createTreeWalker(first,NodeFilter.SHOW_TEXT);const node=walker.nextNode();if(node)node.textContent=node.textContent.replace(/^\[!\w+\]\s*/, '');}
  }
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
      const highlightLanguage=lang==='manim'?'json':['python-calc','manim-python'].includes(lang)?'python':lang;
      if(hljs.getLanguage(highlightLanguage)){try{code.innerHTML=hljs.highlight(code.textContent,{language:highlightLanguage}).value;}catch{}}
      const bar=document.createElement('div');bar.className='code-bar no-export';
      bar.innerHTML=`<span>${escape(lang||'testo')}</span><button class="text-button">Copia</button>`;
      bar.querySelector('button').onclick=async()=>{await navigator.clipboard.writeText(code.textContent);bar.querySelector('button').textContent='Copiato';};
      if(final&&onExecute&&['python-calc','manim','manim-python'].includes(lang)){const run=document.createElement('button');run.className='text-button';run.textContent=lang.startsWith('manim')?'Renderizza animazione':'Calcola';run.onclick=()=>onExecute(lang,code.textContent);bar.append(run);}
      code.parentElement.prepend(bar);
      if(lang.startsWith('manim')&&final){const pre=code.parentElement,details=document.createElement('details'),summary=document.createElement('summary');details.className='animation-instructions';summary.textContent=lang==='manim-python'?'Codice Python Manim':'Istruzioni dell’animazione';pre.replaceWith(details);details.append(summary,pre);}
    }
  }
}

export function appendMedia(target,media,{api}={}) {
  for(const m of media||[]){
    const figure=document.createElement('figure'),url='/media/'+escape(m.path);
    if(!m.mime?.startsWith('image/')&&!m.mime?.startsWith('audio/')&&!m.mime?.startsWith('video/')){figure.className='document-output';figure.innerHTML=`<a href="${url}" download="${escape(m.name)}">▤ ${escape(m.name)} · Scarica</a>`;}
    else if(m.mime?.startsWith('video/')){figure.className='video-output';figure.innerHTML=`<video controls playsinline preload="metadata" src="${url}" aria-label="${escape(m.name)}"></video><figcaption><a href="${url}" download="${escape(m.name)}">Scarica MP4</a></figcaption>`;addVideoAudioControl(figure);}
    else if(m.mime?.startsWith('audio/')){
      figure.className='audio-output';figure.innerHTML=`<div class="audio-title">♫ ${escape(m.name)}</div><audio class="no-export" controls preload="metadata" src="${url}" aria-label="${escape(m.name)}"></audio><figcaption class="no-export audio-downloads"></figcaption>`;
      const caption=figure.querySelector('figcaption');
      for(const format of ['wav','mp3']){
        if(m.path.toLowerCase().endsWith('.'+format)){const a=document.createElement('a');a.href='/media/'+m.path;a.download=m.name;a.textContent='Scarica '+format.toUpperCase();caption.append(a);}
        else if(api){const button=document.createElement('button');button.type='button';button.className='text-button';button.textContent='Scarica '+format.toUpperCase();button.dataset.audioFormat=format;
          button.onclick=async()=>{
            caption.querySelector('.audio-export-error')?.remove();button.disabled=true;button.textContent='Conversione '+format.toUpperCase()+'…';
            try{const result=await api('/export/audio',{id:m.id,format});const a=document.createElement('a');a.href=result.url;a.download=result.name;document.body.append(a);a.click();a.remove();}
            catch(error){const notice=document.createElement('span');notice.className='audio-export-error render-error';notice.setAttribute('role','alert');notice.textContent=error.message;caption.append(notice);}
            finally{button.disabled=false;button.textContent='Scarica '+format.toUpperCase();}
          };caption.append(button);
        }
      }
      if(!m.path.toLowerCase().endsWith('.wav')&&!m.path.toLowerCase().endsWith('.mp3')){const a=document.createElement('a');a.href='/media/'+m.path;a.download=m.name;a.textContent='Scarica originale';caption.append(a);}
    }
    else{figure.className='image-output';figure.innerHTML=`<a href="${url}" target="_blank" rel="noopener"><img src="${url}" alt="${escape(m.name)}" loading="lazy"></a><figcaption class="no-export">${escape(m.name)} <a href="${url}" download>Scarica originale</a></figcaption>`;}
    target.append(figure);
  }
}
