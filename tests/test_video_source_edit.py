import copy,json,threading,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.video_edit import request,source,source_interval,validate_edits
from h3chat.video_options import validate_plan
from h3chat.video_reference import validate_source,reference_shape,video_block,anchor_positions,source_still
from h3chat.video_resume import checkpoint
import test_video_edit as fixture


class SourceEditTests(unittest.TestCase):
    setUp=fixture.VideoEditTests.setUp
    tearDown=fixture.VideoEditTests.tearDown
    original=fixture.VideoEditTests.original

    def test_selected_movie_interval_reaches_sampler_and_retains_audio(self):
        chat,original,refs,outputs,params=self.original();before=copy.deepcopy(self.app.store.settings());calls=[]
        ident=request(self.app,chat,{'source':original,'assistant':False,'remount':False,'patches':[
            {'clip':2,'mode':'video','prompt':'Change only the jacket to red','start':4,'end':9,'images':[]}]})['job_id']
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            self.assertEqual(len(refs),1);self.assertTrue(refs[0]['mime'].startswith('audio/'))
            self.assertIn('<Video 1>',plan['prompt']);self.assertIn('jacket',plan['prompt'])
            self.assertEqual(plan['images'],[]);self.assertEqual(plan['audios'][0]['start'],26)
            guide=kw['scene']['source_video'];self.assertEqual(guide,{'path':outputs[1],'start':4,'frames':120,'megapixels':.35})
            calls.append(guide)
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True)
            path.write_bytes(b'\0\0\0\x18ftypisomnew')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params|{'duration':5,'source_video_recipe':guide}}
        def mux(engine,clips,audio,target,*args,**kw):
            self.assertEqual((kw['audio_start'],kw['audio_duration']),(26,5))
            target.write_bytes(b'\0\0\0\x18ftypisomnew');return {'duration':5}
        def splice(worker,body,*args,**kw):
            self.assertEqual(body['original'],str(self.app.data/outputs[1]))
            Path(body['output']).write_bytes(b'\0\0\0\x18ftypisommerged');return {'frames':360}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch.object(self.app.engine,'tool_call',side_effect=splice),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=mux):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        answer=self.app.store.chat(chat)['messages'][-1]
        self.assertEqual(answer['status'],'done',answer['meta']);self.assertEqual(len(calls),1)
        self.assertEqual(answer['media'][0]['generation']['source_video_recipe'],calls[0])
        self.assertEqual(self.app.store.settings(),before)

    def test_references_are_optional_and_a_replacement_image_stays_a_reference(self):
        chat,original,*_=self.original();value=source(self.app,chat,original)
        patches=validate_edits([{'clip':1,'mode':'video','prompt':'Replace the actor with <Picture 1>','images':[1]}],value)
        self.assertEqual((patches[0]['mode'],patches[0]['images']),('video',[1]))
        self.assertEqual(validate_edits([{'clip':1,'mode':'video','prompt':'Change background'}],value)[0]['images'],[])
        for bad in ({'mode':'video','reference_megapixels':True},{'mode':'video','reference_megapixels':2},{'mode':'reference','reference_megapixels':.3},{'mode':'video','prompt':'Use <Video 2>'}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):validate_edits([{'clip':1,'prompt':'Change'}|bad],value)

    def test_external_interval_uses_original_movie_and_global_offset(self):
        chat,original,*_=self.original();value=source(self.app,chat,original)
        value['imported']={'path':'uploads/external.mp4'}
        guide=source_interval(value,{'clip':2,'start':4,'end':9,'reference_megapixels':.5})
        self.assertEqual(guide,{'path':'uploads/external.mp4','start':19,'frames':120,'megapixels':.5})

    def test_video_labels_cannot_silently_be_used_without_source(self):
        plan={'prompt':'Edit <Video 1>','images':[],'audios':[]}
        with self.assertRaisesRegex(ValueError,'Video'):validate_plan(plan,[],5)
        self.assertEqual(validate_plan(plan,[],5,source_video=True)['prompt'],plan['prompt'])
        with self.assertRaises(ValueError):validate_plan(plan|{'prompt':'Edit <Video 2>'},[],5,source_video=True)

    def test_source_bounds_and_shape(self):
        for bad in ({'frames':361},{'frames':True},{'start':float('nan')},{'start':-1},{'path':''}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):validate_source({'path':'movie.mp4','start':0,'frames':360}|bad)
        w,h,cw,ch=reference_shape(1920,1080,.35)
        self.assertAlmostEqual(w/h,16/9,delta=.01);self.assertEqual((cw%32,ch%32),(0,0));self.assertLess(cw*ch,.4*1024**2)

    def test_validation_checks_selected_interval_not_the_whole_clip(self):
        value={'record':{'timeline':[{'frames':480,'duration':20,'images':[]}],'plan':{'images':[]}},'images':[]}
        patches=validate_edits([{'clip':1,'mode':'video','prompt':'Change only the outfit','start':2,'end':12}],value)
        self.assertEqual((patches[0]['start'],patches[0]['end']),(2,12))
        with self.assertRaisesRegex(ValueError,'Clip 1.*da 1 a 15'):
            validate_edits([{'clip':1,'mode':'video','prompt':'Change outfit'}],value)
        value['record']['timeline'][0]={'frames':20,'duration':20/24,'images':[]}
        with self.assertRaisesRegex(ValueError,'Clip 1.*0.833333'):
            validate_edits([{'clip':1,'mode':'video','prompt':'Change outfit'}],value)

    def test_common_character_edit_passes_each_actual_clip_and_only_selected_image(self):
        chat,original,refs,outputs,params=self.original();calls=[]
        prompt='Replace the woman with the adult anime character from <Picture 2>; keep her illustrated style and original motions.'
        ident=request(self.app,chat,{'source':original,'assistant':False,'remount':True,
            'patches':[{'clip':n,'mode':'video','prompt':prompt,'images':[2]} for n in (1,2,3)]})['job_id']
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            self.assertEqual([r['id'] for r in selected],[refs[1]['id'],refs[2]['id']])
            self.assertIn('anime character from <Picture 1>',plan['prompt'])
            self.assertEqual(plan['images'],[{'index':1,'role':'reference','seconds':0}])
            guide=kw['scene']['source_video'];calls.append(guide)
            self.assertEqual(guide['path'],outputs[len(calls)-1]);self.assertEqual(guide['start'],0)
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\0\0\0\x18ftypisom')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params|{'duration':kw['scene']['duration']}}
        def mux(engine,clips,audio,target,*args,**kw):
            self.assertEqual(len(clips),3);self.assertEqual(kw['audio_duration'],42)
            target.write_bytes(b'\0\0\0\x18ftypisom');return {'duration':42}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch.object(self.app.engine,'completion') as llm,patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=mux):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
        self.assertEqual([x['frames'] for x in calls],[360,360,288]);llm.assert_not_called()

    def test_anchors_use_interval_local_first_and_last_without_padding(self):
        self.assertEqual(anchor_positions({'frames':120}),[])
        self.assertEqual(anchor_positions({'frames':120,'anchors':'first'}),[0])
        self.assertEqual(anchor_positions({'frames':120,'anchors':'ends'}),[0,119])
        self.assertEqual(anchor_positions({'frames':360,'anchors':'three'}),[0,180,359])
        self.assertEqual(anchor_positions({'frames':121,'anchors':'three'}),[0,60,120])
        value={'path':'source.mp4','start':315,'frames':360,'megapixels':.2,'anchors':'ends'}
        self.assertEqual(validate_source(value),value)
        with self.assertRaises(ValueError):validate_source(value|{'anchors':'all'})
        from unittest.mock import MagicMock
        frames=MagicMock();source_still(frames,{'pad_left':3,'pad_top':4,'content_width':10,'content_height':12},7)
        frames.__getitem__.assert_called_once_with((slice(7,8),slice(4,16),slice(3,13)))

    def test_edited_first_frame_keeps_video_source_and_image_identity(self):
        chat,original,refs,outputs,params=self.original()
        ident=request(self.app,chat,{'source':original,'assistant':False,'remount':False,'patches':[
            {'clip':2,'mode':'video','prompt':'Use <Picture 2> as the edited first frame; follow <Video 1> motion',
             'anchors':'first','anchor_image':2,'images':[],'start':4,'end':9}]})['job_id']
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            self.assertEqual(plan['images'],[{'index':1,'role':'keyframe','seconds':0}])
            self.assertEqual(selected[0]['id'],refs[1]['id'])
            self.assertEqual(kw['scene']['source_video'],{'path':outputs[1],'start':4,'frames':120,'megapixels':.35,'anchors':'first'})
            self.assertIn('EDITED TARGET FIRST FRAME',plan['prompt'])
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True);path.write_bytes(b'\0\0\0\x18ftypisom')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params}
        def splice(worker,body,*args,**kw):
            Path(body['output']).write_bytes(b'\0\0\0\x18ftypisom');return {'frames':360}
        def mux(engine,clips,audio,target,*args,**kw):
            target.write_bytes(b'\0\0\0\x18ftypisom');return {'duration':kw['audio_duration']}
        with patch.object(self.app.engine,'generate_video',side_effect=generate) as gpu,patch.object(self.app.engine,'tool_call',side_effect=splice),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=mux):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        gpu.assert_called_once();self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
        value=source(self.app,chat,original)
        for extra in ({'mode':'reference','anchors':'first'},{'anchors':'first','anchor_image':True},{'anchors':'none','anchor_image':1}):
            with self.assertRaises(ValueError):validate_edits([{'clip':2,'mode':'video','prompt':'Change jacket'}|extra],value)

    def test_three_edited_guides_use_selected_interval_clocks_and_survive_replay(self):
        chat,original,refs,outputs,params=self.original()
        extra={'id':'4'*32,'name':'last.png','path':'uploads/last.png','mime':'image/png'}
        (self.app.data/extra['path']).write_bytes((self.app.data/refs[0]['path']).read_bytes())
        (self.app.data/'uploads'/(extra['id']+'.json')).write_text(json.dumps(extra))
        ident=request(self.app,chat,{'source':original,'assistant':False,'remount':False,'media':[extra],
            'patches':[{'clip':2,'mode':'video','prompt':'Change jacket, keep motion of <Video 1>',
                       'anchors':'three','anchor_images':{'first':2,'middle':1,'last':3},'start':4,'end':9}]})['job_id']
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            self.assertEqual([r['id'] for r in selected[:3]],[refs[1]['id'],refs[0]['id'],extra['id']])
            self.assertEqual(plan['images'],[{'index':1,'role':'keyframe','seconds':0},
                {'index':2,'role':'keyframe','seconds':2.5},{'index':3,'role':'keyframe','seconds':119/24}])
            self.assertEqual(kw['scene']['source_video']['anchors'],'three')
            self.assertEqual(kw['scene']['source_video']['frames'],120)
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True);path.write_bytes(b'\0\0\0\x18ftypisom')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params}
        def splice(worker,body,*args,**kw):
            Path(body['output']).write_bytes(b'\0\0\0\x18ftypisom');return {'frames':360}
        def mux(engine,clips,audio,target,*args,**kw):
            target.write_bytes(b'\0\0\0\x18ftypisom');return {'duration':kw['audio_duration']}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch.object(self.app.engine,'tool_call',side_effect=splice),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=mux):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        answer=self.app.store.chat(chat)['messages'][-1];self.assertEqual(answer['status'],'done',answer['meta'])
        scene=checkpoint(self.app.data,ident)['timeline'][1]
        self.assertEqual(scene['images'],[{'index':2,'role':'keyframe','seconds':4},
            {'index':1,'role':'keyframe','seconds':6.5},{'index':3,'role':'keyframe','seconds':4+119/24}])
        value=source(self.app,chat,original)
        for guides in ({'middle':1},{'first':True},{'first':1,'last':1},{'other':1}):
            with self.assertRaises(ValueError):validate_edits([{'clip':1,'mode':'video','prompt':'Change','anchors':'ends','anchor_images':guides}],value)

    def test_video_only_conditioning_has_the_packed_layout_audio_span(self):
        from types import SimpleNamespace
        latent=SimpleNamespace(shape=(1,24,12,24,40));block=video_block(latent)
        self.assertEqual((block['latent_t'],block['latent_h'],block['latent_w']),(12,24,40))
        self.assertEqual(block['ref_audio_t'],0);self.assertIsNone(block['audio_latent'])
        self.assertIs(block['latent'],latent)

    def test_recreation_keeps_the_source_video_recipe(self):
        from h3chat.video_recreate import load
        from h3chat.video_resume import save
        chat,original,refs,outputs,params=self.original();record=checkpoint(self.app.data,original)
        recipe={'path':outputs[1],'start':0,'frames':360,'megapixels':.35}
        record['timeline'][0]['generation_mode']='video';record['parameters'][0]=params|{'source_video_recipe':recipe}
        plan={'prompt':'Edit <Video 1> jacket from <Picture 1>','images':[{'index':1,'role':'reference','seconds':0}],'audios':[{'index':1,'role':'reuse','start':7}]}
        (self.app.data/outputs[0]).with_name('video-plan.json').write_text(json.dumps({'plan':plan}))
        record['revision_completed']=[1];record['revision_plans']={'1':plan};save(self.app.data/'outputs'/original,record)
        value=load(self.app,chat,original);self.assertEqual(value['recipes'][0]['source_video'],recipe)


if __name__=='__main__':unittest.main()
