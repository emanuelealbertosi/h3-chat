import copy,json,threading,unittest
from unittest.mock import patch
import test_visual_models as fixture
from h3chat.image_history import last_seed
from h3chat.workspaces import guest_allowed

class ImageSeedTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown

    def result(self,seed,finished,model=None,status='done',legacy=False):
        model=model or self.qwen
        chat=self.app.store.create_chat()['id']
        ident=self.app.send(chat,{'prompt':'Un faro','image_model':model['id'],'assistant':False})['job_id']
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
        meta={'model':model['name'],'image_parameters':{'seed':seed},'timing':{'finished_at':finished}}
        if not legacy:meta['image_model_id']=model['id']
        self.app.store.update_answer(job,'Immagine',status,[],meta)
        self.app.store.execute('UPDATE jobs SET status=? WHERE id=?',(status,ident))
        return job

    def test_last_completed_actual_seed_across_chats_and_canvas(self):
        before=copy.deepcopy(self.app.store.settings())
        self.assertIsNone(last_seed(self.app,self.qwen['id'])['seed'])
        chosen=self.result(12345,300)
        self.result(678,200) # A later queued job need not be the last completed.
        self.result(888,400,status='failed')
        self.result(-1,500)
        self.result(444,600,model=self.ming)
        actual=last_seed(self.app,self.qwen['id'])
        self.assertEqual((actual['seed'],actual['chat_id'],actual['message_id']),(12345,chosen['chat_id'],chosen['message_id']))
        self.assertEqual(last_seed(self.app,self.ming['id'])['seed'],444)
        self.assertEqual(self.app.store.settings(),before)
        with self.assertRaises(ValueError):last_seed(self.app,'unknown')
        self.assertTrue(guest_allowed('/api/images/last-seed','GET'))

    def test_older_answers_are_read_without_ambiguous_model_matches(self):
        self.qwen=self.app.external_model(self.qwen['external_config']|{'name':'Qwen seed history test'})
        self.result(987,100,legacy=True)
        self.assertEqual(last_seed(self.app,self.qwen['id'])['seed'],987)
        self.app.catalog['duplicate']=self.ming|{'id':'duplicate','name':self.qwen['name']}
        self.assertIsNone(last_seed(self.app,self.qwen['id'])['seed'])
        self.result(765,200)
        self.assertEqual(last_seed(self.app,self.qwen['id'])['seed'],765)

    def test_generation_records_effective_seed_and_actual_model_id(self):
        chat=self.app.store.create_chat()['id']
        ident=self.app.send(chat,{'prompt':'Un faro','image_model':self.qwen['id'],'assistant':False,
                                 'image_parameters':{'seed':-1}})['job_id']
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
        output={'id':ident,'path':'outputs/test.png','name':'test.png','mime':'image/png','generation':{'seed':456789}}
        with patch.object(self.app.engine,'generate',return_value=output):self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1]
        self.assertEqual(answer['meta']['image_model_id'],self.qwen['id'])
        self.assertEqual(last_seed(self.app,self.qwen['id'])['seed'],456789)
        self.assertEqual(json.loads(job['payload'])['settings']['_image_request_parameters']['seed'],-1)

if __name__=='__main__':unittest.main()
