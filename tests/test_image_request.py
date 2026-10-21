import base64,copy,io,json,threading,unittest
from unittest.mock import patch
import test_visual_models as fixture
from h3chat.image_options import options
from h3chat.request_draft import load

class ImageRequestTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown

    def test_chat_controls_are_snapshotted_and_editable_draft_preserves_them(self):
        model=self.app.external_model({'profile':'moss','files':self.qwen['external_config']['files']})
        original=copy.deepcopy(self.app.store.settings());chat=self.app.store.create_chat()['id']
        parameters={'width':1024,'height':576,'aspect':'16:9','steps':32,'cfg':2.5,'sampler':'heun','scheduler':'karras','seed':12345}
        ident=self.app.send(chat,{'prompt':'Un faro al tramonto','image_model':model['id'],'assistant':False,'image_parameters':parameters})['job_id']
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,));payload=json.loads(job['payload']);captured=options(model,payload['settings'],payload['prompt'])
        for key,value in parameters.items():self.assertEqual(captured[key],value)
        self.assertFalse(payload['settings']['_assistant']);self.assertEqual(payload['prompt'],'Un faro al tramonto')
        self.assertEqual(self.app.store.settings(),original)
        draft=load(self.app,chat,job['message_id']);saved=draft['controls']['image_presets'][model['id']]
        self.assertEqual(saved['seed'],12345);self.assertEqual(saved['scheduler'],'karras')
        self.assertEqual(options(self.qwen,payload['settings'])['steps'],25)
        explicit=options(model,payload['settings'],'Un faro, 1024x1024, 24 passi, seed 99, CFG 4, sampler euler, scheduler sgm_uniform.')
        self.assertEqual((explicit['width'],explicit['height'],explicit['steps'],explicit['seed'],explicit['cfg'],explicit['sampler'],explicit['scheduler']),(1024,1024,24,99,4,'euler','sgm_uniform'))

    def test_bad_controls_fail_before_queueing(self):
        chat=self.app.store.create_chat()['id']
        for parameters in ({'steps':0},{'seed':1.5},{'scheduler':'invented'},{'width':1080},{'cfg':float('nan')},{'unexpected':1}):
            with self.subTest(parameters=parameters),self.assertRaises(ValueError):
                self.app.send(chat,{'prompt':'Un faro','image_model':self.qwen['id'],'image_parameters':parameters})
        with self.assertRaises(ValueError):self.app.send(chat,{'prompt':'Un faro','image_parameters':{'seed':1}})
        self.assertIsNone(self.app.store.one('SELECT id FROM jobs'))

    def test_moss_attachment_reaches_edit_worker_with_saved_strength_and_prompt_priority(self):
        from PIL import Image
        image=io.BytesIO();Image.new('RGB',(512,320),'navy').save(image,'PNG')
        media=self.app.upload({'name':'source.png','data':base64.b64encode(image.getvalue()).decode()})
        model=self.app.external_model({'profile':'moss','files':self.qwen['external_config']['files']})
        self.assertIn('edit',model['capabilities']);self.assertEqual(model['max_refs'],1)
        chat=self.app.store.create_chat()['id'];original=copy.deepcopy(self.app.store.settings())
        ticket=self.app.send(chat,{'prompt':'A painted landscape, intensità 0,35','media':[{'id':media['id']}],
            'image_model':model['id'],'assistant':False,'image_parameters':{'strength':.7,'seed':42}})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))
        saved=load(self.app,chat,job['message_id'])['controls']['image_presets'][model['id']]
        self.assertEqual(saved['strength'],.7);self.assertEqual(self.app.store.settings(),original)
        result={'id':job['id'],'name':'out.png','mime':'image/png','path':'outputs/out.png'}
        with patch.object(self.app.engine,'refine_image_prompt') as refine,patch.object(self.app.engine,'generate',return_value=result) as generate:
            self.app.execute_job(job,threading.Event())
        refine.assert_not_called();args=generate.call_args.args
        self.assertEqual(args[1]['_image_options']['strength'],.35)
        request=self.app.engine.image_request(args[0],args[1],args[2],args[3],self.base/'out.png')
        self.assertEqual(request['strength'],.35);self.assertEqual(len(request['references']),1)
        self.assertEqual(request['references'][0],str(self.app.data/media['path']))
