"""Synthetic no-audio sequences; no models, external APIs or production data."""
import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from h3chat.video_sequence import apply,resolve,scenes,controls
from h3chat.video_options import options
from h3chat.video_engine import VideoEngine
from h3chat.video_routing import direct_plan
from h3chat.downloads import Cancelled
import test_video as fixture

class SequenceTests(unittest.TestCase):
    def test_prompt_scene_count_and_duration_override_controls(self):
        settings={'video_model':'m','_video_scene_count':2,'_video_scene_seconds':12}
        for text in ('Crea un video unico di 3 scene da 20 secondi','Create 3 scenes of 20 seconds','3 scene, 20 secondi l’una'):
            spec=resolve(settings,text)
            self.assertEqual((spec['count'],spec['scene_seconds'],spec['duration']),(3,20,60))
        spec=resolve(settings,'Video di 45 secondi in 3 scene')
        self.assertEqual((spec['count'],spec['scene_seconds'],spec['duration']),(3,15,45))
        self.assertEqual(resolve(settings,'Video di 2 minuti')['duration'],120)
    def test_long_scenes_keep_boundaries_and_native_limit(self):
        s=apply({'video_model':'m','_video_scene_count':3,'_video_scene_seconds':20},'A landscape')
        self.assertEqual(options({'id':'m'},s,False)['duration'],15)
        clips=scenes(s)
        self.assertEqual([c['duration'] for c in clips],[15,5]*3)
        self.assertEqual([c['start'] for c in clips],[0,15,20,35,40,55])
        self.assertEqual([c['logical_scene'] for c in clips],[1,1,2,2,3,3])
        self.assertEqual(sum(c['frames'] for c in clips),60*24)
    def test_explicit_fifteen_is_not_replaced_by_twelve_or_segment_cap(self):
        original={'video_model':'m','video_overrides':{'m':{'duration':12}},'_video_segment_seconds':10}
        for settings,prompt in ((original,'Video di 15 secondi'),(original|{'_video_scene_seconds':15},'A landscape')):
            result=apply(settings,prompt)
            self.assertEqual(result['_video_duration'],15)
            # A single scene longer than the chosen segment cap must split too.
            self.assertEqual(resolve(settings,prompt)['duration'],15)
        self.assertEqual(original['video_overrides']['m']['duration'],12)
    def test_bad_values_rejected_before_any_generation(self):
        for body in ({'video_scene_count':True},{'video_scene_count':0},{'video_scene_seconds':float('nan')},{'video_scene_seconds':0}):
            with self.assertRaises(ValueError):controls(body)
        with self.assertRaises(ValueError):resolve({'video_model':'m'},'100 scene da 15 secondi')
        with self.assertRaises(ValueError):apply({'video_model':'m'},'2 scene da 15 secondi',remote=True)
    def test_storyboard_without_audio_honors_logical_windows(self):
        from h3chat.video_storyboard import build,local_plan
        settings=apply({'video_model':'m','_assistant':True,'_video_editing':'storyboard','context':8000,'video_prompt_max_tokens':3000,'chat_model':'chat'},'2 scene da 20 secondi')
        descriptions=['A ceramic teapot rotates on a table.','A hand lifts the lid.','The camera reveals a garden.','A bird flies toward the trees.']
        value={'style':'Soft daylight.','shots':[{'end':i+1,'prompt':text,'time_basis':'local','continuity':'cut','lip_sync':False,'images':[]} for i,text in enumerate(descriptions)]}
        engine=VideoEngine();engine.require_model=Mock(return_value={});engine.start_llama=Mock();engine.completion=Mock(return_value=(json.dumps(value),'stop'))
        plan={'prompt':'A teapot and a garden.','images':[],'audios':[]}
        with tempfile.TemporaryDirectory() as tmp:result=build(engine,plan,[],settings,'2 scene da 20 secondi',threading.Event(),lambda _:None,Path(tmp)/'log')
        self.assertEqual([s['end'] for s in result['shots']],[15,20,35,40])
        self.assertEqual([s['logical_scene'] for s in result['shots']],[1,1,2,2])
        self.assertEqual([s['continuity'] for s in result['shots']],['cut','continue','cut','continue'])
        local,refs=local_plan(result,result['shots'][0],plan,[],None,0)
        self.assertNotIn('<Audio',local['prompt']);self.assertEqual(local['audios'],[])
    def test_modes_preserve_start_frame_and_reference_identity(self):
        for mode,refs in (('t2v',[]),('i2v',[{'id':'i','name':'input.png','path':'input.png','mime':'image/png'}]),('ref2video',[{'id':'i','name':'input.png','path':'input.png','mime':'image/png'}])):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                engine=VideoEngine();engine.data=Path(tmp);engine.tool_call=Mock(return_value={});calls=[]
                prompt=('I2V. Use <Picture 1> as first frame. ' if mode=='i2v' else 'Use <Picture 1> as identity reference. ' if refs else '')+'A camera moves across a landscape.'
                settings=apply({'video_model':'m','_assistant':False,'_video_scene_count':2,'_video_scene_seconds':20},prompt)
                plan=direct_plan(prompt,refs,40);before=copy.deepcopy(plan)
                def generate(model,settings,local,chosen,job,cancel,stage,**kw):
                    scene=kw['scene'];calls.append((local,chosen,scene));target=engine.data/'outputs'/job/'video.mp4';target.parent.mkdir(parents=True);target.write_bytes(b'\x00\x00\x00\x18ftypisom')
                    return {'id':job,'path':target.relative_to(engine.data).as_posix(),'generation':{'duration':scene['duration'],'seed':1}}
                engine.generate_video=Mock(side_effect=generate)
                with patch('h3chat.soundtrack.compose',return_value={'duration':40,'clip_audio':True}) as compose:
                    result=engine.generate_long_video({'id':'m'},settings,plan,refs,'a'*32,threading.Event(),lambda _:None,prompt=prompt)
                self.assertEqual(len(calls),4);self.assertEqual(plan,before)
                self.assertEqual(result['generation']['duration'],40);self.assertEqual(result['generation']['scenes'],2)
                self.assertIsNone(compose.call_args.args[2]);self.assertTrue(compose.call_args.kwargs['clip_audio'])
                if refs:
                    self.assertEqual(calls[0][0]['images'][0]['role'],'keyframe' if mode=='i2v' else 'reference')
                    self.assertTrue(all(c[0]['images'][0]['role']=='reference' for c in calls[1:]))
                    self.assertTrue(all(c[1]==refs for c in calls))
                saved=json.loads((engine.data/'outputs'/('a'*32)/'scenes.json').read_text())
                self.assertEqual(saved['completed'],4);self.assertEqual(saved['request_context']['settings']['_video_sequence']['count'],2)
                self.assertIn('generated_soundtrack',saved)

