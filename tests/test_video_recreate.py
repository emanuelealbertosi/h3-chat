import copy,json,threading,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.video_recreate import describe,request,load
from h3chat.video_resume import checkpoint,save
from h3chat.video_options import options
import test_video_edit as fixture


class VideoRecreateTests(unittest.TestCase):
    setUp=fixture.VideoEditTests.setUp
    tearDown=fixture.VideoEditTests.tearDown
    original=fixture.VideoEditTests.original

    def test_experimental_canvas_and_model_choices_do_not_change_presets(self):
        chat,ident,refs,outputs,p=self.film();before=copy.deepcopy(self.app.store.settings())
        manifest=describe(self.app,chat,ident)
        self.assertEqual(manifest['model_id'],self.model['id'])
        self.assertIn(self.model['id'],[m['id'] for m in manifest['models']])
        new=request(self.app,chat,{'source':ident,'model':self.model['id'],
            'parameters':{'megapixels':1.5,'experimental_resolution':True,'steps':12}})['job_id'];calls=[]
        with patch.object(self.app.engine,'generate_video',side_effect=self.renderer(calls)),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',return_value={'duration':42}):self.execute(new)
        self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
        for _,_,opts,scene in calls:
            self.assertEqual(opts['megapixels'],1.5)
            self.assertGreater(scene['canvas']['width']*scene['canvas']['height'],1344*768)
        self.assertEqual(self.app.store.settings(),before)

    def film(self):
        chat,ident,refs,outputs,p= self.original()
        record=checkpoint(self.app.data,ident)
        for i,s in enumerate(record['timeline']):
            s.update(images=[{'index':2 if i==1 else 1,'role':'reference'}],lip_sync=i==1)
            params=p|{'duration':s['duration'],'megapixels':.7,'seed':100+i,'engine':'minimax-h3'}
            record['parameters'][i]=params
            plan={'prompt':f'Exact LOCAL direction {i+1} with <Picture 1>.',
                'images':[{'index':1,'role':'keyframe' if i==2 else 'reference','seconds':0}],
                'audios':[{'index':1,'role':'lipsync' if i==1 else 'reuse','start':7+s['start']}]}
            path=self.app.data/outputs[i];(path.parent/'video-plan.json').write_text(json.dumps({'plan':plan,'parameters':params}))
        save(self.app.data/'outputs'/ident,record)
        return chat,ident,refs,outputs,p

    def renderer(self,calls,fail=None):
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            if fail is not None and len(calls)==fail:raise RuntimeError('Synthetic interruption')
            opts=options(model,settings,False);scene=copy.deepcopy(kw['scene'])
            calls.append((copy.deepcopy(plan),copy.deepcopy(refs),opts,scene))
            out=self.app.data/'outputs'/job/'video.mp4';out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(b'\0\0\0\x18ftypisomnew')
            canvas=scene['canvas'];params=opts|{'duration':scene['duration'],'width':canvas['output_width'],'height':canvas['output_height'],
                'canvas_width':canvas['width'],'canvas_height':canvas['height'],'aspect':canvas['aspect'],'engine':'minimax-h3'}
            return {'path':out.relative_to(self.app.data).as_posix(),'generation':params}
        return generate

    def execute(self,ident):self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())

    def test_exact_per_clip_plans_and_assets_are_replayed_with_new_resolution(self):
        chat,original,refs,outputs,p=self.film();before=copy.deepcopy(self.app.store.settings());source_bytes=(self.app.data/'outputs'/original/'scenes.json').read_bytes()
        manifest=describe(self.app,chat,original)
        self.assertEqual((manifest['clips'],manifest['audio'],manifest['aspect']),(3,'song.wav','16:9'))
        self.assertNotIn('settings',manifest);self.assertNotIn('uploads/',json.dumps(manifest))
        new=request(self.app,chat,{'source':original,'parameters':{'megapixels':1,'steps':20}})['job_id'];calls=[]
        with patch.object(self.app.engine,'generate_video',side_effect=self.renderer(calls)),patch.object(self.app.engine,'refine_video') as planner,patch.object(self.app.knowledge,'retrieve') as rag,patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',return_value={'duration':42}) as mux:
            self.execute(new)
        answer=self.app.store.chat(chat)['messages'][-1];self.assertEqual(answer['status'],'done',answer['meta'])
        self.assertEqual(len(calls),3);planner.assert_not_called();rag.assert_not_called()
        self.assertEqual([c[0]['prompt'] for c in calls],manifest['directions'] and [d['prompt'] for d in manifest['directions']])
        self.assertEqual([c[1][0]['id'] for c in calls],[refs[0]['id'],refs[1]['id'],refs[0]['id']])
        self.assertEqual([c[0]['audios'][0]['start'] for c in calls],[7,22,37])
        self.assertEqual([c[0]['audios'][0]['role'] for c in calls],['reuse','lipsync','reuse'])
        self.assertEqual(calls[2][0]['images'][0]['role'],'keyframe')
        self.assertEqual([c[2]['seed'] for c in calls],[100,101,102])
        self.assertTrue(all(c[2]['megapixels']==.98 and c[2]['steps']==20 for c in calls))
        self.assertEqual([c[3]['frames'] for c in calls],[360,360,288])
        self.assertEqual((calls[0][3]['canvas']['output_width'],calls[0][3]['canvas']['output_height']),(1344,756))
        self.assertEqual((calls[0][3]['canvas']['width'],calls[0][3]['canvas']['height']),(1344,768))
        self.assertEqual(mux.call_args.kwargs,{'audio_start':7,'audio_duration':42})
        self.assertEqual(self.app.store.settings(),before);self.assertEqual((self.app.data/'outputs'/original/'scenes.json').read_bytes(),source_bytes)
        # New video retains a recipe even when no legacy per-clip plan is written by the mocked renderer.
        replay=load(self.app,chat,new);self.assertEqual(replay['recipes'][1]['plan'],calls[1][0])

    def test_invalid_requests_and_user_queue_are_enforced(self):
        chat,original,*_=self.film()
        for parameters in ({'megapixels':1.1},{'steps':True},{'seed':False},{'duration':30},{'aspect':'9:16'},{'steps':0},{'offload':'yes'},{'cfg':float('nan')}):
            with self.subTest(parameters=parameters),self.assertRaises(ValueError):request(self.app,chat,{'source':original,'parameters':parameters})
        self.assertEqual(len(self.app.store.all('SELECT * FROM jobs')),1)
        request(self.app,chat,{'source':original,'parameters':{}})
        with self.assertRaisesRegex(ValueError,'richiesta attiva'):request(self.app,chat,{'source':original,'parameters':{}})

    def test_different_checkpoint_preserves_the_exact_recipe_and_preferences(self):
        chat,original,*_=self.film()
        alternate=copy.deepcopy(self.model);alternate.update(id='alternate-h3',name='Alternate H3')
        self.app.catalog[alternate['id']]=alternate
        self.app.store.save_settings({'video_overrides':{'alternate-h3':{'attention':'veda','attention_chunks':8,'veda_sparsity':90,'veda_reference_sparsity':0}}})
        before=copy.deepcopy(self.app.store.settings())
        new=request(self.app,chat,{'source':original,'model':alternate['id'],'parameters':{'steps':20}})['job_id']
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(new,));payload=json.loads(job['payload'])
        self.assertEqual(payload['settings']['video_model'],'alternate-h3')
        calls=[]
        with patch.object(self.app.engine,'generate_video',side_effect=self.renderer(calls)),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',return_value={'duration':42}):self.execute(new)
        answer=self.app.store.chat(chat)['messages'][-1]
        self.assertEqual(answer['status'],'done',answer['meta'])
        self.assertEqual(answer['meta']['model'],'Alternate H3')
        self.assertEqual(len(calls),3)
        self.assertTrue(all(c[2]['steps']==20 for c in calls))
        self.assertTrue(all(c[2]['attention']=='veda' and c[2]['attention_chunks']==8 and c[2]['veda_reference_sparsity']==0 for c in calls))
        self.assertEqual(self.app.store.settings(),before)

    def test_cross_chat_gallery_reuse_is_workspace_scoped(self):
        chat,original,*_=self.film();other=self.app.store.create_chat()['id']
        self.assertEqual(describe(self.app,other,original)['source'],original)
        for ident in ('../'+original,'0'*32):
            with self.assertRaises(ValueError):describe(self.app,chat,ident)
        self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(original,))
        with self.assertRaises(ValueError):describe(self.app,chat,original)

    def test_missing_assets_fail_before_enqueue(self):
        chat,original,refs,*_=self.film();(self.app.data/refs[0]['path']).unlink()
        with self.assertRaisesRegex(ValueError,'riferimento'):request(self.app,chat,{'source':original})
        self.assertEqual(len(self.app.store.all('SELECT * FROM jobs')),1)

    def test_postedited_actual_direction_is_kept_instead_of_modification_request(self):
        chat,original,*_=self.film()
        record=checkpoint(self.app.data,original);plan_path=self.app.data/record['outputs'][1]
        value=json.loads((plan_path.parent/'video-plan.json').read_text());value['plan']['prompt']='New medium two-shot <Picture 1>, rotating camera.'
        (plan_path.parent/'video-plan.json').write_text(json.dumps(value))
        record.update(revision_completed=[2],revision_plans={'2':value['plan']});save(self.app.data/'outputs'/original,record)
        self.assertEqual(describe(self.app,chat,original)['directions'][1]['prompt'],value['plan']['prompt'])

    def test_cancelled_recreation_resumes_saved_clips(self):
        chat,original,*_=self.film();new=request(self.app,chat,{'source':original,'parameters':{'steps':16}})['job_id'];calls=[]
        with patch.object(self.app.engine,'generate_video',side_effect=self.renderer(calls,fail=1)),patch('h3chat.soundtrack.probe',return_value={'duration':60}):self.execute(new)
        self.assertEqual(checkpoint(self.app.data,new)['completed'],1)
        retry=self.app.regenerate(chat)['job_id']
        with patch.object(self.app.engine,'generate_video',side_effect=self.renderer(calls)),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',return_value={'duration':42}):self.execute(retry)
        self.assertEqual(len(calls),3);self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
        self.assertEqual(checkpoint(self.app.data,retry)['outputs'][0],checkpoint(self.app.data,new)['outputs'][0])

    def test_interval_edit_recovers_combined_direction_and_old_and_new_images(self):
        chat,original,*_=self.film();record=checkpoint(self.app.data,original)
        record['parameters'][1]['post_edit_interval']={'start':4,'end':9}
        record['prompts'][1]='Old hero <Picture 1>.\nUPDATED INTERVAL 4–9: cabin <Picture 2>.'
        record['timeline'][1]['images']=[{'index':2,'role':'reference'}]
        save(self.app.data/'outputs'/original,record)
        value=load(self.app,chat,original);self.assertTrue(value['partial'])
        recipe=value['recipes'][1]
        self.assertEqual(len([x for x in recipe['refs'] if x['mime'].startswith('image/')]),2)
        self.assertIn('Old hero <Picture 1>',recipe['plan']['prompt']);self.assertIn('cabin <Picture 2>',recipe['plan']['prompt'])
        self.assertEqual(recipe['plan']['audios'][0]['start'],22)

    def test_single_generated_video_without_music_reuses_saved_plan(self):
        chat,original,refs,*_=self.film();folder=self.app.data/'outputs'/original
        record=checkpoint(self.app.data,original);(folder/'scenes.json').unlink()
        value=json.loads((self.app.data/record['outputs'][0]).with_name('video-plan.json').read_text());value['plan']['audios']=[]
        value['parameters']['frames']=360;(folder/'video-plan.json').write_text(json.dumps(value));(folder/'video.mp4').write_bytes(b'\0\0\0\x18ftypisom')
        row=self.app.store.one('SELECT j.message_id,m.meta,j.payload FROM jobs j JOIN messages m ON m.id=j.message_id WHERE j.id=?',(original,))
        meta=json.loads(row['meta']);meta['references']=[refs[0]];meta['video_parameters']['duration']=15
        payload=json.loads(row['payload']);payload['media']=[refs[0]]
        self.app.store.execute('UPDATE messages SET meta=? WHERE id=?',(json.dumps(meta),row['message_id']))
        self.app.store.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(payload),original))
        manifest=describe(self.app,chat,original);self.assertEqual(manifest['clips'],1);self.assertIsNone(manifest['audio'])
        new=request(self.app,chat,{'source':original})['job_id'];calls=[]
        with patch.object(self.app.engine,'generate_video',side_effect=self.renderer(calls)),patch('h3chat.soundtrack.compose') as mux:self.execute(new)
        self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done');mux.assert_not_called()


if __name__=='__main__':unittest.main()
