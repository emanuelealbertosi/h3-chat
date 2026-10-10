import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import PIL
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

class ImageSizeWorkerTests(unittest.TestCase):
    def test_isolated_runtime_reads_all_references_and_exif_without_torch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worker = root/'native/image-size-worker.py'
            worker.parent.mkdir()
            shutil.copyfile(ROOT/'native/image-size-worker.py', worker)
            shutil.copytree(Path(PIL.__file__).parent, root/'runtime/vision/packages/PIL', ignore=shutil.ignore_patterns('__pycache__'))
            paths = []
            for name, size, orientation in (('landscape.png',(640,480),None), ('portrait.jpg',(400,300),6), ('reference.webp',(300,500),None)):
                path = root/name
                image = Image.new('RGB',size)
                if orientation:
                    exif = Image.Exif();exif[274] = orientation
                    image.save(path,exif=exif)
                else:image.save(path)
                paths.append(str(path))
            # The host interpreter has no global Pillow; only this worker's
            # private runtime can supply it. No document runtime is on sys.path.
            code = "import runpy,sys;sys.path=[p for p in sys.path if 'documents' not in p and 'site-packages' not in p];assert 'PIL' not in sys.modules;runpy.run_path(sys.argv[1],run_name='__main__');assert 'torch' not in sys.modules"
            result = subprocess.run([sys.executable,'-I','-X','utf8','-c',code,str(worker)],input=json.dumps({'paths':paths})+'\n',capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            events = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(events[0]['event'],'hello')
            self.assertEqual(events[1],{'event':'result','result':{'sizes':[[640,480],[300,400],[300,500]]}})

    def test_missing_private_pillow_reports_setup_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker = Path(tmp)/'native/image-size-worker.py'
            worker.parent.mkdir()
            shutil.copyfile(ROOT/'native/image-size-worker.py',worker)
            code = "import runpy,sys;sys.path=[p for p in sys.path if 'documents' not in p and 'site-packages' not in p];runpy.run_path(sys.argv[1],run_name='__main__')"
            result = subprocess.run([sys.executable,'-I','-X','utf8','-c',code,str(worker)],input='{"paths":["missing.png"]}\n',capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            event = json.loads(result.stdout.splitlines()[1])
            self.assertEqual(event['event'],'error')
            self.assertIn('reinstalla',event['message'])

if __name__ == '__main__':unittest.main()
