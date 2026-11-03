import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from PIL import Image,ImageDraw

WORKER=Path(__file__).resolve().parents[1]/'native/motion-atlas-worker.py'
spec=importlib.util.spec_from_file_location('motion_atlas_cpu',WORKER)
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)


class AtlasTests(unittest.TestCase):
    def test_cell_registration_ignores_small_neighbor_piece(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source=folder/'parts.png';target=folder/'alpha.png'
            image=Image.new('RGB',(400,600),'#ff00ff');draw=ImageDraw.Draw(image)
            for i in range(6):
                x=(i%2)*200+65;y=(i//2)*200+30
                draw.rounded_rectangle((x,y,x+70,y+140),radius=15,fill='#347d79')
            draw.rectangle((195,260,205,290),fill='#173d48')
            image.save(source);proof=worker.prepare(source,target)
            self.assertEqual(proof['parts']['upper_arm']['x'],65)
            self.assertEqual(proof['parts']['upper_arm']['width'],71)
            with Image.open(target) as alpha:
                self.assertEqual(alpha.mode,'RGBA');self.assertEqual(alpha.getpixel((0,0))[3],0)

    def test_bad_background_fails_and_ipc_handshake_is_flushed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'white.png';Image.new('RGB',(300,300),'white').save(source)
            with self.assertRaises(ValueError):worker.prepare(source,Path(tmp)/'alpha.png')
            image=Image.new('RGB',(300,300),'#fff7ff');ImageDraw.Draw(image).rectangle((0,0,299,299),outline='#ff00ff',width=2);image.save(source)
            with self.assertRaises(ValueError):worker.prepare(source,Path(tmp)/'alpha.png')
            # Inject the same document runtime used by this interpreter before
            # starting the isolated script; embedded Python ignores PYTHONPATH.
            code='import runpy,sys;sys.path[:0]='+repr(sys.path)+';runpy.run_path('+repr(str(WORKER))+',run_name="__main__")'
            child=subprocess.Popen([sys.executable,'-X','utf8','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                self.assertEqual(json.loads(child.stdout.readline())['event'],'hello')
                out,_=child.communicate(json.dumps({'input':str(source),'output':str(Path(tmp)/'alpha.png')})+'\n',timeout=20)
                self.assertEqual(json.loads(out)['event'],'error')
            finally:
                if child.poll() is None:child.kill();child.communicate()
