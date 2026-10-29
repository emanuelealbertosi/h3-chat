"""Private CPU browser owned by one Agent worker. No personal profile access."""
import os,re,secrets,shutil,subprocess,time
from pathlib import Path
from .agent_browser_cdp import CDP
from .agent_browser_page import Page,web_url
from .agent_browser_proxy import PublicProxy
from .browser_runtime import executable
from .agent_browser_process import start


class Browser:
    def __init__(self,root,folder,*,proxy_factory=PublicProxy):
        self.root=Path(root);self.folder=Path(folder).resolve();self.folder.mkdir(parents=True,exist_ok=True)
        self.download_folder=self.folder/'downloads';self.download_folder.mkdir(exist_ok=True)
        self.profile=self.folder/('profile-'+secrets.token_hex(8));self.profile.mkdir()
        self.process=None;self.cdp=None;self.proxy=None;self.tabs={};self.current=None;self.downloads={};self.closed=False
        self.log=(self.folder/'browser.log').open('ab')
        try:
            exe=executable(root)
            if not exe:raise ValueError('Installa il browser H3 dal setup prima di usare il browser Agent.')
            self.proxy=proxy_factory()
            flags=['--headless=new','--edge-skip-compat-layer-relaunch','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking',
                '--disable-component-update','--disable-extensions','--disable-sync','--disable-translate','--disable-features=MediaRouter,OptimizationHints,AutofillServerCommunication',
                '--disable-quic','--force-webrtc-ip-handling-policy=disable_non_proxied_udp','--disable-domain-reliability','--disable-breakpad',
                '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--window-size=1280,900',
                '--proxy-server='+self.proxy.address,'--proxy-bypass-list=<-loopback>','--user-data-dir='+str(self.profile),'about:blank']
            self.process=start([str(exe),*flags],self.log,self.folder)
            deadline=time.monotonic()+25;active=self.profile/'DevToolsActivePort'
            while time.monotonic()<deadline:
                if self.process.poll() not in (None,0):raise RuntimeError('Il browser Agent non si è avviato. Consulta browser.log.')
                if active.is_file():
                    lines=active.read_text().splitlines()
                    if len(lines)>=2 and lines[0].isdigit() and lines[1].startswith('/devtools/browser/'):
                        self.cdp=CDP('ws://127.0.0.1:'+lines[0]+lines[1],self.event);break
                time.sleep(.1)
            if not self.cdp:raise TimeoutError('Avvio browser Agent scaduto.')
            self.cdp.call('Browser.setDownloadBehavior',{'behavior':'allowAndName','downloadPath':str(self.download_folder),'eventsEnabled':True})
            self.cdp.call('Browser.setPermission',{'permission':{'name':'clipboard-read'},'setting':'denied'})
            self.cdp.call('Browser.setPermission',{'permission':{'name':'clipboard-write'},'setting':'denied'})
            for item in self.cdp.call('Target.getTargets').get('targetInfos',[]):
                if item.get('type')=='page' and item.get('url')=='about:blank':self.attach(item['targetId']);break
            if not self.current:self.open('about:blank',internal=True)
        except BaseException:self.close();raise

    def event(self,event):
        method=event.get('method');params=event.get('params',{});guid=params.get('guid','')
        if method=='Browser.downloadWillBegin' and re.fullmatch(r'[a-zA-Z0-9-]{1,80}',guid):
            self.downloads[guid]={'id':guid,'url':params.get('url','')[:4096],'name':Path(params.get('suggestedFilename','download')).name[:200],'state':'inProgress','bytes':0}
        elif method=='Browser.downloadProgress' and guid in self.downloads:
            row=self.downloads[guid];row.update(state=params.get('state','inProgress'),bytes=params.get('receivedBytes',0),total=params.get('totalBytes',0))
            if row['bytes']>128*1024**2 and row['state']=='inProgress':
                # Cancel outside the CDP event callback to avoid re-entering its lock.
                row['oversize']=True

    def pump(self):
        self.cdp.call('Browser.getVersion')
        for guid,row in self.downloads.items():
            if row.get('oversize') and row['state']=='inProgress':self.cdp.call('Browser.cancelDownload',{'guid':guid});row['state']='canceled'

    def attach(self,target):
        if target in self.tabs:self.current=target;return self.tabs[target]
        session=self.cdp.call('Target.attachToTarget',{'targetId':target,'flatten':True})['sessionId']
        page=Page(self.cdp,session);page.call('Page.enable');page.call('Runtime.enable');page.call('DOM.enable');page.call('Network.enable')
        page.call('Network.setBlockedURLs',{'urls':['file://*','ftp://*','chrome://*','edge://*','devtools://*']})
        page.call('Emulation.setDeviceMetricsOverride',{'width':1280,'height':900,'deviceScaleFactor':1,'mobile':False})
        page.call('Page.setInterceptFileChooserDialog',{'enabled':True})
        self.tabs[target]=page;self.current=target;return page

    def sync(self):
        targets=[]
        for target in self.cdp.call('Target.getTargets').get('targetInfos',[]):
            if target.get('type')!='page':continue
            url=target.get('url','')
            try:
                if url!='about:blank':web_url(url)
            except ValueError:
                # Chromium/Edge may add a welcome/settings tab to a fresh
                # private profile. It is never an Agent page or an action target.
                self.cdp.call('Target.closeTarget',{'targetId':target['targetId']});continue
            targets.append(target)
        existing={t['targetId'] for t in targets}
        for target in list(self.tabs):
            if target not in existing:self.tabs.pop(target)
        for item in targets:
            if item['targetId'] not in self.tabs:
                if len(self.tabs)>=5:self.cdp.call('Target.closeTarget',{'targetId':item['targetId']});continue
                previous=self.current;self.attach(item['targetId']);self.current=previous or item['targetId']
        if self.current not in self.tabs:self.current=next(iter(self.tabs),None)
        return [{'id':t['targetId'],'url':t.get('url',''),'title':t.get('title',''),'selected':t['targetId']==self.current} for t in targets if t['targetId'] in self.tabs]

    def open(self,url,new_tab=False,internal=False):
        if not internal:web_url(url)
        if new_tab or not self.current:
            if len(self.tabs)>=5:raise ValueError('Sono già aperte cinque schede Agent. Riusa una scheda.')
            target=self.cdp.call('Target.createTarget',{'url':'about:blank'})['targetId'];page=self.attach(target)
        else:page=self.tabs[self.current]
        page.refs={};result=page.call('Page.navigate',{'url':url})
        if result.get('errorText'):raise ValueError('Navigazione non riuscita: '+result['errorText'][:300])
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            time.sleep(.1)
            try:
                ready=self.cdp.evaluate('document.readyState',page.session)
                if ready in ('interactive','complete'):break
            except RuntimeError:continue
        return self.observe()

    def observe(self):
        self.pump();tabs=self.sync()
        if not self.current:raise ValueError('Nessuna scheda Agent aperta. Apri una pagina.')
        return self.tabs[self.current].observe()|{'tab':self.current,'tabs':tabs,'downloads':self.download_status()}

    def download_status(self):
        result=[]
        for guid,row in self.downloads.items():
            value=dict(row);path=self.download_folder/guid
            if row['state']=='completed' and not row.get('oversize') and path.is_file() and not path.is_symlink() and not (path.stat().st_file_attributes&0x400 if os.name=='nt' else False):
                size=path.stat().st_size
                if size<=128*1024**2:value.update(path=str(path),bytes=size)
            result.append(value)
        return result[-30:]

    def run(self,operation,args):
        if operation=='open':return self.open(args['url'],args.get('new_tab',False))
        if operation=='observe':return self.observe()
        if operation=='tabs':
            self.sync()
            if args.get('tab'):
                if args['tab'] not in self.tabs:raise ValueError('Scheda Agent non disponibile.')
                self.current=args['tab']
            return self.observe()
        if operation=='downloads':self.pump();return {'downloads':self.download_status()}
        page=self.tabs.get(self.current)
        if not page:raise ValueError('Apri prima una pagina Agent.')
        if operation in ('click','fill','select'):return page.act(operation,args['ref'],args.get('value'))
        if operation=='scroll':return page.scroll(args['direction'],args.get('amount',600))
        if operation=='screenshot':return page.screenshot(self.folder/('screenshot-'+secrets.token_hex(8)+'.png'))
        if operation=='press':
            if not page.fresh:raise ValueError('Osserva nuovamente la pagina prima di premere un tasto.')
            keys={'Enter':13,'Escape':27,'Tab':9,'ArrowDown':40,'ArrowUp':38,'ArrowLeft':37,'ArrowRight':39}
            key=args.get('key')
            if key not in keys:raise ValueError('Tasto browser non consentito.')
            for event in ('keyDown','keyUp'):page.call('Input.dispatchKeyEvent',{'type':event,'key':key,'windowsVirtualKeyCode':keys[key],'nativeVirtualKeyCode':keys[key]})
            page.refs={};page.fresh=False;return {'pressed':key,'observe_again':True}
        raise ValueError('Operazione browser non disponibile.')

    def close(self):
        if self.closed:return
        self.closed=True
        if self.cdp:
            try:self.cdp.call('Browser.close',timeout=2)
            except (OSError,ValueError,RuntimeError,TimeoutError):pass
            self.cdp.close()
        if self.process:
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=3)
            if os.name=='nt':self.process.close()
            else:
                import signal
                try:os.killpg(self.process.pid,signal.SIGTERM)
                except ProcessLookupError:pass
        if self.proxy:self.proxy.close()
        self.log.close()
        # Only this fresh, internally named profile is disposable. Downloads
        # and screenshots remain available for the Agent artifact registration.
        if self.profile.parent==self.folder and self.profile.name.startswith('profile-'):
            shutil.rmtree(self.profile,ignore_errors=True)
