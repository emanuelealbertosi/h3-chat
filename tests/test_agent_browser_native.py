import http.server,socket,tempfile,threading,time,unittest
from pathlib import Path
from h3chat.agent_browser_native import Browser
from h3chat.agent_browser_page import web_url
from h3chat.agent_browser_proxy import PublicProxy
from h3chat.browser_runtime import executable

ROOT=Path(__file__).resolve().parents[1]
HTML=b'''<!doctype html><html><head><title>H3 Agent fixture</title></head><body>
<h1>Dynamic fixture</h1><button onclick="document.querySelector('#status').textContent='Clicked dynamically'">Change</button>
<p id="status">Before click</p><input aria-label="Name" placeholder="Name"><button onclick="document.querySelector('#status').textContent=document.querySelector('input').value">Echo</button>
<input type="password" aria-label="Password"><input type="file" aria-label="Upload file">
<select aria-label="Colour"><option value="red">Red</option><option value="blue">Blue</option></select>
<a href="/download">Download fixture</a><button style="display:none">Hidden</button>
<p style="margin-top:1600px">Bottom</p></body></html>'''


class BrowserPageValidation(unittest.TestCase):
    def test_only_web_urls_without_credentials_or_nonstandard_ports(self):
        for url in ('file:///C:/private','data:text/html,x','javascript:alert(1)','https://u:p@example.com','http://example.com:8788','https://example.com/\nsecret'):
            with self.subTest(url=url),self.assertRaises(ValueError):web_url(url)
        self.assertEqual(web_url('https://example.com/a?q=1'),'https://example.com/a?q=1')


@unittest.skipUnless(executable(ROOT),'H3 browser not installed')
class RealPrivateBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Fixture(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path=='/download':
                    raw=b'Original test download only';self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Disposition','attachment; filename="fixture.txt"')
                else:raw=HTML;self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def log_message(self,*args):pass
        cls.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join(3)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        def resolver(host,port):
            if host!='fixture.test':raise ValueError('fixture only')
            return socket.AF_INET,socket.SOCK_STREAM,6,('127.0.0.1',self.server.server_port)
        self.browser=Browser(ROOT,Path(self.temp.name),proxy_factory=lambda:PublicProxy(resolver=resolver))
        self.addCleanup(self.browser.close)

    @staticmethod
    def ref(page,name):return next(e['ref'] for e in page['elements'] if e['name']==name)

    def test_javascript_fill_select_stale_secret_and_screenshot(self):
        page=self.browser.open('http://fixture.test/')
        self.assertEqual(page['title'],'H3 Agent fixture');self.assertNotIn('Hidden',[e['name'] for e in page['elements']])
        old=self.ref(page,'Change');self.browser.run('click',{'ref':old})
        with self.assertRaisesRegex(ValueError,'scaduto'):self.browser.run('click',{'ref':old})
        page=self.browser.observe();self.assertIn('Clicked dynamically',page['text'])
        self.browser.run('fill',{'ref':self.ref(page,'Name'),'value':'A literal "quote"; no code'})
        page=self.browser.observe();self.browser.run('click',{'ref':self.ref(page,'Echo')})
        self.assertIn('A literal "quote"; no code',self.browser.observe()['text'])
        page=self.browser.observe();self.browser.run('select',{'ref':self.ref(page,'Colour'),'value':'blue'})
        for name in ('Password','Upload file'):
            page=self.browser.observe()
            with self.assertRaisesRegex(ValueError,'Password'):self.browser.run('fill',{'ref':self.ref(page,name),'value':'not sent'})
        result=self.browser.run('screenshot',{});self.assertGreater(result['bytes'],1000)
        self.assertTrue(Path(result['path']).read_bytes().startswith(b'\x89PNG'))
        process=self.browser.process;profile=self.browser.profile;self.browser.close()
        self.assertIsNotNone(process.poll());self.assertFalse(profile.exists())

    def test_original_download_and_fresh_tabs(self):
        page=self.browser.open('http://fixture.test/')
        self.browser.run('click',{'ref':self.ref(page,'Download fixture')})
        deadline=time.monotonic()+8;rows=[]
        while time.monotonic()<deadline:
            rows=self.browser.run('downloads',{})['downloads']
            if any(r.get('path') for r in rows):break
            time.sleep(.1)
        saved=next(r for r in rows if r.get('path'))
        self.assertEqual(Path(saved['path']).read_bytes(),b'Original test download only');self.assertEqual(saved['name'],'fixture.txt')
        page=self.browser.open('http://fixture.test/',new_tab=True);self.assertEqual(len(page['tabs']),2)
        with self.assertRaisesRegex(ValueError,'Scheda'):self.browser.run('tabs',{'tab':'unowned-target'})
