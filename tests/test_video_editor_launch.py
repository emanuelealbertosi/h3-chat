import copy,json,threading,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.video_edit import describe,request
from h3chat.video_job_resume import describe as resume_info
from h3chat.video_resume import checkpoint
import test_video_edit as fixture


class EditorLaunchTests(unittest.TestCase):
    setUp=fixture.VideoEditTests.setUp
    tearDown=fixture.VideoEditTests.tearDown
    original=fixture.VideoEditTests.original

    def test_last_accepted_launch_survives_stop_and_preset_changes(self):
        chat,ident,*_=self.original();source=(self.app.data/'outputs'/ident/'scenes.json').read_bytes()
        self.assertIsNone(describe(self.app,chat,ident)['last_launch'])
        selected={'attention':'veda','attention_chunks':56,'attention_chunks_mode':'manual','megapixels':.98,
            'seed':0,'cfg':2,'shift_video':9,'veda_sparsity':80,'pdd_enabled':False}
        job=request(self.app,chat,{'source':ident,'assistant':False,'remount':False,'video_steps':16,
            'parameters':selected,'patches':[{'clip':2,'mode':'video','prompt':'Red jacket <Picture 2>',
                'images':[2],'start':2,'end':7,'reference_megapixels':.2,'lip_sync':True,'audio_guide':True}]})['job_id']
        self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(job,))
        settings=self.app.store.settings();settings['video_overrides']={self.model['id']:{'attention':'pytorch','seed':999,'megapixels':.5}};self.app.store.save_settings(settings)
        jobs=self.app.store.all('SELECT * FROM jobs')
        loaded=describe(self.app,chat,ident)['last_launch']
        self.assertEqual(loaded['job_id'],job);self.assertEqual(loaded['steps'],16);self.assertFalse(loaded['assistant'])
        for key,v in selected.items():self.assertEqual(loaded['parameters'][key],v)
        self.assertEqual(loaded['edit']['patches'][0]['reference_megapixels'],.2)
        self.assertEqual(loaded['edit']['patches'][0]['start'],2)
        self.assertEqual(loaded['pending_clips'],[2])
        other,other_id,*_=self.original();self.assertIsNone(describe(self.app,other,other_id)['last_launch'])
        self.assertEqual(self.app.store.all('SELECT * FROM jobs')[:len(jobs)],jobs)
        self.assertEqual((self.app.data/'outputs'/ident/'scenes.json').read_bytes(),source)

    def test_clip_launches_keep_independent_parameters_and_remap_reference_ids(self):
        chat,source,refs,*_=self.original()
        first=request(self.app,chat,{'source':source,'assistant':False,'parameters':{'megapixels':.7,'cfg':2,'seed':10},
            'patches':[{'clip':2,'mode':'video','prompt':'Use <Picture 2>','images':[2]}]})['job_id']
        self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(first,))
        second=request(self.app,chat,{'source':source,'assistant':False,'parameters':{'megapixels':.98,'cfg':3,'seed':20},
            'patches':[{'clip':3,'mode':'video','prompt':'Use <Picture 1>','images':[1]}]})['job_id']
        self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(second,))
        launch=describe(self.app,chat,source)['last_launch']
        self.assertEqual(launch['parameters']['cfg'],3)
        self.assertEqual(launch['clip_launches']['2']['parameters']['seed'],10)
        self.assertEqual(launch['clip_launches']['3']['parameters']['seed'],20)
        self.assertEqual([p['clip'] for p in launch['edit']['patches']],[2,3])
        self.assertEqual(launch['pending_clips'],[3])
        self.assertEqual(launch['edit']['patches'][0]['prompt'],'Use <Picture 2>')

    def test_launches_follow_multiple_resulting_timelines_without_resetting_older_clips(self):
        chat,original,refs,outputs,params=self.original()
        def generate(model,settings,plan,refs,ident,*args,**kw):
            target=self.app.data/'outputs'/ident/'video.mp4';target.parent.mkdir(parents=True)
            target.write_bytes(b'\0\0\0\x18ftypisomnew');return {'path':target.relative_to(self.app.data).as_posix(),'generation':params}
        def fit(worker,body,*args,**kw):Path(body['output']).write_bytes(b'\0\0\0\x18ftypisomfit');return {}
        def mux(engine,clips,audio,target,*args,**kw):target.write_bytes(b'\0\0\0\x18ftypisommux');return {'duration':kw['audio_duration']}
        def run(source,clip,seed):
            job=request(self.app,chat,{'source':source,'assistant':False,'remount':False,'parameters':{'seed':seed},'patches':[{'clip':clip,'mode':'video','prompt':'A red jacket','audio_guide':False}]})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(job,)),threading.Event())
            self.assertEqual(self.app.store.one('SELECT status FROM jobs WHERE id=?',(job,))['status'],'done')
            return job
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch.object(self.app.engine,'tool_call',side_effect=fit),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=mux):
            first=run(original,2,123);second=run(first,3,456)
        launch=describe(self.app,chat,second)['last_launch']
        self.assertEqual(launch['clip_launches']['2']['parameters']['seed'],123)
        self.assertEqual(launch['clip_launches']['3']['parameters']['seed'],456)
        self.assertEqual(launch['pending_clips'],[])

    def test_interrupted_working_timeline_retains_ready_clip_and_launch_recipe(self):
        chat,original,refs,outputs,params=self.original();before=(self.app.data/'outputs'/original/'scenes.json').read_bytes()
        job=request(self.app,chat,{'source':original,'assistant':False,'remount':False,'video_steps':12,
            'parameters':{'attention':'veda','megapixels':.98,'seed':123},'patches':[
                {'clip':2,'mode':'video','prompt':'Red jacket','audio_guide':False},
                {'clip':3,'mode':'video','prompt':'Blue jacket','audio_guide':False}]})['job_id']
        calls=[]
        def generate(model,settings,plan,refs,ident,*args,**kw):
            calls.append(ident)
            if len(calls)==2:raise RuntimeError('Synthetic interruption')
            target=self.app.data/'outputs'/ident/'video.mp4';target.parent.mkdir(parents=True)
            target.write_bytes(b'\0\0\0\x18ftypisomnew')
            return {'path':target.relative_to(self.app.data).as_posix(),'generation':params}
        def fit(worker,body,*args,**kw):
            Path(body['output']).write_bytes(b'\0\0\0\x18ftypisomfitted');return {}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch.object(self.app.engine,'tool_call',side_effect=fit),patch('h3chat.soundtrack.probe',return_value={'duration':60}):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(job,)),threading.Event())
        saved=checkpoint(self.app.data,job);self.assertEqual(saved['revision_completed'],[2])
        self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(job,))
        manifest=describe(self.app,chat,job);launch=manifest['last_launch']
        self.assertEqual(launch['pending_clips'],[3]);self.assertEqual(launch['completed_clips'],[2])
        selected=manifest['clips'][1]['selected_version']
        self.assertEqual(launch['edit']['versions']['2'],selected)
        self.assertNotEqual(selected,manifest['clips'][1]['versions'][0]['id'])
        self.assertTrue((self.app.data/saved['outputs'][1]).is_file())
        info=resume_info(self.app,chat,job_id=job)
        self.assertTrue(info['timeline_available']);self.assertEqual(info['ready_clips'],[2]);self.assertEqual(info['missing_clips'],[3])
        self.assertEqual((self.app.data/'outputs'/original/'scenes.json').read_bytes(),before)


if __name__=='__main__':unittest.main()
