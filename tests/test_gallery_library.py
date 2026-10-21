import tempfile
import unittest
from pathlib import Path
from h3chat.store import Store
from h3chat.workspaces import guest_allowed


class LibraryTests(unittest.TestCase):
    def test_internal_reference_keeps_ownership_without_appearing_as_user_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);path=Path(tmp)/'outputs/job/guide.png';path.parent.mkdir(parents=True);path.write_bytes(b'image')
            item={'id':'a'*32,'path':'outputs/job/guide.png','name':'Guida.png','mime':'image/png'}
            store.gallery.register([item],internal=True);store.gallery.register([item])
            self.assertEqual(store.gallery.listing(kind='image')['total'],0)
            self.assertEqual(store.gallery.get(item['id'])['path'],item['path'])
    def test_rename_and_removal_keep_chat_and_job_inputs_and_do_not_resurrect(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);path=Path(tmp)/'uploads/video.mov';path.parent.mkdir(exist_ok=True);path.write_bytes(b'video')
            item={'id':'a'*32,'path':'uploads/video.mov','name':'video.mov','mime':'video/quicktime'}
            store.gallery.register([item],'uploaded');store.gallery.rename(item['id'],'Il mio video.mov')
            store.gallery.reconcile();self.assertEqual(store.gallery.listing()['items'][0]['name'],'Il mio video.mov')
            store.gallery.remove(item['id']);store.gallery.register([item],'uploaded')
            self.assertEqual(store.gallery.listing()['total'],0);self.assertTrue(path.is_file())
            self.assertEqual(store.gallery.get(item['id'])['path'],item['path'])
            for name in ('','   ','x'*151,'hello\nworld'):
                with self.assertRaises(ValueError):store.gallery.rename(item['id'],name)
            with self.assertRaises(ValueError):store.gallery.remove('b'*32)

    def test_guest_can_manage_only_workspace_gallery_routes(self):
        self.assertTrue(guest_allowed('/api/gallery/'+'a'*32,'PATCH'))
        self.assertTrue(guest_allowed('/api/gallery/'+'a'*32,'DELETE'))
        self.assertTrue(guest_allowed('/api/gallery/'+'a'*32+'/preview','POST'))
        self.assertFalse(guest_allowed('/api/gallery/../../private','DELETE'))


if __name__=='__main__':unittest.main()
