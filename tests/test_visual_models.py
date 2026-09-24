import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from h3chat.engine import Engine
from h3chat.service import Service
from h3chat.store import DEFAULTS
from h3chat.image_options import options
from h3chat.visual_routing import visual_route
from h3chat.hardware import assess_model
from test_external_models import safetensors
from test_models_hardware import gguf

ROOT = Path(__file__).resolve().parents[1]


class VisualModelsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.app = Service(ROOT, self.base/'data', start_worker=False)
        files = {role:str(safetensors(self.base/(role+'.safetensors'))) for role in ('diffusion','llm','vae')}
        self.ming = self.app.external_model({'profile':'ming','files':files})
        self.qwen = self.app.external_model({'profile':'qwen21','files':files})
        llm = gguf(self.base/'llm.gguf', **{'general.architecture':'qwen3'})
        gguf(self.base/'mmproj.gguf', **{'general.architecture':'clip'})
        self.llm = self.app.external_model({'profile':'chat','files':{'model':str(llm)}})
        self.settings = self.app.save_settings({'chat_model':self.llm['id'],'diagram_model':self.ming['id'],
            'create_model':self.qwen['id'],'edit_model':self.qwen['id']})

    def tearDown(self):
        self.app.close()
        self.tmp.cleanup()

    def route(self, prompt, **settings):
        return visual_route([{'content':prompt,'media':[]}], self.settings | settings)

    def test_auto_diagrams_explicit_wins_and_discussion_stays_text(self):
        for prompt in ('Crea un grafico di y=x^2','Disegna un grafo orientato','Puoi creare un diagramma?', 'Fammi uno schema del neurone'):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.route(prompt)['image_model'], self.ming['id'])
        for prompt in ('Spiegami i grafi','Non creare un grafico','Crea un grafico Mermaid','Scrivi codice per un diagramma','Crea una foto di un gatto'):
            self.assertIsNone(self.route(prompt))
        self.assertIsNone(self.route('Crea un diagramma',diagram_auto=False))
        self.assertEqual(self.route('Crea un diagramma',_image_model=self.qwen['id'])['image_model'], self.qwen['id'])

    def test_presets_and_engine_specific_sampler_validation(self):
        for model,steps in ((self.ming,12),(self.qwen,25)):
            value = options(model,self.settings)
            self.assertEqual((value['width'],value['height'],value['steps'],value['cfg'],value['sampler'],value['scheduler']), (1024,1024,steps,1,'euler','simple'))
            self.assertEqual(value['strength'],1)
            self.assertEqual(model['max_refs'],4)
            self.assertEqual(model['engine'],'vision')
            with self.assertRaises(ValueError):
                self.app.validate_settings({'image_overrides':{model['id']:{'sampler':'ddim_trailing'}}})

    def test_reference_edit_overrides_defaults_without_reordering(self):
        media=[{'id':str(i),'path':str(i)+'.png'} for i in range(4)]
        history=[{'content':'Crea un diagramma dai riferimenti','media':media}]
        route=visual_route(history,self.settings)
        self.assertEqual(route['intent'],'edit')
        self.assertEqual(route['image_model'],self.ming['id'])
        request=self.app.engine.image_request(self.ming,self.settings,'prompt',media,self.base/'out.png')
        self.assertEqual(request['references'],[str(self.app.data/m['path']) for m in media])
        with self.assertRaises(ValueError):self.app.engine.image_request(self.ming,self.settings,'prompt',media+media,self.base/'out.png')

    def test_assistant_choice_is_snapshotted_and_off_skips_refiner(self):
        for assistant in (True,False):
            chat=self.app.store.create_chat()
            result=self.app.send(chat['id'],{'prompt':'Crea un grafico con tre barre','image_model':self.qwen['id'],'assistant':assistant,'canvas':True})
            job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(result['job_id'],))
            payload=json.loads(job['payload'])
            self.assertEqual(payload['settings']['_assistant'],assistant)
            self.assertEqual(payload['settings']['_image_model'],self.qwen['id'])
            self.app.store.save_settings({'create_model':self.ming['id'],'vision_enabled':False})
            media={'id':job['id'],'name':'image.png','path':'outputs/image.png','mime':'image/png'}
            with patch.object(self.app.engine,'refine_image_prompt',return_value=('Precise visual instructions',{'model':self.llm['name']})) as refine, patch.object(self.app.engine,'generate',return_value=media) as generate:
                self.app.execute_job(job,threading.Event())
            self.assertEqual(refine.call_count,int(assistant))
            self.assertEqual(generate.call_args.args[0]['id'],self.qwen['id'])
            self.assertEqual(generate.call_args.args[2], 'Precise visual instructions' if assistant else payload['prompt'])
            answer=self.app.store.messages(chat['id'])[-1]
            self.assertEqual(answer['status'],'done')
            self.assertEqual(answer['media'],[])
            self.assertEqual(answer['meta']['artifact']['media'],[media])
            self.assertEqual(answer['meta']['assistant_on'],assistant)

    def test_assistant_off_and_invalid_values_rejected_before_queue(self):
        for body in ({'assistant':'off'},{'image_model':self.llm['id']}):
            with self.assertRaises(ValueError):self.app.send(self.app.store.create_chat()['id'],{'prompt':'Crea immagine',**body})
        for setting in ({'vision_enabled':'off'},{'diagram_model':self.qwen['id']},{'backend':'vision'}):
            with self.assertRaises(ValueError):self.app.validate_settings(setting)

    def test_vision_off_omits_projector_and_changes_context_identity(self):
        engine=self.app.engine
        on=self.settings|{'vision_enabled':True}
        off=self.settings|{'vision_enabled':False}
        self.assertIn('mmproj',engine.model_files(self.llm,on))
        self.assertNotIn('mmproj',engine.model_files(self.llm,off))
        self.assertNotEqual(engine.session_key('chat',self.llm,on),engine.session_key('chat',self.llm,off))
        history=[{'role':'user','status':'done','seq':1,'content':'Descrivi','media':[{'path':'x.png'}]}]
        with self.assertRaisesRegex(ValueError,'Vision è Off'):engine.chat_messages(history,self.llm,off)

    def test_projector_stays_cpu_in_resident_and_llm_is_reused(self):
        class Response(io.BytesIO):status=200
        class Process:
            pid=123;stdin=None;stdout=None
            def poll(self):return None
            def terminate(self):pass
            def wait(self,timeout):return 0
        for vision in (True,False):
            commands=[]
            settings=self.settings|{'backend':'cuda','memory_policy':'resident','vision_enabled':vision}
            def start(session,args):commands.append(args);session.process=Process()
            with patch('h3chat.engine.runtime_executable',return_value='llama-server.exe'),patch('h3chat.residency.Session.start',start),patch('h3chat.engine.urllib.request.urlopen',return_value=Response(b'{}')):
                self.app.engine.start_llama(self.llm,settings,self.base/'llama.log',threading.Event())
                self.app.engine.start_llama(self.llm,settings,self.base/'llama.log',threading.Event())
            self.assertEqual(len(commands),1,'Assistant must reuse the same loaded LLM')
            self.assertEqual('--mmproj' in commands[0],vision)
            self.assertEqual('--no-mmproj-offload' in commands[0],vision)
            self.app.engine.stop()

    def test_semantic_diagram_edit_routes_to_ming_with_previous_reference(self):
        history=[{'role':'user','status':'done','seq':1,'content':'immagine','media':[{'path':'x.png'}]},
                 {'role':'user','status':'done','seq':2,'content':'Vorrei un altro arco tra i due nodi del disegno precedente','media':[]}]
        with patch.object(self.app.engine,'completion',return_value=json.dumps({'intent':'diagram-edit','prompt':'Add an edge'})) as completion:
            result=self.app.engine.route(history,self.settings,threading.Event())
        self.assertEqual(result['intent'],'edit')
        self.assertEqual(result['image_model'],self.ming['id'])
        self.assertIn('diagram-edit',completion.call_args.kwargs['schema']['properties']['intent']['enum'])

    def test_extra_selected_image_survives_idle_but_is_evicted_before_chat(self):
        class Process:
            pid=123;stdin=None;stdout=None;ended=False
            def poll(self):return 0 if self.ended else None
            def terminate(self):self.ended=True
            def wait(self,timeout):return 0
        base=self.settings|{'create_model':self.ming['id'],'edit_model':self.ming['id']}
        session=self.app.engine._activate('image',self.qwen,base|{'_image_model':self.qwen['id']},self.base/'image.log',threading.Event())
        session.process=Process();session.ready=True
        self.app.engine.configure(base)
        self.assertTrue(session.alive())
        self.app.engine._activate('chat',self.llm,base,self.base/'chat.log',threading.Event())
        self.assertFalse(session.alive())
        self.assertEqual(len(self.app.engine.sessions),1)

    def test_cpu_vision_memory_remains_ram_in_resident(self):
        hardware={'ram':{'total_mb':40000,'free_mb':32000},'gpu':[{'name':'GPU','vendor':'NVIDIA','total_mb':16000,'free_mb':15000}]}
        model=self.llm|{'vision':self.llm['vision']|{'projector_size':1024**3}}
        settings=self.settings|{'memory_policy':'resident','backend':'cuda'}
        on=assess_model(model,settings,hardware)
        off=assess_model(model,settings|{'vision_enabled':False},hardware)
        self.assertEqual(on['vram_gb'],off['vram_gb'])
        self.assertGreater(on['ram_gb'],off['ram_gb']+1)


if __name__=='__main__':unittest.main()
