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

    def test_chat_shows_only_used_inputs_without_changing_saved_references(self):
        chat,ident,refs,outputs,params=self.original()
        video={'id':ident,'name':'Original video.mp4','mime':'video/mp4','path':f'outputs/{ident}/video.mp4'}
        (self.app.data/video['path']).write_bytes(b'\0\0\0\x18ftypisom')
        self.app.store.gallery.register([video])
        new=request(self.app,chat,{'source':ident,'assistant':False,'remount':False,
            'patches':[{'clip':2,'mode':'video','prompt':'Replace the character','images':[2]}]})['job_id']
        messages=self.app.store.chat(chat)['messages'];user=messages[-2]
        self.assertEqual([r['id'] for r in user['display_media']],[ident,refs[1]['id'],refs[2]['id']])
        self.assertEqual(user['media'],refs)
        payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(new,))['payload'])
        self.assertEqual(payload['media'],refs)
        self.assertEqual(payload['settings']['_video_edit']['patches'][0]['images'],[2])
        self.assertNotIn('display_media',messages[0])
        self.assertEqual(describe(self.app,chat,ident)['images'][0]['id'],refs[0]['id'])
        self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(new,))
        replay=self.app.store.regenerate(chat)
        self.assertEqual(self.app.store.chat(chat)['messages'][-2]['display_media'],user['display_media'])
        replay_payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(replay,))['payload'])
        self.assertEqual(replay_payload['media'],refs)

    def test_per_request_resolution_uses_source_aspect_and_keeps_preferences(self):
        chat,ident,refs,outputs,params=self.original();before=copy.deepcopy(self.app.store.settings())
        manifest=describe(self.app,chat,ident);self.assertEqual(manifest['model_id'],self.model['id'])
        self.assertIn(self.model['id'],[m['id'] for m in manifest['models']])
        new=request(self.app,chat,{'source':ident,'assistant':False,'model':self.model['id'],
            'parameters':{'megapixels':2,'experimental_resolution':True},
            'patches':[{'clip':2,'prompt':'Closer framing'}]})['job_id']
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            canvas=kw['scene']['canvas'];self.assertEqual(canvas['aspect'],'16:9')
            self.assertGreater(canvas['width']*canvas['height'],1344*768)
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True);path.write_bytes(b'\x00\x00\x00\x18ftypisomnew')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params}
        def fit(worker,body,*args,**kw):
            Path(body['output']).write_bytes(b'\x00\x00\x00\x18ftypisomnew')
            return {}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch.object(self.app.engine,'tool_call',side_effect=fit) as fitted,patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',return_value={'duration':42}):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(new,)),threading.Event())
        self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
        self.assertEqual(fitted.call_args.args[1]['width'],640)
        self.assertEqual(self.app.store.settings(),before)

    def test_clip_only_partial_outputs_save_timeline_and_resume_without_regeneration(self):
        chat,ident,refs,outputs,params=self.original()
        original=(self.app.data/'outputs'/ident/'scenes.json').read_bytes()
        new=request(self.app,chat,{'source':ident,'assistant':False,'remount':False,'patches':[
            {'clip':2,'prompt':'Closer framing','start':4,'end':9},
            {'clip':3,'prompt':'A new final moment'}]})['job_id']
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(b'\x00\x00\x00\x18ftypisomnew')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params|{'duration':kw['scene']['duration']}}
        def splice(worker,body,*args,**kw):
            Path(body['output']).write_bytes(b'\0\0\0\x18ftypisommerged')
            return {'frames':360}
        with patch.object(self.app.engine,'generate_video',side_effect=generate) as gpu,patch.object(self.app.engine,'tool_call',side_effect=splice) as merging,patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=RuntimeError('Synthetic mux error')):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(new,)),threading.Event())
        self.assertEqual(gpu.call_count,2);merging.assert_called_once()
        saved=checkpoint(self.app.data,new);self.assertFalse(saved['revision_remount'])
        self.assertEqual(saved['revision_completed'],[2,3])
        recovered=self.app.regenerate(chat)['job_id']
        def compose(engine,clips,audio,target,*args,**kw):
            target.write_bytes(b'\x00\x00\x00\x18ftypisomnew')
            return {'duration':kw['audio_duration']}
        with patch.object(self.app.engine,'generate_video') as repeat,patch.object(self.app.engine,'tool_call') as splice,patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=compose) as mux:
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(recovered,)),threading.Event())
        repeat.assert_not_called();splice.assert_not_called()
        self.assertEqual([c.kwargs['audio_start'] for c in mux.call_args_list],[26,37])
        self.assertEqual([c.kwargs['audio_duration'] for c in mux.call_args_list],[5,12])
        self.assertTrue(all(len(c.args[1])==1 for c in mux.call_args_list))
        self.assertTrue(all(c.args[1][0] not in [self.app.data/p for p in outputs] for c in mux.call_args_list))
        answer=self.app.store.chat(chat)['messages'][-1]
        self.assertEqual(answer['status'],'done',answer['meta']);self.assertEqual(len(answer['media']),2)
        self.assertEqual([m['generation']['duration'] for m in answer['media']],[5,12])
        self.assertTrue(all(m['generation']['clip_only'] for m in answer['media']))
        for m in answer['media']:self.assertEqual(self.app.store.gallery.get(m['id'])['path'],m['path'])
        self.assertEqual(answer['meta']['video_parameters']['reused_clips'],0)
        self.assertTrue(saved['working_timeline'])
        self.assertEqual(describe(self.app,chat,recovered)['duration'],42)
        self.assertEqual(describe(self.app,chat,recovered)['edited_clips'],[2,3])
        self.assertEqual(answer['media'][0]['generation']['timeline_id'],recovered)
        self.assertEqual((self.app.data/'outputs'/ident/'scenes.json').read_bytes(),original)

    def test_accumulated_edits_use_updated_clip_and_assemble_without_ai(self):
        from h3chat.video_assemble import request as assemble
        from h3chat.video_edit import source,source_interval
        chat,ident,refs,outputs,params=self.original()
        before=(self.app.data/'outputs'/ident/'scenes.json').read_bytes()
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            out=self.app.data/'outputs'/job/'video.mp4';out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(b'\0\0\0\x18ftypisomnew')
            return {'path':out.relative_to(self.app.data).as_posix(),'generation':params|{'duration':kw['scene']['duration']}}
        def compose(engine,clips,audio,target,*args,**kw):
            target.write_bytes(b'\0\0\0\x18ftypisomfinal');return {'duration':kw['audio_duration']}
        def splice(worker,body,*args,**kw):
            Path(body['output']).write_bytes(b'\0\0\0\x18ftypisommerged');return {'frames':360}
        with patch.object(self.app.engine,'generate_video',side_effect=generate) as gpu,patch.object(self.app.engine,'tool_call',side_effect=splice),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=compose) as mux:
            first=request(self.app,chat,{'source':ident,'assistant':False,'remount':False,'patches':[{'clip':2,'mode':'video','prompt':'Change outfit','start':2,'end':6}]})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(first,)),threading.Event())
            updated=source(self.app,chat,first)
            self.assertEqual(source_interval(updated,{'clip':2,'start':7,'end':9})['path'],updated['record']['outputs'][1])
            second=request(self.app,chat,{'source':first,'assistant':False,'remount':False,'patches':[{'clip':3,'prompt':'Change background'}]})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(second,)),threading.Event())
            saved=checkpoint(self.app.data,second)
            self.assertEqual(saved['outputs'][1],updated['record']['outputs'][1]);self.assertEqual(saved['edited_clips'],[2,3])
            self.assertEqual(saved['outputs'][0],outputs[0]);self.assertEqual(gpu.call_count,2)
            final=assemble(self.app,chat,{'source':second})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(final,)),threading.Event())
            self.assertEqual(gpu.call_count,2)
            self.assertEqual(mux.call_args.args[1],[self.app.data/p for p in saved['outputs']])
            self.assertEqual(mux.call_args.kwargs['audio_start'],7);self.assertEqual(mux.call_args.kwargs['audio_duration'],42)
        answer=self.app.store.chat(chat)['messages'][-1]
        self.assertEqual(answer['status'],'done',answer['meta']);self.assertFalse(answer['media'][0]['generation'].get('clip_only',False))
        self.assertEqual(describe(self.app,chat,final)['edited_clips'],[2,3])
        self.assertEqual((self.app.data/'outputs'/ident/'scenes.json').read_bytes(),before)

    def test_full_version_from_draft_uses_latest_timeline_metadata(self):
        chat,original,refs,outputs,params=self.original()
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            out=self.app.data/'outputs'/job/'video.mp4';out.parent.mkdir(parents=True);out.write_bytes(b'\0\0\0\x18ftypisomnew')
            return {'path':out.relative_to(self.app.data).as_posix(),'generation':params|{'duration':kw['scene']['duration']}}
        def mux(engine,clips,audio,target,*args,**kw):
            target.write_bytes(b'\0\0\0\x18ftypisomfinal');return {'duration':kw['audio_duration']}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=mux):
            draft=request(self.app,chat,{'source':original,'assistant':False,'remount':False,'patches':[{'clip':2,'prompt':'Change outfit'}]})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(draft,)),threading.Event())
            final=request(self.app,chat,{'source':draft,'assistant':False,'remount':True,'patches':[{'clip':3,'prompt':'Change background'}]})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(final,)),threading.Event())
        answer=self.app.store.chat(chat)['messages'][-1];self.assertEqual(answer['status'],'done',answer['meta'])
        generation=answer['media'][0]['generation'];self.assertTrue(generation['remount'])
        self.assertNotIn('clip_only',generation);self.assertNotIn('timeline_id',generation)
        self.assertEqual(answer['media'][0]['id'],final)
        self.assertEqual(describe(self.app,chat,final)['edited_clips'],[2,3])
        self.assertEqual(checkpoint(self.app.data,final)['outputs'][1],checkpoint(self.app.data,draft)['outputs'][1])

    def test_remount_flag_rejects_non_booleans_before_queueing(self):
        chat,ident,*_=self.original()
        for invalid in ('false',0,None):
            with self.subTest(value=invalid),self.assertRaisesRegex(ValueError,'Rimonta'):
                request(self.app,chat,{'source':ident,'remount':invalid,'patches':[{'clip':1,'prompt':'Change'}]})
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),1)

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
        new=request(self.app,chat,{'source':ident,'assistant':False,'video_steps':20,'patches':[
            {'clip':2,'prompt':'Close-up of <Picture 1> singing.','images':[1,2],'lip_sync':True},
            {'clip':3,'prompt':'Close-up of <Picture 2>.','images':[2]}]})['job_id']
        calls=[]
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            from h3chat.video_options import options
            self.assertEqual(options(model,settings,False)['steps'],20)
            calls.append((plan,selected,kw['scene']))
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\x00\x00\x00\x18ftypisomnew')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params|{'steps':20}}
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
        self.assertEqual(answer['meta']['video_parameters']['edited_steps'],[20])
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

    def test_i2v_requires_one_guide_and_does_not_queue_invalid_modes(self):
        chat,ident,*_=self.original()
        for item in ({'mode':'i2v'},{'mode':'i2v','start_image':True},
                     {'mode':'i2v','start_image':3},{'mode':'i2v','start_image':1,'images':[1,2]},
                     {'mode':'reference','start_image':1},{'mode':'other'}):
            with self.subTest(item=item),self.assertRaises(ValueError):
                request(self.app,chat,{'source':ident,'assistant':False,'patches':[{'clip':2,'prompt':'Animate'}|item]})
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),1)

    def test_i2v_fresh_upload_starts_selected_interval_at_frame_zero(self):
        chat,ident,refs,outputs,params=self.original()
        extra={'id':'4'*32,'name':'new-first-frame.png','path':'uploads/new-first-frame.png','mime':'image/png'}
        path=self.app.data/extra['path'];path.write_bytes(b'synthetic');(path.parent/(extra['id']+'.json')).write_text(json.dumps(extra))
        new=request(self.app,chat,{'source':ident,'assistant':False,'media':[{'id':extra['id']}],
            'patches':[{'clip':2,'prompt':'Continue <Picture 1> with slow camera motion.','mode':'i2v','start_image':3,'start':4,'end':9,'lip_sync':True}]})['job_id']
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            self.assertEqual([r['id'] for r in selected],[extra['id'],refs[-1]['id']])
            self.assertEqual(plan['images'],[{'index':1,'role':'keyframe','seconds':0}])
            self.assertEqual(plan['audios'],[{'index':1,'role':'lipsync','start':26}])
            self.assertIn('EXACT INITIAL FRAME',plan['prompt']);self.assertIn('Begin from <Picture 1>',plan['prompt'])
            self.assertEqual((kw['scene']['duration'],kw['scene']['frames'],kw['scene']['start']),(5,120,19))
            self.assertEqual(kw['scene']['canvas']['aspect'],'16:9')
            out=self.app.data/'outputs'/job/'video.mp4';out.parent.mkdir(parents=True);out.write_bytes(b'\0\0\0\x18ftypisom')
            return {'path':out.relative_to(self.app.data).as_posix(),'generation':params|{'duration':5,'output_frames':120}}
        def splice(worker,body,*args,**kw):
            self.assertEqual((body['start_frame'],body['end_frame'],body['total_frames']),(96,216,360))
            Path(body['output']).write_bytes(b'\0\0\0\x18ftypisom');return {'frames':360}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch.object(self.app.engine,'tool_call',side_effect=splice),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',return_value={'duration':42}) as mux:
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(new,)),threading.Event())
        answer=self.app.store.chat(chat)['messages'][-1];self.assertEqual(answer['status'],'done',answer['meta'])
        self.assertEqual(mux.call_args.kwargs['audio_start'],7)
        saved=checkpoint(self.app.data,new)
        self.assertEqual(saved['timeline'][1]['images'],[{'index':3,'role':'keyframe','seconds':4}])
        manifest=describe(self.app,chat,new);self.assertEqual((manifest['clips'][1]['mode'],manifest['clips'][1]['start_image']),('i2v',3))
        from h3chat.video_recreate import load
        recipe=load(self.app,chat,new)['recipes'][1]
        self.assertEqual(next(x for x in recipe['plan']['images'] if x['role']=='keyframe')['seconds'],4)

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

