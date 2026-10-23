import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.video_edit_memory import describe,source_indices,restore
from h3chat.video_edit import request,validate_edits
from h3chat.video_resume import checkpoint,save
import test_video_edit as fixtures


class MemorySelectionTests(unittest.TestCase):
    def test_only_previous_frames_since_last_cut_are_used(self):
        record={'timeline':[{'continuity':c} for c in ('cut','continue','continue','cut','continue','continue')]}
        self.assertEqual(source_indices(record,5),(3,[3,4]))
        self.assertEqual(source_indices(record,4),(3,[3]))
        self.assertFalse(describe(record,0)['available'])
        self.assertFalse(describe(record,3)['default'])
        self.assertTrue(describe(record,4)['default'])
        with self.assertRaises(ValueError):source_indices(record,0)

    def test_selected_paths_are_validated_and_future_outputs_excluded(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('one.mp4','selected-two.mp4','future.mp4'):(root/name).write_bytes(b'\0\0\0\x18ftypisom')
            record={'timeline':[{'continuity':'cut'},{'continuity':'continue'},{'continuity':'continue'}],
                    'outputs':['one.mp4','selected-two.mp4','future.mp4'],'clip_sources':[None]*3}
            memory,info=restore(root,record,2)
            self.assertEqual(memory,{'opening':str(root/'one.mp4'),'recent':[str(root/'one.mp4'),str(root/'selected-two.mp4')]})
            self.assertEqual(info,{'opening_clip':1,'recent_clips':[1,2]})
            self.assertNotIn('future',str(memory))
            record['clip_sources'][1]={'path':'a.mp4','start':4}
            with self.assertRaisesRegex(ValueError,'preparato'):restore(root,record,2)
            record['clip_sources'][1]=None;record['outputs'][1]='../unowned.mp4'
            with self.assertRaises((ValueError,PermissionError)):restore(root,record,2)


class EditMemoryTests(unittest.TestCase):
    setUp=fixtures.VideoEditTests.setUp
    tearDown=fixtures.VideoEditTests.tearDown
    original=fixtures.VideoEditTests.original

    def test_newly_generated_previous_clip_is_used_and_replay_keeps_memory(self):
        chat,ident,refs,outputs,params=self.original()
        original=checkpoint(self.app.data,ident)
        for i,s in enumerate(original['timeline']):s['continuity']='continue' if i else 'cut'
        save(self.app.data/'outputs'/ident,original)
        before=(self.app.data/'outputs'/ident/'scenes.json').read_bytes()
        new=request(self.app,chat,{'source':ident,'assistant':False,'patches':[
            {'clip':2,'prompt':'The same man closes a book.','recover_memory':True},
            {'clip':3,'prompt':'The same man walks to the window.','recover_memory':True}]})['job_id']
        calls=[]
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            scoped=kw['scene'];calls.append((scoped,plan))
            self.assertEqual(scoped['continuity'],'continue')
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(b'\0\0\0\x18ftypisomnew')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params}
        with patch.object(self.app.engine,'generate_video',side_effect=generate), \
             patch('h3chat.soundtrack.probe',return_value={'duration':60}), \
             patch('h3chat.soundtrack.compose',side_effect=RuntimeError('Synthetic mux failure')):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(new,)),threading.Event())
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0][0]['resume_memory']['recent'],[str(self.app.data/outputs[0])])
        self.assertEqual(calls[1][0]['resume_memory']['recent'],[str(self.app.data/outputs[0]),str(self.app.data/'outputs'/new/'scene-002/video.mp4')])
        saved=checkpoint(self.app.data,new)
        self.assertEqual(saved['revision_completed'],[2,3])
        self.assertTrue(saved['timeline'][1]['recover_memory']);self.assertEqual(saved['timeline'][1]['continuity'],'continue')
        self.assertEqual(saved['parameters'][2]['visual_memory_recovered']['recent_clips'],[1,2])
        self.assertEqual((self.app.data/'outputs'/ident/'scenes.json').read_bytes(),before)
        retry=self.app.regenerate(chat)['job_id']
        def compose(engine,clips,audio,target,*args,**kwargs):
            target.write_bytes(b'\0\0\0\x18ftypisomnew');return {'duration':42}
        with patch.object(self.app.engine,'generate_video') as gpu, \
             patch('h3chat.soundtrack.probe',return_value={'duration':60}), \
             patch('h3chat.soundtrack.compose',side_effect=compose):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(retry,)),threading.Event())
        gpu.assert_not_called()
        self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
        manifest=__import__('h3chat.video_edit',fromlist=['describe']).describe(self.app,chat,retry)
        self.assertTrue(manifest['memory_recovery']);self.assertTrue(manifest['clips'][1]['memory']['default'])

    def test_unsupported_combinations_fail_before_enqueue_and_cut_is_explicit_opt_in(self):
        chat,ident,refs,outputs,params=self.original()
        value={'record':checkpoint(self.app.data,ident),'images':refs[:2]}
        for item in ({'clip':1,'recover_memory':True}, {'clip':2,'recover_memory':'yes'},
                     {'clip':2,'recover_memory':True,'mode':'video'},
                     {'clip':2,'recover_memory':True,'mode':'i2v','start_image':1},
                     {'clip':2,'recover_memory':True,'start':1,'end':10}):
            with self.subTest(item=item),self.assertRaises(ValueError):
                validate_edits([{'prompt':'Change the action'}|item],value)
        value['record']['timeline'][1]['continuity']='cut'
        self.assertFalse(describe(value['record'],1)['default'])
        accepted=validate_edits([{'clip':2,'prompt':'Explicitly continue from the previous scene','recover_memory':True}],value)
        self.assertTrue(accepted[0]['recover_memory']);self.assertEqual(accepted[0]['mode'],'reference')
        legacy=validate_edits([{'clip':2,'prompt':'A new scene'}],value)
        self.assertNotIn('recover_memory',legacy[0])

    def test_memory_and_selected_final_image_reach_native_generation_together(self):
        chat,ident,refs,outputs,params=self.original()
        new=request(self.app,chat,{'source':ident,'assistant':False,'patches':[
            {'clip':2,'prompt':'Walk naturally toward the requested final pose.','images':[1],
             'recover_memory':True,'end_frame':2}]})['job_id']
        def generate(model,settings,plan,chosen,job,cancel,stage,**kw):
            self.assertEqual(kw['scene']['resume_memory']['recent'],[str(self.app.data/outputs[0])])
            self.assertEqual([x['id'] for x in chosen],[refs[0]['id'],refs[1]['id'],refs[2]['id']])
            self.assertEqual(plan['images'][0]['role'],'reference')
            self.assertEqual(plan['images'][1],{'index':2,'role':'keyframe','seconds':359/24})
            self.assertIn('FINAL FRAME',plan['prompt']);self.assertEqual(plan['audios'][0]['start'],22)
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\0\0\0\x18ftypisomnew')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params}
        with patch.object(self.app.engine,'generate_video',side_effect=generate) as gpu, \
             patch('h3chat.soundtrack.probe',return_value={'duration':60}), \
             patch('h3chat.soundtrack.compose',return_value={'duration':42}):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(new,)),threading.Event())
        gpu.assert_called_once()
        answer=self.app.store.chat(chat)['messages'][-1];self.assertEqual(answer['status'],'done',answer['meta'])
        saved=checkpoint(self.app.data,new)
        self.assertEqual(saved['timeline'][1]['images'][1]['seconds'],359/24)

    def test_final_frame_uses_selected_next_clip_and_is_not_extracted_again_on_resume(self):
        chat,ident,refs,outputs,params=self.original()
        new=request(self.app,chat,{'source':ident,'assistant':False,'patches':[
            {'clip':2,'prompt':'Approach the next shot.','images':[1],'recover_memory':True,'end_frame':'next'}]})['job_id']
        extractions=[]
        def tool(worker,body,*args,**kwargs):
            self.assertEqual(body['op'],'extract_guides');extractions.append(body)
            self.assertEqual(body['source'],str(self.app.data/outputs[2]))
            self.assertEqual(body['positions'],{'last':0});self.assertEqual(body['frames'],288)
            path=Path(body['folder'])/'last.png';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'synthetic final image')
            return {'last':{'path':str(path),'width':640,'height':360,'frame':0}}
        def generate(model,settings,plan,chosen,job,cancel,stage,**kw):
            self.assertEqual(plan['images'][-1]['role'],'keyframe');self.assertEqual(plan['images'][-1]['seconds'],359/24)
            self.assertTrue(kw['scene']['resume_memory'])
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\0\0\0\x18ftypisomnew')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params}
        with patch.object(self.app.engine,'tool_call',side_effect=tool), \
             patch.object(self.app.engine,'generate_video',side_effect=generate), \
             patch('h3chat.soundtrack.probe',return_value={'duration':60}), \
             patch('h3chat.soundtrack.compose',side_effect=RuntimeError('Synthetic interrupted montage')):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(new,)),threading.Event())
        self.assertEqual(len(extractions),1)
        saved=checkpoint(self.app.data,new);self.assertEqual(saved['revision_end_frames']['2']['signature']['choice'],'next')
        retry=self.app.regenerate(chat)['job_id']
        with patch.object(self.app.engine,'tool_call') as tools,patch.object(self.app.engine,'generate_video') as gpu, \
             patch('h3chat.soundtrack.probe',return_value={'duration':60}), \
             patch('h3chat.soundtrack.compose',return_value={'duration':42}):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(retry,)),threading.Event())
        tools.assert_not_called();gpu.assert_not_called()
        answer=self.app.store.chat(chat)['messages'][-1];self.assertEqual(answer['status'],'done',answer['meta'])

    def test_final_anchor_rejects_invalid_indices_modes_and_missing_next_clip(self):
        chat,ident,refs,outputs,params=self.original();value={'record':checkpoint(self.app.data,ident),'images':refs[:2]}
        for item in ({'clip':3,'end_frame':'next'},{'clip':2,'end_frame':True},{'clip':2,'end_frame':3},
                     {'clip':2,'end_frame':'original','mode':'video'},{'clip':2,'end_frame':'original','start':1,'end':10}):
            with self.subTest(item=item),self.assertRaises(ValueError):validate_edits([{'prompt':'Change'}|item],value)

    def test_older_storyboard_recovers_only_its_explicit_saved_master_track(self):
        chat,ident,refs,outputs,params=self.original();record=checkpoint(self.app.data,ident)
        record['plan']['audios'][0]['role']='reference'
        record['request_context']={'settings':{'_video_soundtrack':refs[-1]}}
        save(self.app.data/'outputs'/ident,record)
        from h3chat.video_edit import source
        self.assertEqual(source(self.app,chat,ident)['audio']['id'],refs[-1]['id'])
        self.assertEqual(checkpoint(self.app.data,ident)['plan']['audios'][0]['role'],'reference')
        record['request_context']['settings']['_video_soundtrack']={'id':'not-the-supplied-track'}
        save(self.app.data/'outputs'/ident,record)
        with self.assertRaisesRegex(ValueError,'canzone originale'):source(self.app,chat,ident)
