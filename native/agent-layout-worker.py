"""Read-only, offline CPU measurement of authorized HTML slides."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('h3_capture',ROOT/'native/infographic-worker.py')
capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
# Reuse the existing private CDP transport and process-tree cleanup. Importing
# that worker does not invoke its __main__ entry point or load a GPU model.
emit=capture.emit

MEASURE=r'''Array.from(document.querySelectorAll('iframe'),(frame)=>{
 const d=frame.contentDocument,w=WIDTH,h=HEIGHT,area=d.querySelector('[data-h3-background-content]');
 const bounds=area?area.getBoundingClientRect():{left:0,top:0,right:w,bottom:h};
 const root=d.querySelector('[data-h3-content-canvas]')||d.body,out=[],small=[],poster=[];
 for(const el of root.querySelectorAll('h1,h2,h3,h4,h5,h6,p,li,pre,code,td,th,figure,img,svg,div,span')){
  if(el.closest('[hidden],defs,clipPath,mask,pattern'))continue;
  const style=d.defaultView.getComputedStyle(el),r=el.getBoundingClientRect();
  if(style.display==='none'||style.visibility==='hidden'||!r.width||!r.height)continue;
  const text=(el.innerText||el.getAttribute('alt')||'').trim().replace(/\s+/g,' ').slice(0,130);
  if(!text&&!['IMG','svg','SVG'].includes(el.tagName))continue;
  if(el.children.length&&['DIV','SPAN','FIGURE'].includes(el.tagName))continue;
  if(r.left<bounds.left-2||r.top<bounds.top-2||r.right>bounds.right+2||r.bottom>bounds.bottom+2){
   if(out.length<25)out.push({tag:el.tagName,text,box:{x:Math.round(r.x),y:Math.round(r.y),width:Math.round(r.width),height:Math.round(r.height)}});
  }
  if(text&&parseFloat(style.fontSize)<12&&small.length<10)small.push({text,font:style.fontSize});
 }
 // Text may fit on the page while being clipped by a reserved poster zone.
 // Measure actual text runs, including SVG text, against that local boundary.
 // Decorative shapes are allowed to bleed intentionally inside their zone.
 for(const zone of root.querySelectorAll('[data-poster-zone]')){
  const box=zone.getBoundingClientRect(),walk=d.createTreeWalker(zone,4);let node;
  while((node=walk.nextNode())&&poster.length<25){
   const text=(node.textContent||'').trim().replace(/\s+/g,' ');if(!text)continue;
   const el=node.parentElement;if(!el||el.closest('defs,clipPath,mask,pattern'))continue;
   const id=zone.dataset.posterZone;let hidden=false;
   for(let p=el;p&&zone.contains(p);p=p.parentElement){const style=d.defaultView.getComputedStyle(p);if(style.display==='none'||style.visibility==='hidden'||parseFloat(style.opacity)===0)hidden=true;}
   if(hidden){poster.push({id,text:text.slice(0,130),reason:'testo nascosto'});continue;}
   const range=d.createRange();range.selectNodeContents(node);const rects=Array.from(range.getClientRects()).filter(r=>r.width&&r.height);
   if(!rects.length){poster.push({id,text:text.slice(0,130),reason:'testo non renderizzato'});continue;}
   for(const r of rects)if(r.left<box.left-2||r.top<box.top-2||r.right>box.right+2||r.bottom>box.bottom+2){
    poster.push({id,text:text.slice(0,130),reason:'testo tagliato dal riquadro',box:{x:Math.round(r.x),y:Math.round(r.y),width:Math.round(r.width),height:Math.round(r.height)}});break;
   }
  }
 }
 return {width:w,height:h,out_of_bounds:out,small_text:small,poster_overflow:poster,issue:out.length>0||poster.length>0};
})'''

def run(request):
    from h3chat.downloads import safe_join
    from h3chat.slides import FORMATS,validate_content,encode
    from h3chat.infographic_document import document
    from h3chat.engine import CREATE_NO_WINDOW
    from h3chat.platform_runtime import is_macos
    data=Path(request['data']).resolve();folder=Path(request['folder']).resolve()
    if not folder.is_relative_to(data/'outputs'):raise ValueError('Cartella di verifica non autorizzata.')
    deck=request['deck'];media=request['media'];validate_content(encode(deck),media)
    if deck.get('engine')!='llm' or not 1<=len(deck['pages'])<=5:raise ValueError('Verifica: seleziona da 1 a 5 slide HTML.')
    for item in media:
        if not item.get('path','').startswith(('uploads/','outputs/')):raise ValueError('Asset non autorizzato.')
        safe_join(data,item['path'])
    folder.mkdir(parents=True,exist_ok=True);source=folder/'measurement.html'
    source.write_text(document(ROOT,data,deck,media),encoding='utf8')
    width,height=FORMATS[deck['format']];height=round(height)
    if os.name!='nt':
        choices=list((ROOT/'runtime/browser').rglob('headless_shell'))+list((ROOT/'runtime/browser').rglob('chrome-headless-shell'))
    else:
        choices=[Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe']
    executable=next((p for p in choices if p.is_file()),None)
    if not executable:raise ValueError('Browser di verifica CPU non disponibile. Controlla l’installazione documenti.')
    profile=folder/'browser-profile';profile.mkdir(exist_ok=True);portfile=profile/'DevToolsActivePort';portfile.unlink(missing_ok=True)
    process=subprocess.Popen([str(executable),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
        '--disable-background-networking','--disable-component-update','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',
        '--user-data-dir='+str(profile),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=CREATE_NO_WINDOW)
    cdp=None
    try:
        deadline=time.monotonic()+40
        while not portfile.is_file():
            # Edge's launcher may exit while its private browser child starts.
            if time.monotonic()>deadline:raise RuntimeError('Il browser di verifica non si è avviato.')
            time.sleep(.1)
        port=int(portfile.read_text().splitlines()[0])
        with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/json/list',timeout=10) as response:tabs=json.load(response)
        cdp=capture.CDP(next(t['webSocketDebuggerUrl'] for t in tabs if t['type']=='page'))
        cdp.call('Page.enable');cdp.call('Network.enable');cdp.call('Network.setBlockedURLs',{'urls':['http://*','https://*','ws://*','wss://*']})
        cdp.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':False})
        cdp.call('Page.navigate',{'url':source.as_uri()})
        while cdp.evaluate("document.readyState==='complete'&&document.querySelectorAll('iframe').length==="+str(len(deck['pages']))) is not True:
            if time.monotonic()>deadline:raise RuntimeError('Caricamento delle pagine di verifica non riuscito.')
            time.sleep(.1)
        cdp.evaluate("Promise.all([...document.querySelectorAll('iframe')].map(async f=>{await f.contentDocument.fonts.ready;await Promise.all([...f.contentDocument.images].map(i=>i.decode().catch(()=>{})));}))",True)
        cdp.evaluate((ROOT/'static/vendor/infographic-renderer.js').read_text(encoding='utf8'))
        cdp.evaluate('Promise.all(Array.from(document.querySelectorAll("iframe"),f=>H3Infographic.prepare(f.contentDocument,'+str(height)+',{},5)))',True)
        report=cdp.evaluate(MEASURE.replace('WIDTH',str(width)).replace('HEIGHT',str(height)))
        return {'pages':report,'renderer':'CPU offline','visual_review':False}
    finally:
        if cdp:
            try:cdp.call('Browser.close')
            except (OSError,RuntimeError):pass
            cdp.sock.close()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait()

if __name__=='__main__':
    emit('hello',engine='agent-layout-cpu')
    try:
        private_tree=capture.own_process_tree();emit('result',result=run(json.loads(sys.stdin.readline())))
    except Exception as error:
        import traceback
        traceback.print_exc();emit('error',message=str(error))
