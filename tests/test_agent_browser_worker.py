import json,os,socket,tempfile,threading,time,unittest
from pathlib import Path
from h3chat.browser_runtime import executable
from h3chat.platform_runtime import python_executable
from h3chat.residency import Session

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name=='nt' and executable(ROOT) and Path(python_executable(ROOT)).is_file(),'Windows private browser worker runtime unavailable')
class RealBrowserWorker(unittest.TestCase):
    def test_stop_worker_closes_its_browser_endpoint_and_releases_profile(self):
        with tempfile.TemporaryDirectory() as raw:
            folder=Path(raw)/'agent/browser';folder.mkdir(parents=True)
            session=Session(('browser-stop',),'tool',{'id':'browser-test','name':'Browser test'},{},{},Path(raw)/'worker.log')
            self.addCleanup(session.stop);cancel=threading.Event()
            session.start([python_executable(ROOT),'-X','utf8',ROOT/'native/agent-browser-worker.py'],ipc=True,cwd=ROOT)
            session.wait('hello',cancel,10);session.send({'op':'start','folder':str(folder)});started=session.wait('result',cancel,35)['result']
            self.assertTrue(started['started'])
            session.send({'op':'observe','args':{}});page=session.wait('result',cancel,10)['result'];self.assertEqual(page['url'],'about:blank')
            port=int(next(folder.glob('profile-*/DevToolsActivePort')).read_text().splitlines()[0])
            with socket.create_connection(('127.0.0.1',port),timeout=1):pass
            session.stop();self.assertIsNotNone(session.process.poll())
            deadline=time.monotonic()+5;closed=False
            while time.monotonic()<deadline:
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.1):pass
                except OSError:closed=True;break
                time.sleep(.1)
            self.assertTrue(closed,'The owned browser must stop when its worker stops.')
