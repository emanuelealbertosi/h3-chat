import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.H3_PLAYWRIGHT||'playwright');
const out=new URL('../work/qa/',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1');await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
try{
 await page.goto(process.env.H3_TEST_URL||'http://127.0.0.1:8788');await page.waitForSelector('#new-chat');await page.waitForFunction(()=>document.querySelector('#model-name').textContent!=='Scegli un modello'||document.querySelector('#setup-nudge'));
 await page.screenshot({path:out+'/home.png'});
 await page.click('#settings-open');await page.selectOption('[data-setting="profile"]','cpu');await page.selectOption('[data-setting="chat_model"]','qwen3-06');
 await page.screenshot({path:out+'/setup.png'});await page.click('#settings-save');
 await page.click('#new-chat');await page.waitForSelector('.chat-row.active');await page.fill('#prompt','Rispondi solo con il risultato di 7 per 8.');await page.click('#send');
 await page.waitForSelector('.message.assistant .message-actions button',{timeout:120000});
 const response=await page.locator('.message.assistant .message-content').innerText();if(!response.includes('56'))throw Error('Risposta reale inattesa: '+response);
 console.log('Risposta CPU reale: '+response);
 await page.click('#canvas-toggle');await page.click('#canvas-write');
 const source=`# Dati, formule e idee

Questo è un **documento di collaudo** del canvas, con testo modificabile, formule e grafici numerici.

## Una relazione precisa

La funzione è $f(x)=x^2$.

$$
\\int_0^2 x^2\\,dx = \\frac{8}{3}
$$

| x | f(x) |
|---|---|
| 0 | 0 |
| 1 | 1 |
| 2 | 4 |
| 3 | 9 |

\`\`\`python
def quadrato(x: float) -> float:
    return x ** 2
\`\`\`

\`\`\`chart
{"type":"line","title":"Crescita quadratica","xLabel":"x","yLabel":"f(x)","labels":["0","1","2","3"],"datasets":[{"label":"x²","data":[0,1,4,9]}]}
\`\`\`

\`\`\`mermaid
flowchart LR
 A[Prompt] --> B{Router}
 B --> C[Chat]
 B --> D[Immagine]
 C --> E[Canvas]
 D --> E
\`\`\`
`;
 await page.fill('#canvas-title','Collaudo canvas H3');await page.fill('#canvas-source',source);await page.click('#canvas-preview-tab');
 await page.waitForSelector('#canvas-preview .diagram svg',{timeout:30000});await page.waitForSelector('#canvas-preview canvas');
 for(const label of ['Prompt','Router','Canvas']){if(!(await page.locator('#canvas-preview .diagram svg').textContent()).includes(label))throw Error('Etichetta diagramma mancante: '+label);}
 if(await page.locator('#canvas-preview .katex').count()<2)throw Error('Formule non renderizzate');
 if(await page.locator('#canvas-preview .render-error').count())throw Error(await page.locator('#canvas-preview .render-error').innerText());
 await page.screenshot({path:out+'/canvas-ui.png'});
 for(const format of ['docx','pdf','png']){
   const downloadPromise=page.waitForEvent('download',{timeout:90000});await page.click(`[data-export="${format}"]`);const download=await downloadPromise;await download.saveAs(out+'/canvas.'+format);console.log('Export '+format+' OK');
   await page.waitForFunction(()=>!document.querySelector('#canvas-panel').classList.contains('exporting'));
 }
 await page.reload();await page.waitForSelector('.chat-link');await page.locator('.chat-link').first().click();await page.click('#canvas-toggle');await page.waitForSelector('#canvas-preview .diagram svg');
 if(!(await page.locator('#canvas-preview').innerText()).includes('Crescita quadratica'))throw Error('Canvas non persistito');
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:out+'/mobile.png'});
 const over=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);if(over)throw Error('Overflow orizzontale mobile');
 if(errors.length)throw Error(errors.join('\n'));
 await writeFile(out+'/browser-result.json',JSON.stringify({passed:true,response,errors,exports:['docx','pdf','png']},null,2));
 console.log('Browser, persistenza, rendering e 3 export OK');
}finally{await browser.close();}
