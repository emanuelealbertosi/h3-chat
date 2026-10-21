import copy,json,threading,unittest
from pathlib import Path
from unittest.mock import patch
import test_video_edit as fixture
from h3chat.downloads import Cancelled
from h3chat.video_edit import request,describe
from h3chat.video_resume import checkpoint
from h3chat.video_guide_frames import sample_frames


class AutoGuideTests(unittest.TestCase):
    setUp=fixture.VideoEditTests.setUp
    tearDown=fixture.VideoEditTests.tearDown
    original=fixture.VideoEditTests.original

    def editor(self,max_refs=4):
        real=self.app.engine.require_model
        model={'id':'guide-editor','name':'Image editor fixture','architecture':'flux2',
               'capabilities':['edit'],'max_refs':max_refs,'sampler':'euler','scheduler':'simple'}
        return patch.object(self.app.engine,'require_model',side_effect=lambda ident,kind:model if ident=='guide-editor' and kind=='edit' else real(ident,kind))

    def workers(self,params,events,*,interrupt=False):
        def tool(worker,body,*args,**kw):
            if body.get('op')=='extract_guides':
                events.append(('extract',body['start'],body['positions']))
                folder=Path(body['folder']);folder.mkdir(parents=True,exist_ok=True)
                result={}
                for point,frame in body['positions'].items():
                    path=folder/(point+'.png');path.write_bytes(b'\x89PNG\r\n\x1a\noriginal')
                    result[point]={'id':str(frame+1).zfill(32),'path':str(path),'frame':frame,'width':640,'height':360}
                return result
            if 'start_frame' in body:
                Path(body['output']).write_bytes(b'\0\0\0\x18ftypisommerged');return {'frames':360}
            raise AssertionError(body)
        def image(model,settings,prompt,refs,ident,cancel,stage):
            events.append(('image',ident,[r['id'] for r in refs],prompt))
            if interrupt and sum(e[0]=='image' for e in events)==2:raise Cancelled()
            path=self.app.data/'outputs'/ident/'image.png';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\x89PNG\r\n\x1a\nchanged')
            return {'id':ident,'path':path.relative_to(self.app.data).as_posix(),'name':'image.png','mime':'image/png','generation':{'steps':8}}
        def video(model,settings,plan,refs,ident,cancel,stage,**kw):
            events.append(('video',plan,refs,kw['scene']))
            path=self.app.data/'outputs'/ident/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\0\0\0\x18ftypisomvideo')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params|{'duration':kw['scene']['duration']}}
        def compose(engine,clips,audio,target,*args,**kw):
            target.write_bytes(b'\0\0\0\x18ftypisomfinal');return {'duration':kw['audio_duration']}
        return tool,image,video,compose

    def test_guides_batch_before_video_exact_partial_times_and_gallery(self):
        chat,source,refs,outputs,params=self.original();settings=copy.deepcopy(self.app.store.settings());events=[]
        tool,image,video,compose=self.workers(params,events)
        with self.editor(),patch.object(self.app.engine,'tool_call',side_effect=tool),patch.object(self.app.engine,'generate',side_effect=image),patch.object(self.app.engine,'generate_video',side_effect=video),patch.object(self.app.engine,'stop',side_effect=lambda:events.append(('stop',))),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=compose):
            ident=request(self.app,chat,{'source':source,'assistant':False,'remount':False,'patches':[
                {'clip':2,'start':2,'end':8,'mode':'video','auto_anchors':True,'anchor_edit_model':'guide-editor','prompt':'Replace clothing; use <Picture 1>','images':[1]},
                {'clip':3,'mode':'video','auto_anchors':True,'anchor_edit_model':'guide-editor','prompt':'Change the jacket'}]})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        answer=self.app.store.chat(chat)['messages'][-1];self.assertEqual(answer['status'],'done',answer['meta'])
        self.assertEqual(sum(e[0]=='image' for e in events),6)
        last_image=max(i for i,e in enumerate(events) if e[0]=='image');first_video=next(i for i,e in enumerate(events) if e[0]=='video')
        self.assertLess(last_image,first_video);self.assertEqual(events[first_video-1][0],'stop')
        self.assertEqual(events[0],('extract',2,{'first':0,'middle':72,'last':143}))
        plan=next(e for e in events if e[0]=='video')[1]
        self.assertEqual([r['seconds'] for r in plan['images'] if r['role']=='keyframe'],[0,3,143/24])
        saved=checkpoint(self.app.data,ident);self.assertTrue(saved['revision_request'][0]['auto_anchors'])
        self.assertNotIn('auto_anchors',saved['revision_resolved_request'][0])
        guides=saved['revision_auto_guides']['2']['images'];self.assertEqual(set(guides),{'first','middle','last'})
        for asset in guides.values():self.assertEqual(self.app.store.gallery.get(asset['id'])['path'],asset['path'])
        self.assertEqual(len(describe(self.app,chat,ident)['images']),8)
        self.assertEqual(self.app.store.settings(),settings)

    def test_resume_reuses_successful_guide_and_regenerates_only_missing(self):
        chat,source,refs,outputs,params=self.original();events=[]
        tool,image,video,compose=self.workers(params,events,interrupt=True)
        with self.editor(),patch.object(self.app.engine,'tool_call',side_effect=tool),patch.object(self.app.engine,'generate',side_effect=image),patch.object(self.app.engine,'generate_video',side_effect=video),patch.object(self.app.engine,'stop'),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=compose):
            ident=request(self.app,chat,{'source':source,'assistant':False,'remount':False,'patches':[{'clip':2,'mode':'video','auto_anchors':True,'anchor_edit_model':'guide-editor','prompt':'Change only the jacket'}]})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
            original=checkpoint(self.app.data,ident)['revision_auto_guides']['2']['images']['first']
            resumed=self.app.regenerate(chat)['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(resumed,)),threading.Event())
        self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
        generated=checkpoint(self.app.data,resumed)['revision_auto_guides']['2']['images']
        self.assertEqual(generated['first']['id'],original['id']);self.assertEqual(sum(e[0]=='extract' for e in events),1)
        self.assertEqual(sum(e[0]=='image' for e in events),4) # Three successful images plus the interrupted attempt.
        self.assertEqual(sum(e[0]=='video' for e in events),1)

    def test_invalid_options_and_model_ref_limit_fail_before_queue(self):
        chat,source,*_=self.original();base={'clip':1,'mode':'video','auto_anchors':True,'anchor_edit_model':'guide-editor','prompt':'Change jacket'}
        with self.editor(max_refs=1):
            for bad in ({'auto_anchors':'yes'},{'mode':'reference'},{'anchors':'none'},{'anchor_images':{'first':1}},{'images':[1]}):
                with self.subTest(bad=bad),self.assertRaises(ValueError):request(self.app,chat,{'source':source,'assistant':False,'patches':[base|bad]})
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),1)


class FrameTimingTests(unittest.TestCase):
    def test_samples_exact_start_middle_end_from_60fps_source(self):
        frames=list(range(21000))
        sampled=list(sample_frames(frames,start=315,count=360,positions={'first':0,'middle':180,'last':359},time_of=lambda f:f/60))
        self.assertEqual([(point,frame) for point,index,frame in sampled],[('first',18900),('middle',19350),('last',19797)])
    def test_missing_tail_is_an_error(self):
        with self.assertRaises(ValueError):list(sample_frames(range(60),start=0,count=360,positions={'first':0,'last':359},time_of=lambda f:f/24))

if __name__=='__main__':unittest.main()