class SequenceRequestTests(unittest.TestCase):
    setUp=fixture.VideoTests.setUp
    tearDown=fixture.VideoTests.tearDown
    def test_queue_execution_and_reload_without_audio(self):
        from h3chat.request_draft import load
        chat=self.app.store.create_chat()['id'];before=copy.deepcopy(self.app.store.settings())
        ident=self.app.send(chat,{'video':True,'assistant':False,'prompt':'Crea 3 scene da 20 secondi: un paesaggio al tramonto.','video_scene_count':1,'video_scene_seconds':15})['job_id']
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,));settings=json.loads(job['payload'])['settings']
        self.assertEqual(settings['_video_sequence']['duration'],60)
        media={'id':ident,'name':'video.mp4','path':f'outputs/{ident}/video.mp4','mime':'video/mp4','generation':{'duration':60}}
        with patch.object(self.app.engine,'generate_long_video',return_value=media) as long,patch.object(self.app.engine,'generate_video') as short:
            self.app.execute_job(job,threading.Event())
        self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done');long.assert_called_once();short.assert_not_called()
        request=self.app.store.chat(chat)['messages'][0]
        draft=load(self.app,chat,request['id'])
        self.assertEqual((draft['controls']['video_scene_count'],draft['controls']['video_scene_seconds']),(3,20))
        self.assertEqual(self.app.store.settings(),before)

    def test_resume_preserves_completed_clips_without_requiring_a_track(self):
        from h3chat.video_job_resume_render import render,CONTEXT_KEYS
        chat=self.app.store.create_chat()['id'];source='a'*32
        settings=apply(self.app.store.settings()|{'_assistant':False,'_video_scene_count':2,'_video_scene_seconds':15},'A landscape')
        timeline=scenes(settings);folder=self.app.data/'outputs'/source;folder.mkdir(parents=True)
        clip=folder/'first.mp4';clip.write_bytes(b'\x00\x00\x00\x18ftypisom')
        record={'timeline':timeline,'completed':1,'prompts':['A wide landscape.','Sunlight crosses the hills.'],'parameters':[{'duration':15}],
            'outputs':[clip.relative_to(self.app.data).as_posix()],'plan':{'prompt':'A landscape.','images':[],'audios':[]},'model':self.model['id'],
            'request_context':{'references':[],'settings':{k:v for k,v in settings.items() if k in CONTEXT_KEYS}}}
        (folder/'scenes.json').write_text(json.dumps(record))
        ident=self.app.send(chat,{'video':True,'assistant':False,'prompt':'A landscape'})['job_id'];job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,));payload=json.loads(job['payload'])
        media={'id':ident,'path':f'outputs/{ident}/video.mp4','mime':'video/mp4','generation':{'duration':30}}
        with patch.object(self.app.engine,'generate_long_video',return_value=media) as generate:
            render(self.app,job,payload,payload['settings']|{'_video_resume':source},threading.Event(),lambda _:None,folder/'engine.log')
        recovered=generate.call_args.args[1]
        self.assertEqual(recovered['_video_sequence']['count'],2);self.assertIsNone(recovered['_video_soundtrack'])
        self.assertTrue(clip.is_file())

    def test_new_timeline_exposes_generated_audio_for_later_editing(self):
        from h3chat.video_edit import source
        chat=self.app.store.create_chat()['id'];ident=self.app.send(chat,{'video':True,'assistant':False,'prompt':'2 scene da 15 secondi: un paesaggio.'})['job_id']
        folder=self.app.data/'outputs'/ident;folder.mkdir(parents=True);clip=folder/'first.mp4';clip.write_bytes(b'\x00\x00\x00\x18ftypisom')
        audio=folder/'native-audio.wav';audio.write_bytes(b'RIFFsynthetic')
        track={'id':'b'*32,'name':'Generated audio.wav','path':audio.relative_to(self.app.data).as_posix(),'mime':'audio/wav'}
        record={'timeline':[{'index':0,'start':0,'duration':15,'frames':360},{'index':1,'start':15,'duration':15,'frames':360}],
            'completed':2,'prompts':['Sunlight.','A garden.'],'parameters':[{},{}],'outputs':[clip.relative_to(self.app.data).as_posix()]*2,
            'plan':{'prompt':'A landscape.','images':[],'audios':[]},'model':self.model['id'],'generated_soundtrack':track}
        (folder/'scenes.json').write_text(json.dumps(record))
        self.app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(ident,))
        value=source(self.app,chat,ident)
        self.assertEqual(value['audio'],track);self.assertEqual(value['record']['plan']['audios'],[{'index':1,'role':'reuse','start':0}])
        self.assertEqual(json.loads((folder/'scenes.json').read_text())['plan']['audios'],[])

