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
 const covered=[],visible=[],textBoxes=[],images=[],referenceRegions=REFERENCE_REGIONS;
 if(STRICT_CHECKS){
  // Hit-testing alone mistakes a transparent positioned overlay for an opaque
  // cover. Ignore transparent containers and ancestor backgrounds; inspect the
  // painted foreground instead, keeping intentional image tints possible.
  function blockedAt(target,x,y){
   if(x<0||y<0||x>=w||y>=h)return true;
   for(const hit of d.elementsFromPoint(x,y)){
    if(hit===target||target.contains(hit))return false;
    if(hit.contains(target))continue;
    const s=d.defaultView.getComputedStyle(hit);if(parseFloat(s.opacity)<.95)continue;
    if(['IMG','VIDEO','CANVAS','svg','SVG'].includes(hit.tagName))return true;
    const rgba=s.backgroundColor.match(/^rgba?\(([^)]+)\)/),parts=rgba?rgba[1].split(',').map(Number):[];
    if(parts.length===3||parts.length===4&&parts[3]>=.95)return true;
    for(const n of hit.childNodes)if(n.nodeType===3&&n.textContent.trim()){
     const r=d.createRange();r.selectNodeContents(n);
     if(Array.from(r.getClientRects()).some(b=>x>=b.left&&x<=b.right&&y>=b.top&&y<=b.bottom))return true;
    }
   }
   return false;
  }
  const walk=d.createTreeWalker(root,4);let node;
  while((node=walk.nextNode())){
   const text=(node.textContent||'').trim().replace(/\s+/g,' '),el=node.parentElement;
   if(!text||!el||el.closest('head,title,style,script,noscript,defs,clipPath,mask,pattern,[hidden],[aria-hidden="true"]'))continue;
   let hidden=false,clips=[];
   for(let p=el;p&&root.contains(p);p=p.parentElement){
    const s=d.defaultView.getComputedStyle(p);
    if(s.display==='none'||s.visibility==='hidden'||parseFloat(s.opacity)===0)hidden=true;
    if(/hidden|clip|scroll|auto/.test(s.overflowX+' '+s.overflowY))clips.push(p.getBoundingClientRect());
   }
   const range=d.createRange();range.selectNodeContents(node);
   const rects=Array.from(range.getClientRects()).filter(r=>r.width>1&&r.height>1);
   let bad=hidden||!rects.length;
   for(const r of rects){
    if(r.left<bounds.left-2||r.top<bounds.top-2||r.right>bounds.right+2||r.bottom>bounds.bottom+2||clips.some(b=>r.left<b.left-2||r.top<b.top-2||r.right>b.right+2||r.bottom>b.bottom+2))bad=true;
    let blocked=0;
    for(const f of [.15,.5,.85]){
     if(blockedAt(el,r.left+r.width*f,r.top+r.height*.5))blocked++;
    }
    if(blocked>=2)bad=true;
   }
   if(bad){if(covered.length<30)covered.push({text:text.slice(0,200),reason:hidden?'testo nascosto':'testo tagliato o coperto'});}
   else{visible.push(text);textBoxes.push({text,boxes:rects.map(r=>({x:r.x,y:r.y,width:r.width,height:r.height}))});}
  }
  for(const el of root.querySelectorAll('img[data-asset-id]')){
   const r=el.getBoundingClientRect(),s=d.defaultView.getComputedStyle(el);
   const clips=[r];let hidden=false;
   for(let p=el;p&&root.contains(p);p=p.parentElement){const cs=d.defaultView.getComputedStyle(p);if(cs.display==='none'||cs.visibility==='hidden'||parseFloat(cs.opacity)===0)hidden=true;if(/hidden|clip|scroll|auto/.test(cs.overflowX+' '+cs.overflowY))clips.push(p.getBoundingClientRect());}
   let hits=0;
   for(const fx of [.25,.5,.75])for(const fy of [.25,.5,.75])if(!blockedAt(el,r.left+r.width*fx,r.top+r.height*fy))hits++;
   const visibleImage=!hidden&&el.naturalWidth>0&&hits>=3;
   const nw=el.naturalWidth||1,nh=el.naturalHeight||1,fit=s.objectFit;
   const scale=fit==='cover'?Math.max(r.width/nw,r.height/nh):fit==='none'?1:Math.min(r.width/nw,r.height/nh);
   const dw=fit==='fill'?r.width:nw*scale,dh=fit==='fill'?r.height:nh*scale;
   const pos=s.objectPosition.split(' '),offset=(v,free)=>v?.endsWith('%')?parseFloat(v)/100*free:parseFloat(v)||0;
   const ox=r.left+offset(pos[0],r.width-dw),oy=r.top+offset(pos[1]||pos[0],r.height-dh);
   const inset=s.clipPath.match(/^inset\(([^)]+)\)$/);
   if(inset){const p=inset[1].split('round')[0].trim().split(/\s+/),a=[p[0],p[1]||p[0],p[2]||p[0],p[3]||p[1]||p[0]],n=(v,size)=>v.endsWith('%')?parseFloat(v)*size/100:parseFloat(v)||0;clips.push({left:r.left+n(a[3],r.width),right:r.right-n(a[1],r.width),top:r.top+n(a[0],r.height),bottom:r.bottom-n(a[2],r.height)});}
   const referenceText=referenceRegions.filter(t=>t.id===el.dataset.assetId).map(t=>{
    const [x,y,bw,bh]=t.box;let shown=0;
    for(const fx of [.15,.5,.85])for(const fy of [.2,.5,.8]){const px=ox+(x+bw*fx)*dw,py=oy+(y+bh*fy)*dh;if(clips.every(b=>px>=b.left&&px<=b.right&&py>=b.top&&py<=b.bottom)&&!blockedAt(el,px,py))shown++;}
    return {text:t.text,visible:visibleImage&&shown>=5,box:{x:ox+x*dw,y:oy+y*dh,width:bw*dw,height:bh*dh}};
   });
   images.push({id:el.dataset.assetId,x:r.x,y:r.y,width:r.width,height:r.height,visible:visibleImage,reference_text:referenceText});
  }
 }
 return {width:w,height:h,out_of_bounds:out,small_text:small,poster_overflow:poster,covered_text:covered,visible_text:visible.join('\n'),text_boxes:textBoxes,images,issue:out.length>0||poster.length>0||covered.length>0};
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
    regions=request.get('reference_text_regions',[]);ids={m['id'] for m in media}
    if not isinstance(regions,list) or len(regions)>1000:raise ValueError('Troppi testi del riferimento da verificare.')
    import math
    for row in regions:
        box=row.get('box',[])
        if row.get('id') not in ids or not isinstance(row.get('text'),str) or len(row['text'])>4000 or len(box)!=4 or any(type(n) not in (int,float) or not math.isfinite(n) for n in box) or min(box)<-.000001 or min(box[2:])<=0 or box[0]+box[2]>1.000001 or box[1]+box[3]>1.000001:raise ValueError('Area testuale del riferimento non valida.')
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
        while True:
            # Edge's launcher may exit while its private browser child starts.
            if time.monotonic()>deadline:raise RuntimeError('Il browser di verifica non si è avviato.')
            try:
                lines=portfile.read_text().splitlines()
                if lines:
                    port=int(lines[0]);break
            except (OSError,ValueError):pass
            time.sleep(.1)
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
        report=cdp.evaluate(MEASURE.replace('WIDTH',str(width)).replace('HEIGHT',str(height)).replace('STRICT_CHECKS','true' if request.get('strict_reference') is True else 'false').replace('REFERENCE_REGIONS',json.dumps(regions,ensure_ascii=False)))
        (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
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
