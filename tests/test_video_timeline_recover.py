import copy,json,threading,unittest
from pathlib import Path
from unittest.mock import patch
import test_video_edit as fixture
from h3chat.video_edit import request as edit,describe
from h3chat.video_timeline_recover import request as recover
from h3chat.video_resume import checkpoint,save


class RecoveryTests(unittest.TestCase):
    setUp=fixture.VideoEditTests.setUp
    tearDown=fixture.VideoEditTests.tearDown
    original=fixture.VideoEditTests.original

    def old_export(self):
        chat,original,refs,outputs,params=self.original()
        ident=edit(self.app,chat,{'source':original,'assistant':False,'remount':False,
            'patches':[{'clip':2,'prompt':'Change <Picture 2> outfit','images':[2],'start':4,'end':9,'mode':'video'}]})['job_id']
        row=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,));payload=json.loads(row['payload'])
        patches=payload['settings']['_video_edit']['patches']
        folder=self.app.data/'outputs'/ident;folder.mkdir(parents=True)
        raw=folder/'scene-002/video.mp4';raw.parent.mkdir();raw.write_bytes(b'\0\0\0\x18ftypisomraw')
        item={'path':raw.relative_to(self.app.data).as_posix(),'generation':params|{'duration':5}}
        record=copy.deepcopy(checkpoint(self.app.data,original));record.pop('working_timeline',None)
        record.update(revision_source=original,revision_remount=False,revision_request=patches,revision_completed=[2],
            revision_generated={'2':item},revision_plans={'2':{'prompt':'Change <Picture 1> outfit','images':[{'index':1,'role':'reference','seconds':0}],
                'audios':[{'index':1,'role':'reuse','start':26}]}})
        save(folder,record)
        delivered=folder/'clip-002.mp4';delivered.write_bytes(b'\0\0\0\x18ftypisomdelivered')
        media={'id':'e'*32,'path':delivered.relative_to(self.app.data).as_posix(),'name':'Old clip.mp4','mime':'video/mp4',
            'generation':params|{'duration':5,'post_edit':True,'clip_only':True,'remount':False,'revision_source':original}}
        self.app.store.update_answer(row,'Old separate clip','done',[media],{'intent':'video','model':'Synthetic H3','references':refs,'video_parameters':{'duration':5,'post_edit':True,'clip_only':True}})
        self.app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(ident,))
        return chat,original,ident,refs,outputs

    def test_recovery_reuses_saved_footage_and_is_idempotent(self):
        chat,original,old,refs,outputs=self.old_export()
        original_bytes=(self.app.data/'outputs'/original/'scenes.json').read_bytes()
        old_bytes=(self.app.data/'outputs'/old/'scenes.json').read_bytes()
        job=recover(self.app,chat,{'source':old})['job_id']
        self.assertEqual(recover(self.app,chat,{'source':old})['job_id'],job)
        def splice(worker,body,*args,**kw):
            self.assertEqual(worker,'video-splice-worker.py')
            self.assertEqual(body['original'],str(self.app.data/outputs[1]))
            self.assertEqual((body['start_frame'],body['end_frame']),(96,216))
            Path(body['output']).write_bytes(b'\0\0\0\x18ftypisommerged');return {'frames':360}
        def mux(engine,clips,audio,target,*args,**kw):
            self.assertEqual(clips,[self.app.data/'outputs'/old/'scene-002/video.mp4'])
            self.assertEqual((kw['audio_start'],kw['audio_duration']),(26,5))
            target.write_bytes(b'\0\0\0\x18ftypisomrecovered');return {'duration':5}
        with patch.object(self.app.engine,'generate_video') as gpu,patch.object(self.app.engine,'refine_video') as planner,patch.object(self.app.engine,'tool_call',side_effect=splice),patch('h3chat.soundtrack.compose',side_effect=mux):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(job,)),threading.Event())
        gpu.assert_not_called();planner.assert_not_called()
        answer=self.app.store.chat(chat)['messages'][-1]
        self.assertEqual(answer['status'],'done',answer['meta']);self.assertIn('CPU',answer['meta']['execution_mode'])
        self.assertEqual(answer['media'][0]['generation']['timeline_id'],job)
        manifest=describe(self.app,chat,job);self.assertEqual(manifest['duration'],42);self.assertEqual(manifest['edited_clips'],[2])
        self.assertEqual(checkpoint(self.app.data,job)['outputs'][::2],outputs[::2])
        self.assertEqual(recover(self.app,chat,{'source':old}),{'timeline_id':job})
        self.assertEqual(recover(self.app,chat,{'source':job}),{'timeline_id':job})
        self.assertEqual((self.app.data/'outputs'/original/'scenes.json').read_bytes(),original_bytes)
        self.assertEqual((self.app.data/'outputs'/old/'scenes.json').read_bytes(),old_bytes)

    def test_recovery_requires_original_chat_and_valid_completed_recipe(self):
        chat,original,old,*_=self.old_export();other=self.app.store.create_chat()['id']
        with self.assertRaises(ValueError):recover(self.app,other,{'source':old})
        with self.assertRaises(ValueError):recover(self.app,chat,{'source':original})
        folder=self.app.data/'outputs'/old;saved=checkpoint(self.app.data,old)
        saved['revision_completed']=[];save(folder,saved)
        with self.assertRaisesRegex(ValueError,'completati'):recover(self.app,chat,{'source':old})

    def test_interrupted_recovery_retries_without_any_generation(self):
        chat,original,old,*_=self.old_export();job=recover(self.app,chat,{'source':old})['job_id']
        calls=0
        def splice(worker,body,*args,**kw):
            nonlocal calls
            calls+=1
            if calls==1:raise RuntimeError('Synthetic interrupted recovery')
            Path(body['output']).write_bytes(b'\0\0\0\x18ftypisommerged');return {'frames':360}
        def mux(engine,clips,audio,target,*args,**kw):
            target.write_bytes(b'\0\0\0\x18ftypisomrecovered');return {'duration':5}
        with patch.object(self.app.engine,'generate_video') as gpu,patch.object(self.app.engine,'refine_video') as planner,patch.object(self.app.engine,'tool_call',side_effect=splice),patch('h3chat.soundtrack.compose',side_effect=mux):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(job,)),threading.Event())
            self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'failed')
            retried=self.app.regenerate(chat)['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(retried,)),threading.Event())
        self.assertEqual(calls,2);gpu.assert_not_called();planner.assert_not_called()
        self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
        self.assertEqual(describe(self.app,chat,retried)['edited_clips'],[2])


if __name__=='__main__':unittest.main()
