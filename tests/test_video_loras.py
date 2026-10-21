import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
import test_video_edit as fixture
from test_loras_image_options import lora
from h3chat.video_loras import validate,aligned,prepare_plan
from h3chat.video_options import validate as video_options
from h3chat.loras import LoraLibrary
from h3chat.video_edit import request,describe

class VideoLoraTests(unittest.TestCase):
    setUp=fixture.VideoEditTests.setUp
    tearDown=fixture.VideoEditTests.tearDown
    original=fixture.VideoEditTests.original
    def test_assistant_receives_active_character_identity_without_guessing_franchise(self):
        from h3chat.video_loras import prompt_context
        self.assertEqual(prompt_context([]),'')
        self.assertEqual(prompt_context([{'path':'ignored.safetensors','weight':0}]),'')
        text=prompt_context([{'path':'F:/models/MM-H3 - Aunt Cass BH6 v1.01.safetensors','weight':1}])
        self.assertIn('Disney Big Hero 6',text)
        self.assertIn('not an elderly character from Cars',text)
        self.assertIn('Keep the source wardrobe',text)
    def adapter(self,name='minimax_h3_vfx_edit_ffp.safetensors'):
        return lora(self.folder/name,'minimax_h3_ref2va')
    def test_capture_refreshes_a_partial_cold_index_before_rejecting_selected_lora(self):
        path=self.adapter();lib=LoraLibrary();complete=lib.scan([str(self.folder)])
        item=complete['items'][0]
        with patch.object(lib,'scan',side_effect=[{'items':[],'truncated':True},complete]) as scan:
            captured=lib.capture([{'id':item['id'],'model_id':self.model['id'],'weight':1}],[str(self.folder)],{self.model['id']:self.model})
        self.assertEqual(captured[0]['id'],item['id']);self.assertEqual(scan.call_count,2)

    def test_shared_library_recognizes_h3_and_rejects_image_adapter(self):
        path=self.adapter();lib=LoraLibrary()
        models={self.model['id']:self.model}
        item=lib.scan([str(self.folder)])['items'][0]
        self.assertEqual(item['family'],'minimax-h3')
        self.assertEqual(lib.capture([{'id':item['id'],'model_id':self.model['id'],'weight':.8}],[str(self.folder)],models)[0]['weight'],.8)
        bad=lora(self.folder/'image.safetensors')
        with self.assertRaisesRegex(ValueError,'MiniMax H3'):validate([{'path':str(bad),'weight':1}])
    def test_adapter_selects_aligned_grid_and_pdd_accepts_editing_only(self):
        selected=[{'path':str(self.adapter()),'weight':1}]
        opts=video_options({'loras':selected})
        self.assertEqual(opts['source_conditioning'],'aligned')
        pdd={'pdd_enabled':True,'pdd_lora':str(self.folder/'MiniMax-H3-Ref2VA-Acc-8Step.safetensors'),'steps':8,'sampler':'euler'}
        with patch('h3chat.external_models.valid_weight',return_value=True),patch('h3chat.video_pdd.check_header'):
            combined=video_options({'loras':selected}|pdd)
            self.assertEqual(combined['source_conditioning'],'aligned')
            self.assertEqual(combined['loras'],opts['loras'])
            turbo={'path':str(self.adapter('minimax_h3_dmd_turbo.safetensors')),'weight':1}
            with self.assertRaisesRegex(ValueError,'DMD, Turbo'):video_options({'loras':selected+[turbo]}|pdd)
            self.assertTrue(video_options({'loras':selected+[dict(turbo,weight=0)]}|pdd)['pdd_enabled'])
        self.assertFalse(aligned([dict(selected[0],weight=0)]))
        for weight in (True,float('nan'),3):
            with self.assertRaises(ValueError):validate([dict(selected[0],weight=weight)])
    def test_prompt_trigger_and_native_reference_preserve_audio_and_request(self):
        plan={'prompt':'Change jacket. <Picture 1> gives the new clothes.',
              'images':[{'index':1,'role':'keyframe','seconds':0}],
              'audios':[{'index':1,'role':'reuse','start':315}]}
        before=copy.deepcopy(plan)
        result=prepare_plan(plan,[{'path':str(self.adapter()),'weight':1}],True)
        self.assertTrue(result['prompt'].startswith('vfx_edit:'))
        self.assertEqual(result['images'][0]['role'],'reference')
        self.assertEqual(result['audios'],plan['audios']);self.assertEqual(plan,before)
        with self.assertRaisesRegex(ValueError,'allineata'):prepare_plan(plan,[{'path':str(self.adapter()),'weight':1}],False)
    def test_character_swap_requires_picture(self):
        selected=[{'path':str(self.adapter('minimax_h3_character_swap.safetensors')),'weight':1}]
        with self.assertRaisesRegex(ValueError,'immagine'):prepare_plan({'prompt':'Replace actor','images':[]},selected,True)
        plan=prepare_plan({'prompt':'Replace actor','images':[{'index':1,'role':'reference','seconds':0}]},selected,True)
        self.assertTrue(plan['prompt'].startswith('body_swap:'))
    def test_modal_capture_is_request_local_and_has_shared_catalog(self):
        chat,source,refs,outputs,params=self.original();path=self.adapter()
        self.app.save_settings({'lora_dirs':[str(self.folder)]})
        before=copy.deepcopy(self.app.store.settings())
        data=describe(self.app,chat,source);self.assertEqual(data['loras'][0]['profile'],'vfx_ffp')
        result=request(self.app,chat,{'source':source,'assistant':False,'remount':False,
            'parameters':{'loras':[{'path':str(path),'weight':.9}]},
            'patches':[{'clip':1,'mode':'video','prompt':'Change jacket','images':[],'start':0,'end':3}]})
        payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(result['job_id'],))['payload'])
        opts=payload['settings']['video_overrides'][self.model['id']]
        self.assertEqual(opts['source_conditioning'],'aligned');self.assertEqual(opts['loras'][0]['weight'],.9)
        self.assertEqual(payload['settings']['_video_edit']['patches'][0]['end'],3)
        self.assertEqual(self.app.store.settings(),before)
    def test_bad_mode_fails_before_enqueue(self):
        chat,source,*_=self.original();path=self.adapter()
        with self.assertRaisesRegex(ValueError,'Modifica video'):
            request(self.app,chat,{'source':source,'assistant':False,'parameters':{'loras':[{'path':str(path),'weight':1}]},'patches':[{'clip':1,'prompt':'Change jacket','images':[]}]})
        self.assertFalse(self.app.store.one("SELECT id FROM jobs WHERE status='queued'"))

if __name__=='__main__':unittest.main()
