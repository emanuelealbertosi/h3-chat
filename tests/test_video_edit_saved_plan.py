import copy,json,threading,unittest
from unittest.mock import patch
from h3chat.video_edit import request
from h3chat.video_resume import checkpoint
import test_video_edit as fixture


class SavedEditPlanTests(unittest.TestCase):
    setUp=fixture.VideoEditTests.setUp
    tearDown=fixture.VideoEditTests.tearDown
    original=fixture.VideoEditTests.original

    def body(self,source):
        return {'source':source,'assistant':True,'remount':False,
            'patches':[{'clip':2,'mode':'video','prompt':'Replace the character','images':[2],'lip_sync':True}],
            'plans':{'2':{'prompt':'SOURCE VIDEO EDIT: Preserve <Video 1> motion; use <Picture 1>.',
                'images':[{'index':1,'role':'reference','seconds':0}],
                'audios':[{'index':1,'role':'lipsync','start':22}]}}}

    def test_saved_plan_reaches_generation_unchanged_and_is_snapshotted(self):
        chat,source,refs,outputs,params=self.original();body=self.body(source)
        expected=copy.deepcopy(body['plans']['2']);before=copy.deepcopy(self.app.store.settings())
        new=request(self.app,chat,body)['job_id']
        body['plans']['2']['prompt']='Changed after enqueue'
        def generate(model,settings,plan,selected,job,cancel,stage,**kwargs):
            self.assertEqual(plan,expected)
            self.assertEqual([r['id'] for r in selected],[refs[1]['id'],refs[2]['id']])
            self.assertEqual(kwargs['scene']['source_video']['path'],outputs[1])
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True)
            path.write_bytes(b'\0\0\0\x18ftypisomnew')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params|{'duration':15}}
        def mux(engine,clips,audio,target,*args,**kwargs):
            self.assertEqual(kwargs['audio_start'],22)
            target.write_bytes(b'\0\0\0\x18ftypisomnew');return {'duration':15}
        with patch.object(self.app.engine,'refine_video',side_effect=AssertionError('Must reuse saved directions')),patch.object(self.app.engine,'generate_video',side_effect=generate),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=mux):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(new,)),threading.Event())
        answer=self.app.store.chat(chat)['messages'][-1]
        self.assertEqual(answer['status'],'done',answer['meta'])
        self.assertEqual(checkpoint(self.app.data,new)['revision_plans']['2'],expected)
        self.assertEqual(self.app.store.settings(),before)

    def test_conflicting_refs_audio_and_unselected_plans_rejected_before_queue(self):
        chat,source,*_=self.original();before=len(self.app.store.all('SELECT id FROM jobs'))
        for change in ({'images':[]},{'images':[{'index':1,'role':'keyframe','seconds':0}]},
                       {'audios':[{'index':1,'role':'reuse','start':22}]},
                       {'audios':[{'index':1,'role':'lipsync','start':0}]},
                       {'prompt':'Use <Picture 2>'}):
            body=self.body(source);body['plans']['2'].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):request(self.app,chat,body)
        body=self.body(source);body['plans']['1']=body['plans'].pop('2')
        with self.assertRaises(ValueError):request(self.app,chat,body)
        body=self.body(source);body['patches'][0]['auto_anchors']=True
        with self.assertRaises(ValueError):request(self.app,chat,body)
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),before)


if __name__=='__main__':unittest.main()
