import copy,json,unittest
from h3chat.generation_presets import load,update,recipe
from h3chat.request_draft import load as draft
import test_visual_models as fixture


class GenerationPresetTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown

    def test_save_reload_update_delete_without_jobs_defaults_sources_or_credentials(self):
        chat=self.app.store.create_chat()['id'];before=copy.deepcopy(self.app.store.settings())
        settings=before|{'_lab':'slides','_slides':{'count':5,'generate_images':True,'reuse_images_from':'a'*32},
            '_assistant':False,'_rag':True,'_rag_sources':['private-source'],'context':16000,'api_key':'PRIVATE',
            'agent_defaults':{'scope':'global'},'_agent':{'options':{'auto_approve':True}}}
        ident=self.app.store.enqueue(chat,'PRIVATE PROMPT',[],settings)
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,));jobs=self.app.store.all('SELECT * FROM jobs')
        data=update(self.app,{'action':'save','name':'Le mie slide','chat_id':chat,'message_id':job['message_id']})
        item=data['items'][0];self.assertEqual(item['kind'],'slides');self.assertEqual(item['recipe']['parameters']['context'],16000)
        raw=json.dumps(data);self.assertNotIn('PRIVATE',raw);self.assertNotIn('private-source',raw)
        self.assertNotIn('auto_approve',raw);self.assertNotIn('reuse_images_from',raw);self.assertNotIn('agent_defaults',raw)
        self.assertEqual(load(self.app),data);self.assertEqual(self.app.store.settings(),before);self.assertEqual(self.app.store.all('SELECT * FROM jobs'),jobs)
        changed=update(self.app,{'action':'save','name':'LE MIE SLIDE','chat_id':chat,'message_id':job['message_id']})
        self.assertEqual(len(changed['items']),1);self.assertEqual(changed['items'][0]['id'],item['id'])
        self.assertEqual(update(self.app,{'action':'delete','id':item['id']})['items'],[])

    def test_every_mode_keeps_its_controls_but_not_input_content(self):
        for kind,controls in [('image',{'image_model':'qwen','image_presets':{'qwen':{'seed':43,'aspect':'16:9','steps':15}}}),
                ('video',{'video':True,'video_model':'h3','video_parameters':{'seed':42,'duration':15}}),
                ('voice',{'voice':True,'voice_fields':{'gender':'female','delivery':'warm'}}),
                ('music',{'music':True,'music_fields':{'lyrics':'PRIVATE','style':'Jazz'}}),('transcribe',{'transcribe':True})]:
            actual,value=recipe({'lab':'auto','controls':controls,'parameters':{'context':8000},'prompt':'PRIVATE','media':[{'path':'PRIVATE'}]})
            self.assertEqual(actual,kind);self.assertNotIn('PRIVATE',json.dumps(value))
        for mode in ('slides','infographic','poster','study','manim','calculate','agent'):
            actual,value=recipe({'lab':mode,mode:{'count':5},'parameters':{},'controls':{}})
            self.assertEqual(actual,mode)

    def test_client_cannot_save_arbitrary_config_and_other_chat_cannot_supply_message(self):
        chat=self.app.store.create_chat()['id'];other=self.app.store.create_chat()['id']
        ident=self.app.store.enqueue(chat,'Example',[],self.app.store.settings());job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
        with self.assertRaises(ValueError):update(self.app,{'action':'save','name':'Bad','config':{'api_key':'x'}})
        with self.assertRaises(ValueError):update(self.app,{'action':'save','name':'Bad','chat_id':other,'message_id':job['message_id']})
        self.assertEqual(load(self.app)['items'],[])

    def test_effective_image_parameters_override_defaults_in_named_preset(self):
        kind,value=recipe({'lab':'auto','controls':{},'parameters':{'seed':-1}},
            {'intent':'create','image_model_id':'moss','image_parameters':{'seed':912,'steps':8,'width':1504,'height':1504,'api_key':'PRIVATE'}})
        self.assertEqual(kind,'image');self.assertEqual(value['controls']['image_presets']['moss']['seed'],912)
        self.assertEqual(value['controls']['image_presets']['moss']['steps'],8);self.assertNotIn('PRIVATE',json.dumps(value))

if __name__=='__main__':unittest.main()
