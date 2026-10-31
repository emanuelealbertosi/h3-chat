import hashlib,io,tempfile,threading,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
from h3chat.downloads import download

class RecoveryTests(unittest.TestCase):
    def run_download(self,total=None,body=b'complete',digest=None,oversize=False):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'runtime.zip';part=target.with_name(target.name+'.part');part.write_bytes(b'par')
            class Whole(io.BytesIO):
                status=200
                headers={}
            error=urllib.error.HTTPError('https://example.test/a',416,'Range Not Satisfiable',{'Content-Range':f'bytes */{total}'} if total else {},None)
            with patch('h3chat.downloads.request',side_effect=[error,Whole(body+b'x' if oversize else body)]) as request:
                if oversize:
                    with self.assertRaisesRegex(ValueError,'manifest'):download('https://example.test/a',target,hashlib.sha256(body).hexdigest(),len(body),threading.Event(),lambda *_:None)
                    self.assertFalse(target.exists());return
                if digest:
                    with self.assertRaisesRegex(ValueError,'SHA-256'):download('https://example.test/a',target,digest,len(body),threading.Event(),lambda *_:None)
                    self.assertFalse(target.exists());return
                download('https://example.test/a',target,hashlib.sha256(body).hexdigest(),len(body),threading.Event(),lambda *_:None)
                self.assertEqual(target.read_bytes(),body);self.assertNotIn('Range',request.call_args_list[1].args[1]);self.assertFalse(part.exists())
    def test_rejected_range_restarts_verified_transfer(self):self.run_download(total=8)
    def test_416_without_size_restarts(self):self.run_download()
    def test_changed_remote_size_never_installs(self):self.run_download(total=99,oversize=True)
    def test_restart_still_checks_hash(self):self.run_download(digest='0'*64)
