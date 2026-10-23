import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from h3chat.video_engine import VideoEngine
from h3chat.video_batch import generate,register,memory_for,prompt_options,validate_count,journal
from h3chat.video_options import validate,capture_request,DEFAULTS
from h3chat.video_resume import checkpoint
from h3chat.downloads import Cancelled

MODEL={'id':'video-fixture'}
PLAN={'prompt':'One coherent scene','images':[],'audios':[]}
SCENE={'index':0,'start':0,'duration':5,'frames':120,'continuity':'cut','sequence':'fixture'}

class VideoBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.data=Path(self.tmp.name).resolve()
        self.e=VideoEngine();self.e.data=self.data;self.calls=[]
        self.settings={'video_overrides':{MODEL['id']:{'variants':3,'seed':42,'duration':5}}}
        def once(model,settings,plan,refs,job_id,cancel,stage,**kw):
            self.calls.append((copy.deepcopy(settings),copy.deepcopy(kw),job_id))
            p=self.data/'outputs'/job_id/'video.mp4';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'\0\0\0\x18ftypisomfixture')
            seed=settings['video_overrides'][model['id']].get('seed',-1)
            return {'id':job_id,'mime':'video/mp4','path':p.relative_to(self.data).as_posix(),'generation':{'seed':seed,'frames':120,'duration':5,'width':640,'height':360,'fps':24}}
        self.e._generate_video_once=Mock(side_effect=once)

    def render(self,ident='a'*32,scene=SCENE,settings=None,cancel=None):
        return self.e.generate_video(MODEL,settings or self.settings,PLAN,[],ident,cancel or threading.Event(),lambda _:None,scene=copy.deepcopy(scene))

    def test_three_complete_takes_have_distinct_seeds_paths_and_one_plan(self):
        before=copy.deepcopy(self.settings);item=self.render()
        self.assertEqual([v['generation']['seed'] for v in item['batch_variants']],[42,43,44])
        self.assertEqual(len({v['path'] for v in item['batch_variants']}),3)
        self.assertEqual([c[1]['scene']['frames'] for c in self.calls],[120]*3)
        self.assertEqual(self.settings,before)
        self.assertEqual(item['path'],item['batch_variants'][0]['path'])
        self.assertEqual(len(json.loads(journal(self.data,'a'*32).read_text())['items']),3)

    def test_single_take_keeps_existing_path_and_avoids_batch_journal(self):
        self.render(settings={'video_overrides':{MODEL['id']:{'variants':1}}})
        self.assertEqual(len(self.calls),1);self.assertFalse(journal(self.data,'a'*32).exists())

    def test_take_memory_is_explicit_and_not_the_previous_alternative(self):
        shared={'opening':'opening.mp4','recent':['previous.mp4']}
        self.render(scene=SCENE|{'index':1,'continuity':'continue','resume_memory':shared})
        scenes=[c[1]['scene'] for c in self.calls]
        self.assertEqual([s['resume_memory'] for s in scenes],[shared]*3)
        self.assertEqual(len({s['sequence'] for s in scenes}),3)
        self.assertTrue(all(s['continuity']=='continue' for s in scenes))

    def test_film_mode_restores_matching_branch_instead_of_primary(self):
        memories={str(i):{'opening':f'first-{i}.mp4','recent':[f'last-{i}.mp4']} for i in range(1,4)}
        self.render(scene=SCENE|{'index':2,'batch_memories':memories})
        self.assertEqual([c[1]['scene']['resume_memory'] for c in self.calls],[memories[str(i)] for i in range(1,4)])

    def test_cancel_and_resume_reuses_saved_take_with_no_second_generation(self):
        cancel=threading.Event();original=self.e._generate_video_once.side_effect
        def stop(*a,**kw):
            if self.e._generate_video_once.call_count==2:raise Cancelled()
            return original(*a,**kw)
        self.e._generate_video_once.side_effect=stop
        with self.assertRaises(Cancelled):self.render(cancel=cancel)
        self.assertEqual(len(json.loads(journal(self.data,'a'*32).read_text())['items']),1)
        self.e._generate_video_once=Mock(side_effect=original);self.calls=[]
        result=self.render(ident='b'*32,settings=self.settings|{'_video_resume':'a'*32})
        self.assertEqual(len(self.calls),2);self.assertEqual([v['generation']['seed'] for v in result['batch_variants']],[42,43,44])
        self.assertTrue(result['batch_variants'][0]['path'].startswith('outputs/'+'a'*32))
        self.assertEqual({v['generation']['variant_batch_id'] for v in result['batch_variants']},{'a'*32})

    def test_changed_recipe_cannot_silently_reuse_or_repeat_saved_takes(self):
        self.render();self.calls=[]
        with self.assertRaisesRegex(ValueError,'ricetta'):self.render(settings={'video_overrides':{MODEL['id']:{'variants':3,'seed':99,'duration':5}}})
        self.assertEqual(self.calls,[])

    def test_short_video_saves_resumable_checkpoint_before_alternatives_finish(self):
        original=self.e._generate_video_once.side_effect
        def stop(*a,**kw):
            if self.e._generate_video_once.call_count==2:raise Cancelled()
            return original(*a,**kw)
        self.e._generate_video_once.side_effect=stop
        with self.assertRaises(Cancelled):self.render(scene=None)
        saved=checkpoint(self.data,'a'*32)
        self.assertTrue(saved['batch_standalone']);self.assertEqual(saved['completed'],0);self.assertEqual(len(saved['batch_ready']),1)
        self.assertEqual(saved['request_context']['settings']['video_overrides'],self.settings['video_overrides'])

    def test_registration_keeps_all_takes_but_primary_selected_and_immutable(self):
        item=self.render();r={'timeline':[copy.deepcopy(SCENE)],'outputs':[item['path']],'parameters':[item['generation']],'prompts':['global prompt']}
        register(r,0,item,[])
        self.assertEqual(len(r['clip_versions'][0]),3);self.assertEqual(r['outputs'],[item['path']])
        self.assertEqual(r['selected_versions']['1'],r['clip_versions'][0][0]['id'])
        self.assertEqual([v['parameters']['seed'] for v in r['clip_versions'][0]],[42,43,44])
        item['batch_variants'][1]['generation']['seed']=999
        self.assertEqual(r['clip_versions'][0][1]['parameters']['seed'],43)

    def test_memory_modes_primary_and_branch_are_distinct(self):
        r={'timeline':[SCENE,SCENE|{'index':1,'continuity':'continue'}],'outputs':['primary.mp4','unused.mp4'],
           'clip_versions':[[{'output':'branch2.mp4','parameters':{'variant_index':2}}],[]]}
        self.assertEqual(memory_for(r,1,2,'clip',self.data)['recent'],[str(self.data/'primary.mp4')])
        self.assertEqual(memory_for(r,1,2,'video',self.data)['recent'],[str(self.data/'branch2.mp4')])

    def test_prompt_overrides_count_but_does_not_count_visual_cuts_or_dialogue(self):
        self.assertEqual(prompt_options('Crea tre varianti per ogni clip.'),{'variants':3,'variants_mode':'clip'})
        self.assertEqual(prompt_options('Crea 3 versioni dell’intero video.'),{'variants':3,'variants_mode':'video'})
        self.assertEqual(prompt_options('3 inquadrature e <d>[Italian] tre versioni</d>'),{})
        b={'video':True,'prompt':'3 varianti per clip','video_parameters':{'variants':2}}
        result=capture_request({'video_model':MODEL['id'],'video_overrides':{}},b,lambda *a:MODEL)
        self.assertEqual(result['video_overrides'][MODEL['id']]['variants'],3)
        for invalid in [True,0,9,1.5,'3']:
            with self.subTest(value=invalid),self.assertRaises(ValueError):validate_count(invalid)

    def test_long_film_generates_matching_branches_and_three_full_mounts(self):
        audio={'id':'track','mime':'audio/wav','path':'audio.wav'}
        plan=PLAN|{'audios':[{'index':1,'role':'lipsync','start':0}]}
        settings=self.settings|{'_video_duration':10,'_video_segment_seconds':5,'_video_soundtrack':audio,'_video_audio_source_duration':10,'_assistant':False}
        settings['video_overrides']=copy.deepcopy(settings['video_overrides']);settings['video_overrides'][MODEL['id']]['variants_mode']='video'
        self.e.scene_scripts=Mock(side_effect=AssertionError('No repeat planner'))
        def compose(engine,paths,audio,target,*a,**kw):target.write_bytes(b'\0\0\0\x18ftypisom');return {'duration':10}
        with patch('h3chat.soundtrack.compose',side_effect=compose) as mux:
            self.e.generate_long_video(MODEL,settings,plan,[audio],'a'*32,threading.Event(),lambda _:None,prompt='Original complete direction')
        self.assertEqual(len(self.calls),6);self.assertEqual(mux.call_count,3);self.e.scene_scripts.assert_not_called()
        r=checkpoint(self.data,'a'*32)
        self.assertEqual([len(x) for x in r['clip_versions']],[3,3]);self.assertEqual(len(r['batch_movies']),3)
        for i in range(3):
            expected=str(self.data/r['clip_versions'][0][i]['output'])
            self.assertEqual(self.calls[3+i][1]['scene']['resume_memory']['recent'],[expected])

    def test_long_resume_reuses_partial_batch_and_retains_branch_group(self):
        audio={'id':'track','mime':'audio/wav','path':'audio.wav'};plan=PLAN|{'audios':[{'index':1,'role':'lipsync','start':0}]}
        settings=self.settings|{'_video_duration':10,'_video_segment_seconds':5,'_video_soundtrack':audio,'_video_audio_source_duration':10,'_assistant':False}
        settings['video_overrides']=copy.deepcopy(settings['video_overrides']);settings['video_overrides'][MODEL['id']]['variants_mode']='video'
        original=self.e._generate_video_once.side_effect
        def stop(*a,**kw):
            if self.e._generate_video_once.call_count==5:raise Cancelled()
            return original(*a,**kw)
        self.e._generate_video_once.side_effect=stop
        with self.assertRaises(Cancelled):self.e.generate_long_video(MODEL,settings,plan,[audio],'a'*32,threading.Event(),lambda _:None,prompt='Original')
        self.assertEqual(checkpoint(self.data,'a'*32)['completed'],1)
        self.e._generate_video_once=Mock(side_effect=original);self.calls=[]
        def compose(engine,paths,audio,target,*a,**kw):target.write_bytes(b'\0\0\0\x18ftypisom');return {'duration':10}
        with patch('h3chat.soundtrack.compose',side_effect=compose):
            self.e.generate_long_video(MODEL,settings|{'_video_resume':'a'*32},plan,[audio],'b'*32,threading.Event(),lambda _:None,prompt='Original')
        self.assertEqual(len(self.calls),2)
        r=checkpoint(self.data,'b'*32);self.assertEqual(r['batch_id'],'a'*32)
        self.assertEqual([len(v) for v in r['clip_versions']],[3,3])
        self.assertEqual({v['parameters']['variant_batch_id'] for group in r['clip_versions'] for v in group},{'a'*32})

    def test_source_video_and_i2v_keyframe_are_passed_unchanged_to_all_takes(self):
        source={'path':'source.mp4','start':2,'frames':120,'megapixels':.35}
        self.render(scene=SCENE|{'source_video':source})
        self.assertTrue(all(c[1]['scene']['source_video']==source for c in self.calls))
        start={'id':'start','mime':'image/png','path':'start.png'}
        plan=PLAN|{'images':[{'index':1,'role':'keyframe','seconds':0}]}
        self.e.generate_video(MODEL,self.settings,plan,[start],'b'*32,threading.Event(),lambda _:None,scene=copy.deepcopy(SCENE))
        for call in self.e._generate_video_once.call_args_list[-3:]:
            self.assertEqual(call.args[2],plan);self.assertEqual(call.args[3],[start])

if __name__=='__main__':unittest.main()
