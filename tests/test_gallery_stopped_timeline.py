import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.store import Store,DEFAULTS
from h3chat.gallery import Gallery
from h3chat.gallery_timelines import MIME,touch


class StoppedTimelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.store=Store(self.root);self.gallery=self.store.gallery
        self.chat=self.store.create_chat('Londonpaid')['id']

    def file(self,path):
        target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(b'\0\0\0\x18ftypisomsynthetic');os.utime(target,(100,100));return target

    def stopped(self,finished=10000):
        original='uploads/original.mp4';self.file(original)
        ident=self.store.enqueue(self.chat,'Replace character',[],DEFAULTS)
        folder=self.root/'outputs'/ident;folder.mkdir(parents=True)
        generated={str(i):{'path':f'outputs/{ident}/scene-{i:03d}.mp4'} for i in range(1,21)}
        for item in generated.values():self.file(item['path'])
        saved={'timeline':[{'start':i*10,'duration':10,'frames':240} for i in range(64)],
            'prompts':['Preserve movements']*64,'parameters':[{} for _ in range(64)],'completed':64,
            'outputs':[generated[str(i)]['path'] if i<=20 else original for i in range(1,65)],
            'clip_sources':[None if i<=20 else {'path':original,'start':(i-1)*10} for i in range(1,65)],
            'plan':{'audios':[{'index':1,'role':'reuse'}]},'working_timeline':True,
            'revision_remount':False,'revision_request':[{'clip':i} for i in range(1,65)],
            'revision_completed':list(range(1,21)),'revision_generated':generated}
        target=folder/'scenes.json';target.write_text(json.dumps(saved));os.utime(target,(5000,5000))
        self.store.execute("UPDATE jobs SET created=50,status='cancelled' WHERE id=?",(ident,))
        self.store.execute("UPDATE messages SET status='cancelled',meta=? WHERE id=(SELECT message_id FROM jobs WHERE id=?)",
            (json.dumps({'intent':'video','timing':{'job_id':ident,'finished_at':finished}}),ident))
        return ident,target,saved

    def test_stopped_64_clip_timeline_appears_first_without_final_mp4(self):
        self.file('uploads/later-upload.mp4')
        self.gallery.register([{'id':'b'*32,'path':'uploads/later-upload.mp4','mime':'video/mp4'}],created=6000)
        ident,target,_=self.stopped();before=target.read_bytes()
        listing=self.gallery.listing(kind='video',sort='modified_desc');item=listing['items'][0]
        self.assertEqual(item['id'],ident);self.assertTrue(item['timeline_only']);self.assertEqual(item['video_kind'],'timeline')
        self.assertEqual((item['clip_count'],item['completed_clips'],item['requested_clips']),(64,20,64))
        self.assertEqual(item['modified'],10000);self.assertEqual(item['timeline_status'],'cancelled')
        self.assertEqual(item['chat_id'],self.chat);self.assertIsNone(item['url'])
        self.assertFalse((target.parent/'video.mp4').exists());self.assertEqual(target.read_bytes(),before)
        self.assertEqual(self.gallery.listing(kind='other')['total'],0)
        self.assertTrue(self.gallery.get(ident)['timeline_only'])

    def test_legacy_stops_are_backfilled_once_and_clean_listing_does_not_read_checkpoints(self):
        ident,_,_=self.stopped();self.store.execute("DELETE FROM gallery_pending WHERE source='job'")
        self.store.execute("DELETE FROM gallery_sync WHERE key='timelines-v1'")
        gallery=Gallery(self.store);self.assertEqual(gallery.listing()['items'][0]['id'],ident)
        with patch('h3chat.gallery_timelines.checkpoint',side_effect=AssertionError('Must not rescan saved jobs')):
            self.assertEqual(gallery.listing(sort='name_asc')['total'],1)

    def test_delayed_finish_timing_refreshes_order_but_unrelated_retry_does_not(self):
        ident,_,_=self.stopped(finished=6000);self.assertEqual(self.gallery.listing()['items'][0]['modified'],6000)
        self.store.execute("UPDATE messages SET meta=? WHERE id=(SELECT message_id FROM jobs WHERE id=?)",
            (json.dumps({'timing':{'job_id':ident,'finished_at':12000}}),ident))
        self.assertEqual(self.gallery.listing()['items'][0]['modified'],12000)
        self.store.execute("UPDATE messages SET meta=? WHERE id=(SELECT message_id FROM jobs WHERE id=?)",
            (json.dumps({'timing':{'job_id':'f'*32,'finished_at':50000}}),ident))
        self.assertEqual(self.gallery.listing()['items'][0]['modified'],12000)

    def test_hide_rename_and_draft_touch_preserve_files_and_do_not_resurrect(self):
        ident,target,_=self.stopped();self.gallery.listing()
        self.gallery.rename(ident,'Il mio montaggio');touch(self.gallery,ident,50000)
        item=self.gallery.listing()['items'][0];self.assertEqual(item['name'],'Il mio montaggio');self.assertGreaterEqual(item['modified'],50000)
        self.gallery.remove(ident);self.store.execute("UPDATE jobs SET status='interrupted' WHERE id=?",(ident,))
        self.assertEqual(self.gallery.listing()['total'],0);self.assertTrue(target.is_file())
        self.store.execute('DELETE FROM chats WHERE id=?',(self.chat,));self.assertEqual(self.gallery.listing()['total'],0)

    def test_normal_export_replaces_placeholder_without_duplicate_or_broken_movie(self):
        ident,target,_=self.stopped();self.gallery.listing();self.file(f'outputs/{ident}/video.mp4')
        self.store.execute("UPDATE jobs SET status='done' WHERE id=?",(ident,))
        self.gallery.register([{'id':ident,'path':f'outputs/{ident}/video.mp4','mime':'video/mp4'}])
        result=self.gallery.listing();self.assertEqual(result['total'],1)
        self.assertFalse(result['items'][0]['timeline_only']);self.assertEqual(result['items'][0]['path'],f'outputs/{ident}/video.mp4')
        self.assertNotEqual(self.gallery.get(ident)['mime'],MIME);self.assertTrue(target.is_file())

    def test_missing_or_non_working_checkpoint_does_not_create_a_fake_movie(self):
        ident,target,saved=self.stopped();saved['working_timeline']=False;target.write_text(json.dumps(saved))
        self.assertEqual(self.gallery.listing()['total'],0)


if __name__=='__main__':unittest.main()
