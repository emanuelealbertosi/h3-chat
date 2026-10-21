import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from h3chat.video_edit import resplit_origin


class ResplitOriginTests(unittest.TestCase):
    def test_follows_completed_timeline_chain_to_original_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'original.mp4').write_bytes(b'video')
            store=SimpleNamespace(one=Mock(side_effect=[{'id':'b'*32},None]),gallery=SimpleNamespace(get=Mock(return_value={'mime':'video/mp4','path':'original.mp4'})))
            app=SimpleNamespace(data=root,store=store)
            with patch('h3chat.video_edit.checkpoint',return_value={'revision_source':'c'*32}):
                result=resplit_origin(app,'d'*32,'a'*32,{'record':{'revision_source':'b'*32}})
            self.assertEqual(result,'c'*32)
            self.assertTrue(all(call.args[1][1]=='d'*32 for call in store.one.call_args_list))

    def test_cycle_or_missing_original_has_no_reset_control(self):
        app=SimpleNamespace(store=SimpleNamespace(one=Mock(return_value=None),gallery=SimpleNamespace(get=Mock(side_effect=ValueError('Missing')))))
        self.assertIsNone(resplit_origin(app,'d'*32,'a'*32,{'record':{'revision_source':'a'*32}}))
        self.assertIsNone(resplit_origin(app,'d'*32,'a'*32,{'record':{'revision_source':'b'*32}}))
        self.assertIsNone(resplit_origin(app,'d'*32,'a'*32,{'record':{}}))

    def test_imported_video_uses_itself(self):
        self.assertEqual(resplit_origin(None,'d'*32,'a'*32,{'imported':{'id':'a'*32}}),'a'*32)


if __name__=='__main__':unittest.main()
