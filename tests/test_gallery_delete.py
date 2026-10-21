import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.store import Store
from h3chat.gallery_delete import plan,remove
from h3chat.gallery_timelines import MIME
from h3chat.workspaces import guest_allowed


class GalleryDeleteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=Store(self.root);self.gallery=self.store.gallery
        self.items=[]
        for n in range(3):
            path=f'uploads/{n}/asset.png';file=self.root/path;file.parent.mkdir(parents=True);file.write_bytes(b'fixture')
            item={'id':f'{n+1:032x}','path':path,'name':f'Asset {n}','mime':'image/png'};self.items.append(item)
        self.gallery.register(self.items,'uploaded')
    def tearDown(self):self.temp.cleanup()
    def body(self,ids=None):return {'ids':ids or [i['id'] for i in self.items[:2]]}
    def test_hide_multiple_preserves_files_and_stays_hidden_on_register(self):
        value=remove(self.gallery,self.body());self.assertEqual(len(value['removed']),2);self.assertTrue(value['files_preserved'])
        self.gallery.register(self.items,'uploaded')
        self.assertEqual(self.gallery.listing()['total'],1)
        self.assertTrue(all((self.root/i['path']).is_file() for i in self.items))
    def test_delete_needs_confirmation_and_snapshot_then_only_removes_selected_files(self):
        body=self.body();preview=plan(self.gallery,body)
        for extra in ({'delete_files':True},{'delete_files':True,'confirmed':True,'snapshot':'stale'}):
            with self.assertRaises(ValueError):remove(self.gallery,body|extra)
        result=remove(self.gallery,body|{'delete_files':True,'confirmed':True,'snapshot':preview['snapshot']})
        self.assertEqual(result['files_deleted'],2);self.assertTrue((self.root/self.items[2]['path']).exists())
        self.assertFalse((self.root/self.items[0]['path']).exists());self.assertTrue((self.root/'uploads/0').is_dir())
    def test_active_inputs_are_blocked_but_can_be_hidden(self):
        chat=self.store.create_chat()['id'];self.store.enqueue(chat,'fixture',[self.items[0]],{})
        body=self.body([self.items[0]['id']]);preview=plan(self.gallery,body)
        self.assertFalse(preview['can_delete_files']);self.assertIn('generazione',preview['items'][0]['reason'])
        with self.assertRaises(ValueError):remove(self.gallery,body|{'delete_files':True,'confirmed':True,'snapshot':preview['snapshot']})
        self.assertTrue(remove(self.gallery,body)['files_preserved'])
    def test_output_from_active_job_protected_without_payload_reference(self):
        chat=self.store.create_chat()['id'];job=self.store.enqueue(chat,'fixture',[],{})
        path=self.root/'outputs'/job/'clip.mp4';path.parent.mkdir(parents=True);path.write_bytes(b'clip')
        self.gallery.register([{'id':'e'*32,'path':path.relative_to(self.root).as_posix(),'name':'working','mime':'video/mp4'}])
        self.assertFalse(plan(self.gallery,self.body(['e'*32]))['can_delete_files'])
    def test_saved_timeline_is_hidden_without_destroying_scene_metadata(self):
        self.store.execute('UPDATE gallery SET mime=? WHERE id=?',(MIME,self.items[0]['id']))
        body=self.body([self.items[0]['id']]);self.assertFalse(plan(self.gallery,body)['can_delete_files'])
        remove(self.gallery,body);self.assertTrue((self.root/self.items[0]['path']).is_file())
    def test_foreign_id_invalid_types_and_private_paths_fail_before_mutation(self):
        for body in ({'ids':[]},{'ids':['../private']},{'ids':[self.items[0]['id']]*2},{'ids':[self.items[0]['id'],'f'*32]}):
            with self.assertRaises(ValueError):remove(self.gallery,body)
        self.store.execute('UPDATE gallery SET path=? WHERE id=?',('chat.sqlite',self.items[0]['id']))
        with self.assertRaises(ValueError):plan(self.gallery,self.body())
        self.assertEqual(self.store.all('SELECT * FROM gallery_hidden'),[])
    def test_changed_file_requires_a_new_review(self):
        body=self.body();preview=plan(self.gallery,body);(self.root/self.items[0]['path']).write_bytes(b'new content')
        with self.assertRaisesRegex(ValueError,'cambiati'):remove(self.gallery,body|{'delete_files':True,'confirmed':True,'snapshot':preview['snapshot']})
    def test_permission_error_keeps_that_asset_visible_and_reports_partial_result(self):
        body=self.body();preview=plan(self.gallery,body);original=Path.unlink
        def unlink(file,*args,**kwargs):
            if file==self.root/self.items[0]['path']:raise PermissionError()
            return original(file,*args,**kwargs)
        with patch.object(Path,'unlink',unlink):result=remove(self.gallery,body|{'delete_files':True,'confirmed':True,'snapshot':preview['snapshot']})
        self.assertEqual(result['files_deleted'],1);self.assertEqual(len(result['errors']),1)
        self.assertEqual(self.gallery.listing()['total'],2)
    def test_routes_stay_workspace_scoped(self):
        for name in ('delete-plan','delete'):self.assertTrue(guest_allowed('/api/gallery/'+name,'POST'))
        self.assertFalse(guest_allowed('/api/gallery/delete/private','POST'))


if __name__=='__main__':unittest.main()
