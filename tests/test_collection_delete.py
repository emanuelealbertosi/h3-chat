"""Explicit lot deletion: snapshots, active-use protection, shared files and tombstones."""
import json
import unittest
from unittest.mock import patch
import test_image_collections as fixture
from h3chat import collection_delete as remove
from h3chat import image_collections as lots

class CollectionDeleteTests(unittest.TestCase):
    setUp=fixture.CollectionTests.setUp
    tearDown=fixture.CollectionTests.tearDown
    image=fixture.CollectionTests.image
    lot=fixture.CollectionTests.lot

    def test_multiple_lots_hidden_while_original_files_remain(self):
        first=self.lot();second=self.lot();files=[self.app.data/i['media']['path'] for lot in (first,second) for i in lot['images']]
        ids=[first['id'],second['id']];plan=remove.plan(self.app,{'ids':ids});self.assertEqual(plan['count'],2)
        result=remove.remove(self.app,{'ids':ids,'delete_files':False,'confirmed':True,'snapshot':plan['snapshot']})
        self.assertEqual(set(result['removed']),set(ids));self.assertTrue(all(p.is_file() for p in files));self.assertEqual(lots.listing(self.app)['items'],[])
        self.assertEqual(remove.hidden_ids(self.app),set(ids))

    def test_disk_delete_requires_confirmation_and_fresh_snapshot(self):
        lot=self.lot();plan=remove.plan(self.app,{'ids':[lot['id']]});body={'ids':[lot['id']],'delete_files':True,'snapshot':plan['snapshot']}
        with self.assertRaisesRegex(ValueError,'Conferma'):remove.remove(self.app,body)
        path=self.app.data/lot['images'][0]['media']['path'];path.write_bytes(path.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'cambiati'):remove.remove(self.app,body|{'confirmed':True})
        self.assertTrue(path.exists());self.assertEqual(len(lots.listing(self.app)['items']),1)

    def test_files_are_deleted_once_shared_references_reported_and_unrelated_kept(self):
        first=self.lot();shared=first['images'][0]['media'];second=lots.create(self.app,{'name':'Altro lotto','images':[{'id':shared['id']}]})
        untouched=self.image('nonselezionata');plan=remove.plan(self.app,{'ids':[first['id']]})
        self.assertGreater(plan['referenced_files'],0);self.assertIn('Altro lotto: Altro lotto',str(plan['files']))
        result=remove.remove(self.app,{'ids':[first['id']],'delete_files':True,'confirmed':True,'snapshot':plan['snapshot']})
        self.assertEqual(result['files_deleted'],2);self.assertEqual(result['removed'],[first['id']]);self.assertTrue((self.app.data/untouched['path']).is_file())
        self.assertFalse((self.app.data/shared['path']).exists())

    def test_running_jobs_block_disk_deletion_and_selected_lot_use_blocks_hiding(self):
        lot=self.lot();chat=self.app.store.create_chat()['id'];ticket=self.app.store.enqueue(chat,'Job',[],self.app.store.settings())
        plan=remove.plan(self.app,{'ids':[lot['id']]});self.assertFalse(plan['can_delete_files']);self.assertTrue(plan['can_remove'])
        with self.assertRaises(ValueError):remove.remove(self.app,{'ids':[lot['id']],'delete_files':True,'confirmed':True,'snapshot':plan['snapshot']})
        row=self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ticket,));payload=json.loads(row['payload']);payload['selected_lot']=lot['id']
        self.app.store.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(payload),ticket))
        self.assertFalse(remove.plan(self.app,{'ids':[lot['id']]})['can_remove'])

    def test_background_tombstone_prevents_rediscovery(self):
        from h3chat.slide_backgrounds import save,listing
        lot=self.lot();lot['kind']='backgrounds';save(self.app,lot)
        plan=remove.plan(self.app,{'ids':[lot['id']]});remove.remove(self.app,{'ids':[lot['id']],'delete_files':False,'confirmed':True,'snapshot':plan['snapshot']})
        # Even if a historical manifest returns, deletion remains authoritative.
        save(self.app,lot);self.assertEqual(listing(self.app)['items'],[]);self.assertEqual(lots.listing(self.app)['items'],[])

    def test_foreign_ids_and_duplicate_selection_rejected(self):
        for ids in (['f'*32],['a'*32,'a'*32],['../evil']):
            with self.assertRaises(ValueError):remove.plan(self.app,{'ids':ids})

    def test_failed_file_deletion_keeps_lot_visible_for_retry(self):
        from pathlib import Path
        lot=self.lot();blocked=self.app.data/lot['images'][0]['media']['path'];original=Path.unlink
        def unlink(path,*args,**kwargs):
            if path==blocked:raise PermissionError('Fixture file locked')
            return original(path,*args,**kwargs)
        plan=remove.plan(self.app,{'ids':[lot['id']]})
        with patch.object(Path,'unlink',unlink):result=remove.remove(self.app,{'ids':[lot['id']],'delete_files':True,'confirmed':True,'snapshot':plan['snapshot']})
        self.assertEqual(result['removed'],[]);self.assertEqual(result['files_deleted'],1);self.assertEqual(len(result['errors']),1)
        self.assertTrue(blocked.is_file());self.assertEqual(lots.get(self.app,lot['id'])['available'],1)

if __name__=='__main__':unittest.main()
