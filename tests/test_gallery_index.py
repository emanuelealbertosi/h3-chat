import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.gallery import Gallery
from h3chat.store import Store


class GalleryIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.store=Store(self.root);self.gallery=self.store.gallery
        self.chat=self.store.create_chat()['id']

    def media(self,n,path=None,mime='video/mp4',stamp=100):
        path=path or f'uploads/{n}.mp4';target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(b'fixture');os.utime(target,(stamp,stamp))
        return {'id':f'{n:032x}','name':f'File {n:03}','mime':mime,'path':path}

    def message(self,items,meta=None):
        self.store.execute("INSERT INTO messages(id,chat_id,role,created,media,meta) VALUES ('message',?,'assistant',50,?,?)",
            (self.chat,json.dumps(items),json.dumps(meta or {})))

    def test_clean_searches_do_not_read_history_register_files_or_query_jobs_per_item(self):
        items=[self.media(i) for i in range(1,56)];self.message(items,{'large_plan':'x'*1000000})
        self.assertEqual(self.gallery.listing()['total'],55)
        with patch.object(self.store,'all',wraps=self.store.all) as queries,patch.object(self.gallery,'register',wraps=self.gallery.register) as register:
            self.gallery.listing(query='File',sort='name_asc');self.gallery.listing(offset=48,sort='name_asc')
        register.assert_not_called()
        sql=[c.args[0].lower() for c in queries.call_args_list]
        self.assertFalse(any('from messages' in q or 'from canvas_artifacts' in q or 'from project_sources' in q for q in sql))
        self.assertFalse(any('select chat_id from jobs' in q for q in sql))
        # Includes one small project-menu query per listing, never history.
        self.assertLessEqual(len(sql),10)

    def test_project_filter_follows_chat_moves_and_internal_frames_stay_addressable(self):
        first='a'*32;second='b'*32
        for ident in (first,second):self.store.execute('INSERT INTO projects(id,name,created) VALUES (?,?,0)',(ident,ident))
        self.store.execute('UPDATE chats SET project_id=? WHERE id=?',(first,self.chat))
        image=self.media(1,mime='image/png');frame=self.media(2,'outputs/video-imports/source/layout-v2/frame-001.png','image/png')
        self.message([image,frame]);self.assertEqual(self.gallery.listing(project_id=first)['total'],1)
        self.assertEqual(self.gallery.get(frame['id'])['path'],frame['path'])
        self.store.execute('UPDATE chats SET project_id=? WHERE id=?',(second,self.chat))
        self.assertEqual(self.gallery.listing(project_id=first)['total'],0)
        self.assertEqual(self.gallery.listing(project_id=second)['items'][0]['id'],image['id'])

    def test_later_message_and_canvas_edits_and_restart_are_indexed(self):
        first=self.media(1);second=self.media(2);third=self.media(3)
        self.message([first]);self.gallery.listing();self.gallery.rename(first['id'],'Nome personale')
        self.store.execute("UPDATE messages SET media=?,meta=? WHERE id='message'",
            (json.dumps([first,second]),json.dumps({'slide_generated_images':[third]})))
        self.assertEqual(self.gallery.listing()['total'],3)
        self.assertEqual(self.gallery.get(first['id'])['name'],'Nome personale')
        fourth=self.media(4)
        canvas=self.store.canvas_history.save(self.chat,{'media':[fourth]})
        self.assertEqual(self.gallery.listing()['total'],4)
        fifth=self.media(5)
        self.store.execute('UPDATE canvas_artifacts SET media=? WHERE id=?',(json.dumps([fourth,fifth]),canvas['id']))
        # A restart must not discard durable changes or start another full backfill.
        self.gallery=Gallery(self.store)
        self.assertEqual(self.gallery.listing()['total'],5)
        self.assertEqual(self.store.one('SELECT count(*) n FROM gallery_pending')['n'],0)

    def test_reconcile_does_not_drop_an_update_arriving_during_registration(self):
        first,second=self.media(1),self.media(2);self.message([first])
        real=self.gallery.register;changed=False
        def register(*args,**kwargs):
            nonlocal changed
            real(*args,**kwargs)
            if not changed:
                changed=True;self.store.execute("UPDATE messages SET media=? WHERE id='message'",(json.dumps([second]),))
        with patch.object(self.gallery,'register',side_effect=register):self.gallery.reconcile()
        self.assertEqual(self.store.one('SELECT count(*) n FROM gallery_pending')['n'],1)
        self.assertEqual(self.gallery.listing()['total'],2)

    def test_legacy_registered_files_without_history_get_details_once(self):
        item=self.media(1)
        self.store.execute('INSERT INTO gallery VALUES (?,?,?,?,?,?)',(item['id'],item['path'],'Legacy',item['mime'],'uploaded',40))
        self.store.execute("DELETE FROM gallery_sync WHERE key='incremental-v1'")
        gallery=Gallery(self.store)
        self.assertEqual(gallery.listing()['items'][0]['modified'],100)
        with patch.object(gallery,'register') as register:gallery.listing()
        register.assert_not_called()

    def test_sorting_is_global_before_pagination_and_filters(self):
        for i in range(1,56):self.gallery.register([self.media(i,stamp=1000-i)],'uploaded',i)
        newest=self.gallery.listing(sort='modified_desc');self.assertEqual(newest['items'][0]['id'],f'{1:032x}')
        rest=self.gallery.listing(sort='modified_desc',offset=newest['offset'])
        self.assertEqual([i['id'] for i in newest['items']+rest['items']],[f'{i:032x}' for i in range(1,56)])
        self.assertEqual(self.gallery.listing(sort='added_desc')['items'][0]['id'],f'{55:032x}')
        self.assertEqual(self.gallery.listing(sort='added_asc')['items'][0]['id'],f'{1:032x}')
        self.assertEqual(self.gallery.listing(sort='name_desc')['items'][0]['id'],f'{55:032x}')
        self.assertEqual(self.gallery.listing(sort='modified_asc')['items'][0]['id'],f'{55:032x}')
        self.gallery.rename(f'{55:032x}','Rinominato')
        self.assertEqual(self.gallery.listing(sort='modified_desc')['items'][0]['id'],f'{55:032x}')
        self.assertEqual(self.gallery.listing(query='Rinominato',origin='uploaded',sort='name_asc')['total'],1)
        audio=self.media(80,mime='audio/wav');self.gallery.register([audio])
        self.assertEqual(self.gallery.listing(sort='type_asc')['items'][0]['mime'],'audio/wav')
        self.assertEqual(self.gallery.listing(sort='type_desc')['items'][0]['mime'],'video/mp4')
        for invalid in ('modified; DROP TABLE gallery',[],None):
            with self.assertRaises(ValueError):self.gallery.listing(sort=invalid)

    def test_timeline_clip_and_plain_movie_have_distinct_labels_and_checkpoint_date(self):
        ident='a'*32;folder=self.root/'outputs'/ident;folder.mkdir(parents=True)
        scenes=folder/'scenes.json';scenes.write_text(json.dumps({'timeline':[{},{}],'completed':2,'working_timeline':True}))
        os.utime(scenes,(500,500))
        movie=self.media(1,f'outputs/{ident}/video.mp4')
        clip=self.media(2,f'outputs/{ident}/clip-001.mp4');plain=self.media(3)
        self.gallery.register([movie,clip,plain],created=50)
        found={r['id']:r for r in self.gallery.listing()['items']}
        full,part,source=(found[i['id']] for i in (movie,clip,plain))
        self.assertEqual((full['video_kind'],full['clip_count'],full['modified']),('timeline',2,500))
        self.assertEqual((part['video_kind'],part['timeline_id']),('clip',ident))
        self.assertEqual(source['video_kind'],'')
        scenes.write_text(json.dumps({'timeline':[{}, {}, {}],'completed':3}));os.utime(scenes,(600,600))
        self.gallery.register([movie]);updated=self.gallery.listing()['items'][0]
        self.assertEqual((updated['clip_count'],updated['modified']),(3,600))

    def test_only_project_imports_inside_workspace_are_exposed(self):
        project='a'*32
        self.store.execute('INSERT INTO projects VALUES (?,?,?,0,0)',(project,'Progetto',''))
        inside=self.media(1,'project-imports/book.pdf',mime='application/pdf')
        outside=self.media(2,'uploads/not-a-project-import.pdf',mime='application/pdf')
        for item in (inside,outside):
            self.store.execute('INSERT INTO project_sources(id,project_id,path,name) VALUES (?,?,?,?)',
                (item['id'],project,str(self.root/item['path']),item['name']))
        self.assertEqual(self.gallery.listing()['total'],1)
        self.assertEqual(self.gallery.listing()['items'][0]['id'],inside['id'])


if __name__=='__main__':unittest.main()
