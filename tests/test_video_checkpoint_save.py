import errno,json,os,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.video_resume import save


class CheckpointPublicationTests(unittest.TestCase):
    def test_transient_lock_keeps_old_checkpoint_until_atomic_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);target=folder/'scenes.json';target.write_text('{"old":true}')
            original=Path.replace;attempts=[]
            def replace(part,dest):
                attempts.append(part)
                self.assertEqual(json.loads(part.read_text()),{'new':True})
                if len(attempts)<3:
                    self.assertEqual(json.loads(target.read_text()),{'old':True})
                    raise PermissionError('temporarily open in Windows reader')
                return original(part,dest)
            with patch.object(Path,'replace',replace),patch('h3chat.video_resume.time.sleep') as sleep:
                save(folder,{'new':True})
            self.assertEqual(len(attempts),3);self.assertEqual(sleep.call_count,2)
            self.assertEqual(json.loads(target.read_text()),{'new':True})
            self.assertEqual(list(folder.glob('*.writing')),[])

    def test_persistent_lock_preserves_both_valid_versions_and_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);target=folder/'scenes.json';target.write_text('{"old":true}')
            with patch.object(Path,'replace',side_effect=PermissionError('locked')) as replace,patch('h3chat.video_resume.time.sleep'):
                with self.assertRaises(PermissionError):save(folder,{'new':True})
            self.assertEqual(replace.call_count,12)
            self.assertEqual(json.loads(target.read_text()),{'old':True})
            staged=list(folder.glob('*.writing'));self.assertEqual(len(staged),1)
            self.assertEqual(json.loads(staged[0].read_text()),{'new':True})

    def test_other_io_errors_are_not_silenced_or_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(Path,'replace',side_effect=OSError(errno.ENOSPC,'full')) as replace,patch('h3chat.video_resume.time.sleep') as sleep:
                with self.assertRaises(OSError) as caught:save(Path(tmp),{'new':True})
            self.assertEqual(caught.exception.errno,errno.ENOSPC);self.assertEqual(replace.call_count,1);sleep.assert_not_called()

    def test_staging_does_not_overwrite_previous_failed_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);stale=folder/'scenes.writing';stale.write_text('{"previous":true}')
            save(folder,{'current':True})
            self.assertEqual(json.loads(stale.read_text()),{'previous':True})
            self.assertEqual(json.loads((folder/'scenes.json').read_text()),{'current':True})

    @unittest.skipUnless(os.name=='nt','Windows sharing semantics')
    def test_real_windows_reader_releases_delete_lock(self):
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);target=folder/'scenes.json';target.write_text('{"old":true}')
            handle=kernel.CreateFileW(str(target),0x80000000,3,None,3,0x80,None)
            self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
            timer=threading.Timer(.15,lambda:kernel.CloseHandle(handle));timer.start()
            try:save(folder,{'new':True})
            finally:timer.join()
            self.assertEqual(json.loads(target.read_text()),{'new':True})


if __name__=='__main__':unittest.main()
