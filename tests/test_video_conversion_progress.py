import errno,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.video_conversion_progress import write,read

class ProgressTests(unittest.TestCase):
    def test_transient_windows_replace_lock_retries_without_losing_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'progress.json';original=Path.replace;attempts=[]
            def replace(source,target):
                attempts.append(source)
                if len(attempts)<3:raise PermissionError('file in use')
                return original(source,target)
            with patch.object(Path,'replace',replace),patch('h3chat.video_conversion_progress.time.sleep'):
                self.assertTrue(write(path,'Conversione',done=1,total=2))
            self.assertEqual(read(path)['percent'],50);self.assertEqual(len(attempts),3)
            self.assertEqual(list(Path(folder).glob('*.tmp')),[])

    def test_progress_lock_does_not_fail_media_work_but_disk_full_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'progress.json';write(path,'Ultimo stato valido')
            with patch.object(Path,'replace',side_effect=PermissionError('locked')),patch('h3chat.video_conversion_progress.time.sleep'):
                self.assertFalse(write(path,'Aggiornamento'))
            self.assertEqual(read(path)['stage'],'Ultimo stato valido')
            with patch.object(Path,'write_text',side_effect=OSError(errno.ENOSPC,'disk full')):
                with self.assertRaises(OSError):write(path,'Aggiornamento')
