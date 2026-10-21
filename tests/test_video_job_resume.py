import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from h3chat.store import Store, DEFAULTS
from h3chat.video_job_resume import describe, enqueue, request
from h3chat.video_resume import checkpoint, save
from h3chat.video_timeline import timeline


class VideoJobResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name).resolve()
        self.store = Store(self.data)
        self.store.resume_video = Mock(side_effect=lambda chat, job: enqueue(self.store, chat, job))
        self.app = SimpleNamespace(store=self.store, data=self.data, lock=threading.RLock(), wake=threading.Event())
        self.chat = self.store.create_chat()['id']

    def tearDown(self):self.tmp.cleanup()

    def film(self, status='interrupted', *, completed=2):
        settings = copy.deepcopy(DEFAULTS) | {'_video':True, 'video_model':'original-model',
            'video_overrides':{'original-model':{'steps':12,'seed':734,'megapixels':.5,'attention':'veda'}},
            'chat_model':'original-assistant', '_video_segment_seconds':15}
        ident = self.store.enqueue(self.chat, 'Original direction, unchanged.', [], settings, False, [])
        folder = self.data/'outputs'/ident
        outputs = []
        for n in range(completed):
            path = folder/f'scene-{n+1:03d}/video.mp4'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'\x00\x00\x00\x18ftypisom' + bytes([n])*12)
            outputs.append(path.relative_to(self.data).as_posix())
        folder.mkdir(parents=True, exist_ok=True)
        save(folder, {'timeline':timeline(42), 'prompts':['first saved shot','second saved shot','last saved shot'],
            'plan':{'prompt':'Exact saved plan','images':[],'audios':[]}, 'model':'original-model',
            'completed':completed, 'outputs':outputs, 'parameters':[{'seed':734+n,'steps':12} for n in range(completed)]})
        self.store.execute('UPDATE jobs SET status=? WHERE id=?', (status, ident))
        self.store.execute("UPDATE messages SET status=?,meta=? WHERE id=(SELECT message_id FROM jobs WHERE id=?)",
                           (status, json.dumps({'intent':'video','error':'Interrupted fixture'}), ident))
        return ident

    def payload(self, ident):return json.loads(self.store.one('SELECT payload FROM jobs WHERE id=?', (ident,))['payload'])

    def test_all_interrupted_statuses_resume_exact_job_preserving_original_settings_and_files(self):
        for status in ('failed','cancelled','interrupted'):
            with self.subTest(status=status):
                ident = self.film(status)
                original = self.payload(ident)
                saved = checkpoint(self.data,ident)
                files = {p:(self.data/p).read_bytes() for p in saved['outputs']}
                self.store.save_settings({'chat_model':'changed-assistant','video_model':'changed-model','seed':999})
                summary = describe(self.app,self.chat,job_id=ident)
                self.assertEqual((summary['completed'],summary['remaining'],summary['missing_clips']),(2,1,[3]))
                result = request(self.app,self.chat,{'job_id':ident})
                replay = self.payload(result['job_id'])
                for key in ('prompt','media','until','canvas','loras','project_id','canvas_snapshot'):
                    self.assertEqual(replay[key], original[key])
                expected = original['settings'] | {'_video_resume':ident,'_video_resume_origin':ident}
                self.assertEqual(replay['settings'],expected)
                self.assertEqual({p:(self.data/p).read_bytes() for p in saved['outputs']},files)
                self.assertTrue(self.app.wake.is_set())
                self.store.execute("UPDATE jobs SET status='done' WHERE id=?",(result['job_id'],))

    def test_message_selection_finds_its_exact_latest_attempt_not_last_chat_request(self):
        ident = self.film()
        message = self.store.one('SELECT message_id FROM jobs WHERE id=?',(ident,))['message_id']
        unrelated = self.store.enqueue(self.chat,'A newer unrelated request',[],DEFAULTS)
        self.store.execute("UPDATE jobs SET status='done' WHERE id=?",(unrelated,))
        self.assertEqual(describe(self.app,self.chat,message_id=message)['job_id'],ident)
        result = request(self.app,self.chat,{'job_id':ident})
        self.assertEqual(self.store.one('SELECT message_id FROM jobs WHERE id=?',(result['job_id'],))['message_id'],message)
        self.assertEqual(self.payload(result['job_id'])['prompt'],'Original direction, unchanged.')

    def test_completed_clip_regeneration_does_not_overwrite_interrupted_recipe_or_checkpoint(self):
        ident=self.film('cancelled');original=self.payload(ident);path=self.data/'outputs'/ident/'scenes.json';saved=path.read_bytes()
        old_message=self.store.one('SELECT message_id FROM jobs WHERE id=?',(ident,))['message_id']
        changed=copy.deepcopy(original['settings']);changed['_video_edit']={'source':ident,'patches':[{'clip':1,'prompt':'New version'}]};changed['video_overrides']['original-model']['steps']=20
        revision=self.store.enqueue(self.chat,'Regenerate completed clip 1',[],changed,False,[])
        self.store.execute("UPDATE jobs SET status='done' WHERE id=?",(revision,))
        revision_message=self.store.one('SELECT message_id FROM jobs WHERE id=?',(revision,))['message_id']
        self.assertNotEqual(old_message,revision_message)
        self.assertEqual(describe(self.app,self.chat,message_id=old_message)['missing_clips'],[3])
        resumed=request(self.app,self.chat,{'job_id':ident})['job_id'];payload=self.payload(resumed)
        self.assertEqual(payload['settings'],original['settings']|{'_video_resume':ident,'_video_resume_origin':ident})
        self.assertNotIn('_video_edit',payload['settings']);self.assertEqual(self.payload(ident),original);self.assertEqual(path.read_bytes(),saved)

    def test_repeated_requests_do_not_queue_again_even_after_recovery_cancelled(self):
        ident = self.film()
        first = request(self.app,self.chat,{'job_id':ident})
        second = request(self.app,self.chat,{'job_id':ident})
        self.assertEqual(first,second)
        self.assertEqual(self.store.resume_video.call_count,1)
        self.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(first['job_id'],))
        third = request(self.app,self.chat,{'job_id':ident})
        self.assertEqual(third['job_id'],first['job_id'])
        self.assertEqual(third['status'],'cancelled')
        self.assertEqual(self.store.resume_video.call_count,1)
        self.assertEqual(len(self.store.all('SELECT id FROM jobs')),2)

    def test_explicit_retry_of_failed_recovery_can_use_owned_predecessor_checkpoint(self):
        ident = self.film()
        first = request(self.app,self.chat,{'job_id':ident})['job_id']
        self.store.execute("UPDATE jobs SET status='failed' WHERE id=?",(first,))
        summary = describe(self.app,self.chat,job_id=first)
        self.assertEqual(summary['checkpoint_job_id'],ident)
        second = request(self.app,self.chat,{'job_id':first})['job_id']
        self.assertNotEqual(first,second)
        self.assertEqual(self.payload(second)['settings']['_video_resume'],ident)
        self.assertEqual(self.payload(second)['settings']['_video_resume_origin'],first)

    def test_all_generated_clips_with_failed_mux_need_only_assembly(self):
        ident = self.film(completed=3)
        summary = describe(self.app,self.chat,job_id=ident)
        self.assertEqual(summary['missing_clips'],[])
        self.assertTrue(summary['assembly_only'])
        self.assertEqual(summary['completed'],3)

    def test_revision_counts_only_requested_edits_not_reused_original_clips(self):
        ident = self.film(completed=3)
        payload = self.payload(ident)
        edits = {'source':'c'*32,'patches':[{'clip':1,'prompt':'Change outfit','images':[]},{'clip':3,'prompt':'Change outfit','images':[]}], 'remount':False}
        payload['settings']['_video_edit'] = edits
        self.store.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(payload),ident))
        record = checkpoint(self.data,ident)
        record.update(revision_source=edits['source'],revision_request=edits['patches'],working_timeline=True,
            revision_completed=[1],revision_remount=False,revision_plans={'1':{'prompt':'saved'}},
            revision_generated={'1':{'path':record['outputs'][0]}})
        save(self.data/'outputs'/ident,record)
        summary = describe(self.app,self.chat,job_id=ident)
        self.assertEqual((summary['total'],summary['completed'],summary['remaining'],summary['missing_clips']),(2,1,1,[3]))

    def test_ownership_archived_busy_and_live_job_checks(self):
        ident = self.film()
        other = self.store.create_chat()['id']
        for method in (lambda:describe(self.app,other,job_id=ident),lambda:request(self.app,other,{'job_id':ident})):
            with self.assertRaisesRegex(ValueError,'tua area'):method()
        self.store.execute('UPDATE chats SET archived=1 WHERE id=?',(self.chat,))
        with self.assertRaisesRegex(ValueError,'archivio'):request(self.app,self.chat,{'job_id':ident})
        self.store.execute('UPDATE chats SET archived=0 WHERE id=?',(self.chat,))
        busy = self.store.enqueue(other,'Active request',[],DEFAULTS)
        with self.assertRaisesRegex(ValueError,'attiva o in coda'):request(self.app,self.chat,{'job_id':ident})
        self.store.execute("UPDATE jobs SET status='done' WHERE id=?",(busy,))
        self.store.execute("UPDATE jobs SET status='running' WHERE id=?",(ident,))
        with self.assertRaisesRegex(ValueError,'soltanto'):describe(self.app,self.chat,job_id=ident)

    def test_invalid_or_missing_checkpoint_never_triggers_full_generation(self):
        ident = self.film()
        record = checkpoint(self.data,ident)
        (self.data/record['outputs'][1]).unlink()
        with self.assertRaises((OSError,ValueError)):request(self.app,self.chat,{'job_id':ident})
        self.assertEqual(len(self.store.all('SELECT id FROM jobs')),1)
        self.assertFalse(self.app.wake.is_set())
        for body in ({'job_id':'../private'},{'job_id':ident,'settings':{}},{}):
            with self.assertRaises(ValueError):request(self.app,self.chat,body)

    def test_non_resumable_handlers_are_rejected_without_repeating_model_work(self):
        ident = self.film()
        original = self.payload(ident)
        for key in ('_video_extend','_video_clip','_upscale','_video_assemble','_video_remix'):
            with self.subTest(key=key):
                payload = copy.deepcopy(original)
                payload['settings'][key] = {'source':'c'*32}
                self.store.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(payload),ident))
                with self.assertRaisesRegex(ValueError,'riprendibile'):request(self.app,self.chat,{'job_id':ident})
        self.assertEqual(len(self.store.all('SELECT id FROM jobs')),1)


if __name__=='__main__':unittest.main()
