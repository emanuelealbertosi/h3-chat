import {build} from 'esbuild';
import {mkdir,cp,copyFile} from 'node:fs/promises';
await mkdir('static/vendor',{recursive:true});
await build({entryPoints:['ui/app.js'],outfile:'static/app.js',bundle:true,minify:true,format:'esm',platform:'browser',target:'es2022'});
await copyFile('node_modules/katex/dist/katex.min.css','static/vendor/katex.min.css');
await cp('node_modules/katex/dist/fonts','static/vendor/fonts',{recursive:true});
await copyFile('node_modules/highlight.js/styles/github.css','static/vendor/highlight.css');
await mkdir('licenses',{recursive:true});
for(const pkg of ['marked','dompurify','highlight.js','katex','mermaid','chart.js','docx','html-to-image','jspdf']) {
  for(const file of ['LICENSE','LICENSE.md','LICENSE.txt']) {
    try {await copyFile(`node_modules/${pkg}/${file}`,`licenses/${pkg}.txt`);break;}catch{}
  }
}
console.log('Interfaccia compilata: static/app.js (nessuna CDN a runtime)');
