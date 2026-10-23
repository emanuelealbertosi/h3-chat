import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.video_edit import source,describe
from h3chat.video_editor_drafts import save,load,remove,signature
import test_video_edit as fixture


class EditorDraftTests(unittest.TestCase):
    setUp=fixture.VideoEditTests.setUp
    tearDown=fixture.VideoEditTests.tearDown
    original=fixture.VideoEditTests.original

    def test_memory_and_final_frame_choices_survive_draft_reload(self):
        chat,ident,*_=self.original();body=self.editor(chat,ident)
        body['state']['clips'][1].update(recover_memory=True,end_frame=2)
        saved=save(self.app,chat,ident,body)
        loaded=load(self.app,chat,ident,source(self.app,chat,ident))
        self.assertTrue(loaded['state']['clips'][1]['recover_memory'])
        self.assertEqual(loaded['state']['clips'][1]['end_frame'],2)
        for value in (True,999,'C:/unowned.png'):
            bad=copy.deepcopy(body);bad['state']['clips'][1]['end_frame']=value
            with self.subTest(value=value),self.assertRaises(ValueError):save(self.app,chat,ident,bad)
        self.assertEqual(load(self.app,chat,ident,source(self.app,chat,ident))['state'],saved['state'])

    def editor(self,chat,ident):
        manifest=describe(self.app,chat,ident)
        state={'signature':[[round(c['start']*24),round((c['end']-c['start'])*24)] for c in manifest['clips']],
            'model':manifest['model_id'],'parameters':{'attention':'veda','seed':0},
            'values':{'megapixels':'0.98','video_steps':'16','reference_megapixels':'0.2','assistant':False,'remount':False},
            'active':2,'common_prompt':'Red jacket for <Picture 1>','image_ids':[i['id'] for i in manifest['images']],
            'versions':{str(c['clip']):c['selected_version'] for c in manifest['clips']},'clips':[]}
        for c in manifest['clips']:
            frames=round((c['end']-c['start'])*24)
            state['clips'].append({'enabled':c['clip']==2,'clip':c['clip'],'prompt':'' if c['clip']!=2 else 'A red jacket <Picture 1>',
                'images':[1] if c['clip']==2 else [],'lip_sync':True,'range':c['clip']==2,'first':48 if c['clip']==2 else 0,'last':144 if c['clip']==2 else frames,
                'frames':frames,'mode':'video','anchors':'three' if c['clip']==2 else 'none','anchor_image':None,'start_image':None,
                'auto_anchors':False,'anchor_edit_model':'','anchor_images':{'first':1,'last':2} if c['clip']==2 else {}})
        return {'state':state,'segment_seconds':None}

    def test_save_reload_during_other_job_changes_no_jobs_presets_or_source(self):
        chat,ident,*_=self.original();body=self.editor(chat,ident)
        another=self.app.store.create_chat()['id'];job=self.app.store.enqueue(another,'In flight',[],self.app.store.settings())
        self.app.store.execute("UPDATE jobs SET status='running' WHERE id=?",(job,))
        jobs=self.app.store.all('SELECT * FROM jobs');settings=self.app.store.settings()
        original=(self.app.data/'outputs'/ident/'scenes.json').read_bytes()
        saved=save(self.app,chat,ident,body)
        body['state']['clips'][1]['prompt']='Unsaved changes'
        loaded=describe(self.app,chat,ident)['editor_draft']
        self.assertEqual(loaded['state'],saved['state']);self.assertEqual(loaded['state']['clips'][1]['first'],48)
        self.assertEqual(loaded['state']['parameters']['seed'],0)
        self.assertEqual([r['id'] for r in loaded['image_refs']],saved['state']['image_ids'])
        self.assertEqual(self.app.store.all('SELECT * FROM jobs'),jobs);self.assertEqual(self.app.store.settings(),settings)
        self.assertEqual((self.app.data/'outputs'/ident/'scenes.json').read_bytes(),original)

    def test_other_chat_source_versions_and_unowned_media_cannot_be_substituted(self):
        chat,ident,*_=self.original();body=self.editor(chat,ident);save(self.app,chat,ident,body)
        other=self.app.store.create_chat()['id']
        with self.assertRaises(ValueError):save(self.app,other,ident,body)
        for changed in ('signature','versions','images','extra','range'):
            bad=copy.deepcopy(body)
            if changed=='signature':bad['state']['signature'][0][1]-=1
            elif changed=='versions':bad['state']['versions']['2']='other-video-version'
            elif changed=='images':bad['state']['clips'][1]['images']=[900]
            elif changed=='extra':bad['state']['image_ids'].append('f'*32)
            else:bad['state']['clips'][1]['last']=9999
            with self.subTest(changed=changed),self.assertRaises(ValueError):save(self.app,chat,ident,bad)
        self.assertEqual(load(self.app,chat,ident,source(self.app,chat,ident))['state'],body['state'])

    def test_removing_draft_does_not_remove_video_or_other_chat_draft(self):
        chat,ident,*_=self.original();other,other_id,*_=self.original()
        save(self.app,chat,ident,self.editor(chat,ident));save(self.app,other,other_id,self.editor(other,other_id))
        remove(self.app,chat,ident,{'segment_seconds':None})
        self.assertIsNone(describe(self.app,chat,ident)['editor_draft'])
        self.assertIsNotNone(describe(self.app,other,other_id)['editor_draft'])
        self.assertTrue((self.app.data/'outputs'/ident/'scenes.json').exists())

    def test_atomic_write_failure_retains_last_saved_draft(self):
        chat,ident,*_=self.original();body=self.editor(chat,ident);save(self.app,chat,ident,body)
        changed=copy.deepcopy(body);changed['state']['common_prompt']='New settings'
        with patch.object(Path,'replace',side_effect=OSError('Synthetic write failure')):
            with self.assertRaises(OSError):save(self.app,chat,ident,changed)
        self.assertEqual(load(self.app,chat,ident,source(self.app,chat,ident))['state'],body['state'])
        self.assertEqual(list((self.app.data/'video-editor-drafts').rglob('*.tmp')),[])

    def test_invalid_media_path_is_rejected_before_media_lookup(self):
        chat,ident,*_=self.original();body=self.editor(chat,ident)
        body['state']['image_ids'].append('../../private')
        with patch.object(self.app,'validate_media') as lookup:
            with self.assertRaisesRegex(ValueError,'Identificativo immagine'):save(self.app,chat,ident,body)
        lookup.assert_not_called()

    def test_per_clip_launches_are_saved_independently_and_validated(self):
        chat,ident,*_=self.original();body=self.editor(chat,ident)
        body['state']['clip_launches']={str(n):{'model':self.model['id'],'parameters':{'seed':n*10,'megapixels':mp},
            'steps':12,'assistant':False,'saved_at':123,'reference_megapixels':.2} for n,mp in ((2,.7),(3,.98))}
        save(self.app,chat,ident,body)
        body['state']['clip_launches']['2']['parameters']['seed']=999
        launches=describe(self.app,chat,ident)['editor_draft']['state']['clip_launches']
        self.assertEqual(launches['2']['parameters']['seed'],20);self.assertEqual(launches['3']['parameters']['seed'],30)
        bad=copy.deepcopy(body);bad['state']['clip_launches']['4']=bad['state']['clip_launches'].pop('2')
        with self.assertRaises(ValueError):save(self.app,chat,ident,bad)