class NativeAudioMuxTests(unittest.TestCase):
    def test_native_audio_and_silent_gap_keep_scene_timing_on_cpu(self):
        import ast,math
        from fractions import Fraction
        import av,numpy as np
        path=Path(__file__).resolve().parents[1]/'native/media-compose-worker.py'
        tree=ast.parse(path.read_text(encoding='utf-8'))
        ns={'emit':lambda *a,**k:None,'math':math,'Fraction':Fraction,'Path':Path}
        for node in tree.body:
            if isinstance(node,ast.FunctionDef) and node.name in ('probe','compose'):exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);paths=[]
            for i,hz in enumerate((440,None,880)):
                target=folder/f'{i}.mp4';paths.append(str(target))
                with av.open(str(target),'w') as out:
                    video=out.add_stream('libx264',rate=24);video.width=64;video.height=64;video.pix_fmt='yuv420p'
                    if hz:sound=out.add_stream('aac',rate=48000);sound.layout='stereo'
                    for n in range(24):
                        frame=av.VideoFrame.from_ndarray(np.full((64,64,3),i*80,dtype=np.uint8),format='rgb24');frame.pts=n;frame.time_base=Fraction(1,24)
                        for packet in video.encode(frame):out.mux(packet)
                    for packet in video.encode(None):out.mux(packet)
                    if hz:
                        signal=(.2*np.sin(2*np.pi*hz*np.arange(48000)/48000)).astype(np.float32)
                        frame=av.AudioFrame.from_ndarray(np.stack([signal,signal]),format='fltp',layout='stereo');frame.sample_rate=48000;frame.pts=0;frame.time_base=Fraction(1,48000)
                        for packet in sound.encode(frame):out.mux(packet)
                        for packet in sound.encode(None):out.mux(packet)
            target=folder/'montage.mp4';result=ns['compose'](paths,None,str(target),clip_audio=True)
            self.assertEqual(result['frames'],72);self.assertEqual(result['duration'],3);self.assertTrue(result['clip_audio'])
            with av.open(str(target)) as source:self.assertEqual(sum(1 for _ in source.decode(video=0)),72)
            with av.open(str(target)) as source:audio=np.concatenate([f.to_ndarray() for f in source.decode(audio=0)],axis=1)
            rms=lambda a:float(np.sqrt(np.mean(a*a)))
            self.assertGreater(rms(audio[:,12000:36000]),.05);self.assertLess(rms(audio[:,60000:84000]),.001);self.assertGreater(rms(audio[:,108000:132000]),.05)
