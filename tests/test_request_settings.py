import copy,json,unittest
from h3chat.request_draft import load
from h3chat.request_settings import snapshot,resolve
import test_visual_models as fixture


class RequestSettingsTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown

    def test_voice_sequence_validation_and_reload_preserve_each_interpretation(self):
        chat=self.app.store.create_chat()['id']
        parts=[{'text':'Prima frase.','voice_fields':{'gender':'female','delivery':'warm'}},
               {'text':'Seconda frase.','voice_fields':{'gender':'male','delivery':'lively'}}]
        before=copy.deepcopy(self.app.store.settings())
        sent=self.app.send(chat,{'prompt':'Sequenza vocale','voice':True,'voice_parts':parts,'assistant':False,'rag':False})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));draft=load(self.app,chat,job['message_id'])
        self.assertEqual(draft['voice_parts'],parts)
        self.assertEqual([p['scene_id'] for p in json.loads(job['payload'])['settings']['_voice_parts']],[0,1])
        self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(sent['job_id'],))
        for invalid in ([],[{'text':''}],[{'text':'Testo','secret':'bad'}]):
            with self.assertRaises(ValueError):self.app.send(chat,{'prompt':'Sequenza','voice':True,'voice_parts':invalid})
        self.assertEqual(self.app.store.settings(),before)

    def test_reload_and_resend_restore_model_tuning_and_rag_without_changing_defaults(self):
        chat=self.app.store.create_chat()['id']
        self.app.store.execute("INSERT INTO projects(id,name,created) VALUES ('project-fixture','Progetto',0)")
        self.app.store.execute("UPDATE chats SET project_id='project-fixture' WHERE id=?",(chat,))
        original=self.app.store.settings()|{'context':16000,'max_tokens':4000,'temperature':.3,
            'system_prompt':'Istruzioni originali','rag_top_k':9,'vision_enabled':False,
            '_rag':False,'_rag_sources':[],'_assistant':False,'_lab':'auto','_web':True,
            '_image_model':self.qwen['id'],'_image_request_parameters':{'steps':18,'seed':141,'aspect':'16:9'},
            '_private_test_secret':'NEVER_EXPOSE_ME','agent_defaults':{'scope':'global','grant_id':'DO_NOT_RESTORE'}}
        ident=self.app.store.enqueue(chat,'Un faro',[],original,True)
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,));draft=load(self.app,chat,job['message_id'])
        self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(ident,))
        self.assertEqual(draft['rag'],{'rag':False,'rag_sources':[],'rag_top_k':9})
        self.assertEqual(draft['parameters']['context'],16000);self.assertEqual(draft['parameters']['max_tokens'],4000)
        self.assertNotIn('NEVER_EXPOSE_ME',json.dumps(draft));self.assertNotIn('DO_NOT_RESTORE',json.dumps(draft))
        self.app.save_settings({'context':8000,'max_tokens':1000,'temperature':.8,'system_prompt':'Nuove istruzioni','rag_top_k':2,'vision_enabled':True})
        before=copy.deepcopy(self.app.store.settings())
        ticket=self.app.send(chat,{'prompt':draft['prompt'],'media':draft['media'],'canvas':draft['canvas'],
             **draft['controls'],**draft['rag'],'request_settings':draft['parameters']})
        saved=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ticket['job_id'],))['payload'])['settings']
        self.assertEqual((saved['context'],saved['max_tokens'],saved['temperature']),(16000,4000,.3))
        self.assertEqual(saved['system_prompt'],'Istruzioni originali');self.assertFalse(saved['vision_enabled'])
        self.assertEqual(saved['rag_top_k'],9);self.assertFalse(saved['_rag']);self.assertEqual(saved['_rag_sources'],[])
        self.assertEqual(self.app.store.settings(),before)

    def test_snapshot_is_allowlisted_and_rejects_permissions_or_secrets_from_request(self):
        value=snapshot(self.app.store.settings()|{'api_key':'PRIVATE','_agent':{'scope':'global'}})
        self.assertNotIn('api_key',value);self.assertNotIn('_agent',value);self.assertNotIn('execution_mode',value)
        before=copy.deepcopy(self.app.store.settings())
        for patch in ({'api_key':'x'},{'agent_defaults':{}},{'execution_mode':'gpu'},{'context':True},{'llm_overrides':[]}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):resolve(self.app,{'request_settings':patch})
        self.assertEqual(self.app.store.settings(),before)

    def test_toolbar_changes_override_reloaded_thinking(self):
        result=resolve(self.app,{'request_settings':{'think_level':'high'},'think_level':'off'})
        self.assertEqual(result['think_level'],'off')

    def test_all_lab_options_are_returned_and_loading_never_enqueues(self):
        chat=self.app.store.create_chat()['id']
        options={'_slides':{'count':'auto','text_tone':'dark','background':'light','palette':'pastel','image_source':'lots','image_lots':['a'*32]},
                 '_infographic':{'voice_gender':'mixed','duration':120,'music':'generate','sprite_ids':['b'*32]},
                 '_posters':{'format':'9:16','text_effect':'neon'},'_study':{'kind':'flashcards','count':12},
                 '_manim_presentation':{'mode':'preserve','source':'attachments'},'_lab_source':'print(42)',
                 '_image_lot':{'name':'Lotto','count':8,'format':'9:16','model':self.qwen['id'],'rag':False}}
        settings=self.app.store.settings()|options|{'_lab':'manim','_assistant':True}
        ident=self.app.store.enqueue(chat,'Un esempio',[],settings)
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,));before=self.app.store.all('SELECT * FROM jobs')
        draft=load(self.app,chat,job['message_id'])
        for source,target in (('_slides','slides'),('_infographic','infographic'),('_posters','poster'),('_study','study'),('_manim_presentation','manim_presentation'),('_image_lot','image_lot'),('_lab_source','lab_source')):
            self.assertEqual(draft[target],options[source])
        self.assertEqual(self.app.store.all('SELECT * FROM jobs'),before)

    def test_background_batch_returns_the_unprefixed_prompt_and_exact_configuration(self):
        chat=self.app.store.create_chat()['id'];config={'name':'Cornici','variants':4,'margin':6,'seed_mode':'fixed','seed':41}
        settings=self.app.store.settings()|{'_slide_backgrounds':{'options':config,'tasks':[],'prompt':'Porte logiche'}}
        ident=self.app.store.enqueue(chat,'Crea sfondi · Cornici\nPorte logiche',[],settings,True)
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
        draft=load(self.app,chat,job['message_id'])
        self.assertEqual(draft['prompt'],'Porte logiche');self.assertEqual(draft['background_batch'],config)

    def test_specialized_video_operations_reopen_with_their_original_parameters(self):
        chat=self.app.store.create_chat()['id']
        for key,config,kind in (('_upscale',{'target':'2x','preview':True,'start':10},'upscale'),
             ('_video_remix',{'mode':'voice','text':'Originale','voice_fields':{'gender':'male'},'runtime':{'secret':'PRIVATE'}},'remix'),
             ('_video_recreate',{'source':'a'*32,'parameters':{'steps':12,'seed':42}},'recreate')):
            settings=self.app.store.settings()|{key:config}
            ident=self.app.store.enqueue(chat,'Operazione',[],settings)
            job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,));draft=load(self.app,chat,job['message_id'])
            self.assertEqual(draft['operation']['kind'],kind);self.assertNotIn('PRIVATE',json.dumps(draft))
            self.app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(ident,))

if __name__=='__main__':unittest.main()
