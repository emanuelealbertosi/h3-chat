import base64,json,threading,unittest
from unittest.mock import patch
import test_visual_models as fixture
from test_image_batch import PNG
from h3chat.image_collections import create,update,enqueue_generation
from h3chat.slide_image_lots import resolve,assign,ids

class SlideImageLotTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown
    def lot(self):
        images=[self.app.upload({'name':n+'.png','data':base64.b64encode(PNG).decode()}) for n in ('Porta AND','Porta NOT')]
        return create(self.app,{'name':'Porte logiche','images':[{'id':m['id'],'caption':m['name']} for m in images]})
    def test_multi_lot_validation_and_explicit_rotation(self):
        lot=self.lot();assets,captions=resolve(self.app,[lot['id']]);self.assertEqual(len(captions),2)
        update(self.app,lot['id'],{'semantic_enabled':False});assets,captions=resolve(self.app,[lot['id']]);self.assertEqual(captions,{})
        plan,mode=assign(None,{'slides':[{}, {}, {}]},assets,captions,{},threading.Event(),lambda s:None);self.assertEqual(mode,'rotation');self.assertEqual([r['asset_id'] for r in plan],[assets[0]['id'],assets[1]['id'],assets[0]['id']])
        for bad in (['x'],[{}],[lot['id'],lot['id']]):
            with self.assertRaises(ValueError):ids(bad)
    def test_slide_send_uses_selected_lot_and_never_generates_new_images(self):
        lot=self.lot();images=[i['media'] for i in lot['images']];chat=self.app.store.create_chat()['id']
        ticket=self.app.send(chat,{'prompt':'Crea 2 slide sulle porte logiche','lab':'slides','rag':False,'slides':{'count':2,'image_source':'lots','image_lots':[lot['id']],'generate_images':True}})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));self.assertFalse(json.loads(job['payload'])['settings']['_slides']['generate_images'])
        composed=[0]
        def completion(messages,settings,cancel,**kw):
            props=kw.get('schema',{}).get('properties',{})
            if 'slides' in props:return json.dumps({'title':'Logica','visual_direction':'Diagrammi','slides':[{'title':'NOT','purpose':'Negazione'},{'title':'AND','purpose':'Congiunzione'}]}),'stop'
            if 'content' in props:return json.dumps({'content':'Spiega gli ingressi e il risultato.','visual_plan':'Figura della porta','notes':'Confronta i segnali','sources':[]}),'stop'
            if 'assignments' in props:return json.dumps({'assignments':[{'slide':1,'asset_id':images[1]['id']},{'slide':2,'asset_id':images[0]['id']}]}),'stop'
            idx=1-composed[0];composed[0]+=1
            return '<main><h1>Porta logica</h1><img data-asset-id="'+images[idx]['id']+'"></main>','stop'
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=completion),patch.object(self.app.engine,'generate') as generate,patch('h3chat.slide_vision.describe') as vision:
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta']);generate.assert_not_called();vision.assert_not_called()
        deck=json.loads(answer['meta']['artifact']['content'][13:-4]);self.assertEqual(deck['image_lots']['ids'],[lot['id']]);self.assertEqual(deck['image_lots']['selection'],'semantic');self.assertNotIn('image_generation',deck)
        self.assertEqual([r['asset_id'] for r in deck['image_lots']['plan']],[images[1]['id'],images[0]['id']])
        from h3chat.slides import edit_options
        restored=edit_options('Migliora impaginazione',answer['meta']['artifact']['content']);self.assertEqual(restored['image_source'],'lots');self.assertEqual(restored['image_lots'],[lot['id']]);self.assertFalse(restored['generate_images'])
    def test_resident_policy_does_not_load_media_models_for_existing_lots(self):
        settings=self.app.store.settings()|{'memory_policy':'resident','_slides':{'image_source':'lots'}}
        self.app.engine.policy='resident'
        with patch.object(self.app.engine,'configure'),patch.object(self.app.engine,'start_llama') as llm,patch.object(self.app.engine,'start_image') as image,patch.object(self.app.engine,'start_music') as music,patch.object(self.app.engine,'start_video') as video:
            self.app.engine.prepare(settings,threading.Event(),lambda s:None)
        llm.assert_called_once();image.assert_not_called();music.assert_not_called();video.assert_not_called()
    def test_single_image_lot_generation_and_rag_grounding_are_planned_once(self):
        project=self.app.knowledge.save({'name':'Logica'})['id'];chat=self.app.store.create_chat(project_id=project)['id']
        ticket=enqueue_generation(self.app,chat,{'prompt':'Una illustrazione della porta AND senza testo','options':{'name':'Illustrazioni AND','count':1,'model':self.qwen['id'],'rag':True}})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));seen=[]
        task={'prompt':'A clear AND logic gate illustration','model_id':self.qwen['id'],'model_choice':'','references':[],'parameters':{},'loras':[],'lora_mode':'none'}
        def completion(messages,*a,**kw):seen.append(messages[-1]['content']);return json.dumps({'images':[task]}),'stop'
        def generate(model,settings,prompt,refs,ident,*a):
            folder=self.app.data/'outputs'/ident;folder.mkdir(parents=True);(folder/'image.png').write_bytes(PNG);return {'id':ident,'name':'AND.png','path':f'outputs/{ident}/image.png','mime':'image/png','generation':{'seed':42}}
        source={'id':'1','source_id':'1','name':'Libro','location':'pagina 2','page':2,'text':'AND è vera solo quando entrambi gli ingressi sono veri.','source_url':''}
        with patch.object(self.app.knowledge,'retrieve',return_value=([source],'parole')),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=completion),patch.object(self.app.engine,'generate',side_effect=generate):self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta']);self.assertEqual(len(seen),1);self.assertIn('entrambi gli ingressi',seen[0]);self.assertEqual(len(answer['media']),1)
        from h3chat.image_collections import get
        self.assertEqual(get(self.app,job['id'])['name'],'Illustrazioni AND')

if __name__=='__main__':unittest.main()
