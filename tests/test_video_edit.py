import copy,json,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from h3chat.video_edit import describe,request
from h3chat.video_resume import checkpoint,save
from h3chat.video_timeline import timeline
import test_video as fixture


class VideoEditTests(unittest.TestCase):
    setUp=fixture.VideoTests.setUp
    tearDown=fixture.VideoTests.tearDown

    def original(self):
        chat=self.app.store.create_chat()['id']
        refs=[{'id':'1'*32,'name':'hero.png','path':'uploads/hero.png','mime':'image/png'},
              {'id':'2'*32,'name':'cabin.png','path':'uploads/cabin.png','mime':'image/png'},
              {'id':'3'*32,'name':'song.wav','path':'uploads/song.wav','mime':'audio/wav'}]
        for media in refs:
            path=self.app.data/media['path'];path.parent.mkdir(exist_ok=True);path.write_bytes(b'synthetic asset')
        settings=self.app.store.settings()|{'_video':True,'_assistant':False}
        ident=self.app.store.enqueue(chat,'Synthetic film',refs,settings)
        folder=self.app.data/'outputs'/ident;folder.mkdir(parents=True)
        scenes=timeline(42)
        for s in scenes:s.update(images=[{'index':1,'role':'reference'}],lip_sync=False,continuity='cut')
        params={'width':640,'height':360,'canvas_width':640,'canvas_height':384,'aspect':'16:9','aspect_source':'prompt','fps':24,'steps':12}
        outputs=[]
        for i in range(3):
            path=folder/f'scene-{i+1:03d}/video.mp4';path.parent.mkdir();path.write_bytes(b'\x00\x00\x00\x18ftypisom'+bytes([i]));outputs.append(path.relative_to(self.app.data).as_posix())
        plan={'prompt':'Original film','images':[{'index':i,'role':'reference','seconds':0} for i in (1,2)],'audios':[{'index':1,'role':'reuse','start':7}]}
        save(folder,{'timeline':scenes,'prompts':['first','second','third'],'plan':plan,'completed':3,'parameters':[params]*3,'outputs':outputs,'model':self.model['id'],'audio_start':7})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
        meta={'intent':'video','references':refs,'video_parameters':params|{'duration':42,'scenes':3}}
        self.app.store.update_answer(job,'Original video','done',[],meta)
        self.app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(ident,))
        return chat,ident,refs,outputs,params

    def test_manifest_and_selection_are_scoped_to_completed_chat(self):
        chat,ident,refs,outputs,params=self.original()
        manifest=describe(self.app,chat,ident)
        self.assertEqual([(s['start'],s['end']) for s in manifest['clips']],[(0,15),(15,30),(30,42)])
        self.assertEqual(manifest['images'][0]['name'],'hero.png')
        self.assertNotIn('settings',manifest)
        other=self.app.store.create_chat()['id']
        for target in (ident,'../'+ident):
            with self.assertRaises(ValueError):describe(self.app,other,target)
        self.app.store.execute("UPDATE jobs SET status='running' WHERE id=?",(ident,))
        with self.assertRaises(ValueError):describe(self.app,chat,ident)

    def test_invalid_edits_and_duplicate_queue_do_not_create_work(self):
        chat,ident,refs,outputs,params=self.original()
        bad=[[],[{'clip':0,'prompt':'Change'}],[{'clip':True,'prompt':'Change'}],
             [{'clip':1,'prompt':''}],[{'clip':1,'prompt':'Change','images':[3]}],
             [{'clip':1,'prompt':'Use <Picture 2>','images':[1]}],
             [{'clip':1,'prompt':'Change','lip_sync':'yes'}],
             [{'clip':1,'prompt':'Change'},{'clip':1,'prompt':'Duplicate'}]]
        before=len(self.app.store.all('SELECT id FROM jobs'))
        for patches in bad:
            with self.assertRaises(ValueError):request(self.app,chat,{'source':ident,'patches':patches,'assistant':False})
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),before)
        request(self.app,chat,{'source':ident,'patches':[{'clip':2,'prompt':'Close-up'}],'assistant':False})
        with self.assertRaisesRegex(ValueError,'richiesta attiva'):request(self.app,chat,{'source':ident,'patches':[{'clip':3,'prompt':'Close-up'}],'assistant':False})

    def test_only_selected_clips_are_generated_and_whole_original_song_is_remounted(self):
        chat,ident,refs,outputs,params=self.original()
        original=(self.app.data/'outputs'/ident/'scenes.json').read_bytes()
        settings=copy.deepcopy(self.app.store.settings())
        new=request(self.app,chat,{'source':ident,'assistant':False,'patches':[
            {'clip':2,'prompt':'Close-up of <Picture 1> singing.','images':[1,2],'lip_sync':True},
            {'clip':3,'prompt':'Close-up of <Picture 2>.','images':[2]}]})['job_id']
        calls=[]
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            calls.append((plan,selected,kw['scene']))
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\x00\x00\x00\x18ftypisomnew')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch.object(self.app.engine,'generate_long_video') as full,patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',return_value={'duration':42}) as mux,patch.object(self.app.knowledge,'retrieve') as rag:
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(new,)),threading.Event())
        answer=self.app.store.chat(chat)['messages'][-1]
        self.assertEqual(answer['status'],'done',answer['meta'])
        self.assertEqual(len(calls),2);full.assert_not_called();rag.assert_not_called()
        self.assertEqual([c[0]['audios'][0]['start'] for c in calls],[22,37])
        self.assertEqual([c[0]['audios'][0]['role'] for c in calls],['lipsync','reuse'])
        self.assertEqual(calls[0][2]['canvas']['aspect'],'16:9')
        self.assertEqual(calls[1][2]['frames'],288)
        self.assertEqual(calls[1][1][0]['id'],refs[1]['id'])
        self.assertIn('<Picture 1>',calls[1][0]['prompt']);self.assertNotIn('<Picture 2>',calls[1][0]['prompt'])
        self.assertNotIn('Original scene, for context only',calls[1][0]['prompt'])
        self.assertEqual(mux.call_args.args[1][0],self.app.data/outputs[0])
        self.assertEqual(mux.call_args.args[2],self.app.data/refs[-1]['path'])
        self.assertEqual(mux.call_args.kwargs['audio_start'],7);self.assertEqual(mux.call_args.kwargs['audio_duration'],42)
        self.assertEqual((self.app.data/'outputs'/ident/'scenes.json').read_bytes(),original)
        self.assertEqual(self.app.store.settings(),settings)
        saved=checkpoint(self.app.data,new)
        self.assertEqual(saved['outputs'][0],outputs[0]);self.assertEqual(saved['revision_completed'],[2,3])
        self.assertEqual(answer['meta']['video_parameters']['reused_clips'],1)
        self.assertEqual(answer['media'][0]['id'],new)
        self.assertEqual(describe(self.app,chat,new)['clips'][2]['images'],[2])

    def test_interrupted_edit_recovers_generated_replacement_without_redoing_it(self):
        chat,ident,refs,outputs,params=self.original()
        new=request(self.app,chat,{'source':ident,'assistant':False,'patches':[{'clip':2,'prompt':'Hero close-up'},{'clip':3,'prompt':'Final close-up'}]})['job_id']
        count=0
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            nonlocal count
            count+=1
            if count==2:raise RuntimeError('Synthetic GPU interruption')
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\x00\x00\x00\x18ftypisomnew')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',return_value={'duration':42}):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(new,)),threading.Event())
            self.assertEqual(checkpoint(self.app.data,new)['revision_completed'],[2])
            recovered=self.app.regenerate(chat)['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(recovered,)),threading.Event())
        self.assertEqual(count,3)
        self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
        self.assertEqual(checkpoint(self.app.data,recovered)['outputs'][1],checkpoint(self.app.data,new)['outputs'][1])

    def test_missing_reference_and_short_audio_fail_before_loading_video(self):
        chat,ident,refs,outputs,params=self.original()
        new=request(self.app,chat,{'source':ident,'assistant':False,'patches':[{'clip':3,'prompt':'Close-up'}]})['job_id']
        with patch.object(self.app.engine,'generate_video') as gpu,patch('h3chat.soundtrack.probe',return_value={'duration':40}):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(new,)),threading.Event())
        gpu.assert_not_called();self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'failed')
        (self.app.data/refs[0]['path']).unlink()
        with self.assertRaisesRegex(ValueError,'riferimento originale'):describe(self.app,chat,ident)

    def test_new_gallery_reference_is_added_and_available_in_following_revision(self):
        chat,ident,refs,outputs,params=self.original()
        extra={'id':'4'*32,'name':'new-singer.png','path':'uploads/new-singer.png','mime':'image/png'}
        path=self.app.data/extra['path'];path.write_bytes(b'synthetic');(path.parent/(extra['id']+'.json')).write_text(json.dumps(extra))
        new=request(self.app,chat,{'source':ident,'assistant':False,'media':[{'id':extra['id']}],'patches':[{'clip':2,'prompt':'Close-up of <Picture 3>','images':[3],'lip_sync':True}]})['job_id']
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            self.assertEqual(selected[0]['id'],extra['id']);self.assertIn('<Picture 1>',plan['prompt'])
            out=self.app.data/'outputs'/job/'video.mp4';out.parent.mkdir(parents=True);out.write_bytes(b'\x00\x00\x00\x18ftypisom')
            return {'path':out.relative_to(self.app.data).as_posix(),'generation':params}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',return_value={'duration':42}):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(new,)),threading.Event())
        self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
        manifest=describe(self.app,chat,new)
        self.assertEqual(manifest['images'][2]['id'],extra['id']);self.assertEqual(manifest['clips'][1]['images'],[3])

    def test_invalid_partial_intervals_are_rejected_without_queuing(self):
        chat,ident,*_=self.original()
        for span in ({'start':4},{'end':9},{'start':True,'end':9},{'start':float('nan'),'end':9},
                     {'start':-1,'end':9},{'start':9,'end':4},{'start':4,'end':4.5},{'start':4,'end':16}):
            with self.subTest(span=span),self.assertRaises(ValueError):
                request(self.app,chat,{'source':ident,'assistant':False,'patches':[{'clip':2,'prompt':'Close-up'}|span]})
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),1)

    def test_partial_interval_uses_correct_audio_and_preserves_clip_timeline(self):
        chat,ident,refs,outputs,params=self.original()
        original=(self.app.data/'outputs'/ident/'scenes.json').read_bytes()
        new=request(self.app,chat,{'source':ident,'assistant':False,'patches':[{'clip':2,'prompt':'Close-up','start':4.01,'end':9.01,'lip_sync':True}]})['job_id']
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            self.assertEqual(plan['audios'][0],{'index':1,'role':'lipsync','start':26})
            self.assertEqual((kw['scene']['frames'],kw['scene']['duration'],kw['scene']['start']),(120,5,19))
            self.assertIn('global film interval 19–24 seconds',plan['prompt'])
            out=self.app.data/'outputs'/job/'video.mp4';out.parent.mkdir(parents=True);out.write_bytes(b'\x00\x00\x00\x18ftypisom')
            return {'path':out.relative_to(self.app.data).as_posix(),'generation':params|{'duration':5,'output_frames':120}}
        def splice(worker,body,*args,**kw):
            self.assertEqual(worker,'video-splice-worker.py')
            self.assertEqual((body['start_frame'],body['end_frame'],body['total_frames']),(96,216,360))
            self.assertEqual(body['original'],str(self.app.data/outputs[1]))
            Path(body['output']).write_bytes(b'\x00\x00\x00\x18ftypisommerged')
            return {'frames':360,'duration':15}
        with patch.object(self.app.engine,'generate_video',side_effect=generate) as gpu,patch.object(self.app.engine,'tool_call',side_effect=splice),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',return_value={'duration':42}) as mux:
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(new,)),threading.Event())
        answer=self.app.store.chat(chat)['messages'][-1];self.assertEqual(answer['status'],'done',answer['meta'])
        gpu.assert_called_once();saved=checkpoint(self.app.data,new)
        self.assertEqual(saved['timeline'][1]['start'],15);self.assertEqual(saved['timeline'][1]['frames'],360)
        self.assertEqual(saved['parameters'][1]['duration'],15);self.assertEqual(saved['parameters'][1]['output_frames'],360)
        self.assertEqual(saved['outputs'][::2],outputs[::2]);self.assertTrue(saved['outputs'][1].endswith('edited.mp4'))
        self.assertEqual(mux.call_args.kwargs['audio_start'],7);self.assertEqual(mux.call_args.kwargs['audio_duration'],42)
        self.assertEqual((self.app.data/'outputs'/ident/'scenes.json').read_bytes(),original)
        self.assertEqual(answer['meta']['video_parameters']['replaced_intervals'],[{'clip':2,'start':4,'end':9}])
        self.assertEqual(describe(self.app,chat,new)['clips'][1]['end'],30)

    def test_failed_splice_recovers_generated_interval_without_new_gpu_work(self):
        chat,ident,refs,outputs,params=self.original()
        new=request(self.app,chat,{'source':ident,'assistant':False,'patches':[{'clip':3,'prompt':'Close-up','start':1,'end':4}]})['job_id']
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            self.assertFalse(kw['scene']['last'])
            out=self.app.data/'outputs'/job/'video.mp4';out.parent.mkdir(parents=True);out.write_bytes(b'\x00\x00\x00\x18ftypisom')
            return {'path':out.relative_to(self.app.data).as_posix(),'generation':params}
        calls=0
        def splice(worker,body,*args,**kw):
            nonlocal calls
            calls+=1
            if calls==1:raise RuntimeError('Synthetic interrupted splice')
            Path(body['output']).parent.mkdir(parents=True,exist_ok=True);Path(body['output']).write_bytes(b'\x00\x00\x00\x18ftypisom')
            return {'frames':288}
        with patch.object(self.app.engine,'generate_video',side_effect=generate) as gpu,patch.object(self.app.engine,'tool_call',side_effect=splice),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',return_value={'duration':42}):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(new,)),threading.Event())
            self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'failed')
            recovered=self.app.regenerate(chat)['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(recovered,)),threading.Event())
        gpu.assert_called_once();self.assertEqual(calls,2);self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')

if __name__=='__main__':unittest.main()