class EditRequestRegressionTests(VideoEditTests):
    def test_reload_edit_uses_only_selected_references_and_saved_contract(self):
        from h3chat.request_draft import load
        chat,ident,refs,_,_=self.original()
        video={'id':ident,'name':'Film.mp4','mime':'video/mp4','path':f'outputs/{ident}/video.mp4'}
        (self.app.data/video['path']).write_bytes(b'\0\0\0\x18ftypisom')
        self.app.store.gallery.register([video])
        queued=request(self.app,chat,{'source':ident,'assistant':False,'remount':False,'patches':[{'clip':2,'mode':'video','prompt':'Use <Picture 2>','images':[2],'audio_guide':False}]})['job_id']
        answer=self.app.store.chat(chat)['messages'][-1];before=self.app.store.all('SELECT * FROM jobs')
        draft=load(self.app,chat,answer['id'])
        self.assertEqual([m['id'] for m in draft['media']],[ident,refs[1]['id']])
        self.assertEqual(draft['video_edit']['image_ids'],[r['id'] for r in refs[:2]])
        self.assertFalse(draft['video_edit']['patches'][0]['audio_guide'])
        self.assertEqual(self.app.store.all('SELECT * FROM jobs'),before)

    def test_disabled_audio_guide_never_sends_audio_to_minimax(self):
        chat,ident,refs,outputs,params=self.original()
        job=request(self.app,chat,{'source':ident,'assistant':False,'remount':False,'patches':[{'clip':2,'mode':'video','prompt':'A blue jacket','images':[1],'audio_guide':False}]})['job_id']
        def generate(model,settings,plan,chosen,job_id,cancel,stage,**kw):
            self.assertEqual(plan['audios'],[])
            self.assertEqual(chosen,[refs[0]])
            out=self.app.data/'outputs'/job_id/'video.mp4';out.parent.mkdir(parents=True);out.write_bytes(b'\0\0\0\x18ftypisom')
            return {'path':out.relative_to(self.app.data).as_posix(),'generation':params}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch('h3chat.soundtrack.probe',return_value={'duration':1}),patch('h3chat.soundtrack.compose',return_value={'duration':15}):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(job,)),threading.Event())
        answer=self.app.store.chat(chat)['messages'][-1];self.assertEqual(answer['status'],'done',answer['content'])

    def test_queued_removal_keeps_timeline_editable_and_does_not_use_ai(self):
        from h3chat.video_assemble import request as assemble
        chat,ident,refs,outputs,params=self.original()
        queued=assemble(self.app,chat,{'source':ident,'remove_clips':[2]})['job_id']
        def cpu(worker,body,*args,**kw):
            self.assertEqual(worker,'video-remix-worker.py');self.assertEqual(body['op'],'timeline_audio')
            self.assertEqual(body['intervals'],[{'start':7,'duration':15},{'start':37,'duration':12}])
            Path(body['output']).write_bytes(b'synthetic soundtrack');return {'duration':27}
        def mux(engine,videos,audio,out,*args,**kw):
            self.assertEqual(kw['audio_start'],0);self.assertEqual(kw['audio_duration'],27)
            self.assertEqual([str(p.relative_to(self.app.data)) for p in videos],[str(Path(outputs[0])),str(Path(outputs[2]))])
            out.write_bytes(b'\0\0\0\x18ftypisom');return {'duration':27}
        with patch.object(self.app.engine,'tool_call',side_effect=cpu),patch.object(self.app.engine,'generate_video') as gpu,patch('h3chat.soundtrack.compose',side_effect=mux):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(queued,)),threading.Event())
        gpu.assert_not_called();answer=self.app.store.chat(chat)['messages'][-1]
        self.assertEqual(answer['status'],'done',answer['content'])
        manifest=describe(self.app,chat,queued)
        self.assertEqual(manifest['duration'],27);self.assertEqual(len(manifest['clips']),2)
        self.assertTrue(manifest['preview_audio']['url'].endswith('timeline-audio.wav'))

    def test_remove_clip_reindexes_video_and_cuts_matching_audio(self):
        from h3chat.video_assemble import remove_clips
        chat,ident,refs,outputs,params=self.original();original=checkpoint(self.app.data,ident)
        result,intervals=remove_clips(original,[2])
        self.assertEqual(result['outputs'],[outputs[0],outputs[2]])
        self.assertEqual([x['start'] for x in result['timeline']],[0,15])
        self.assertEqual([x['index'] for x in result['timeline']],[0,1])
        self.assertEqual(intervals,[{'start':7,'duration':15},{'start':37,'duration':12}])
        self.assertEqual(result['audio_start'],0);self.assertEqual(len(original['timeline']),3)
        original['plan']['images']=[{'index':1,'role':'keyframe','seconds':18},{'index':2,'role':'keyframe','seconds':35}]
        retimed,_=remove_clips(original,[2]);self.assertEqual(retimed['plan']['images'],[{'index':1,'role':'reference','seconds':0},{'index':2,'role':'keyframe','seconds':20}])
        for bad in ([1,2,3],[0],[2,2],[True]):
            with self.assertRaises(ValueError):remove_clips(original,bad)

if __name__=='__main__':unittest.main()
