import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.service import Service
from h3chat.slides import PREFIX,encode,options
from h3chat.slide_revision import enqueue
from h3chat.downloads import Cancelled
from h3chat.voice import DEFAULTS as VOICE,controls,validate_fields

ROOT=Path(__file__).resolve().parents[1]


class SlideAITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.app=Service(ROOT,self.temp.name,start_worker=False);self.addCleanup(self.app.close)
        self.model={'id':'fixture-chat','name':'Chat fixture','capabilities':['chat'],'files':[],'vision':{'enabled':False}}
        self.image={'id':'fixture-image','name':'Anima fixture','capabilities':['create'],'files':[],'architecture':'anima'}
        self.events=[]

    def model_for(self,ident,capability):return self.image if capability=='create' else self.model

    def deck(self,chat):
        deck={'version':1,'engine':'llm','format':'4:3','title':'Corso','design':'playful','detail':'full','visual_direction':'Palette calda',
              'references':[{'id':'R1','label':'Libro · pagina 2'}],'pages':[
              {'title':'Prima','status':'ready','html':'<main><h1>Prima</h1><p>Testo originale [R1]</p></main>','sources':['R1']},
              {'title':'Seconda','status':'ready','html':'<main><h1>Seconda</h1><svg><circle r="5"/></svg></main>','sources':[]}]}
        saved=self.app.store.canvas_history.save(chat,{'title':'Corso','content':encode(deck),'media':[]})
        return saved,deck

    def test_revision_changes_only_selected_page_and_preserves_original_history(self):
        chat=self.app.store.create_chat()['id'];saved,original=self.deck(chat)
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):
            sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':'Rendi il titolo più vivace'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],))
        def complete(messages,settings,cancel,**kw):
            self.assertIn('Palette calda',messages[-1]['content']);self.assertIn('1280, 960',messages[-1]['content'])
            kw['on_text']('<main><h1>Nuovo')
            return '<main><h1>Nuovo titolo</h1><p>Testo corretto [R1]</p></main>','stop'
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete):
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        result=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4])
        self.assertEqual(result['pages'][1],original['pages'][1]);self.assertIn('Nuovo titolo',result['pages'][0]['html'])
        self.assertEqual(self.app.store.canvas_history.get(chat,saved['id'])['content'],encode(original))
        self.assertEqual(len(self.app.store.canvas_history.listing(chat)['items']),2)
        self.assertNotIn('<main>',answer['content'])

    def test_revision_refuses_foreign_artifact_and_cancel_keeps_other_pages(self):
        chat=self.app.store.create_chat()['id'];other=self.app.store.create_chat()['id'];saved,original=self.deck(chat)
        with self.assertRaises(ValueError):enqueue(self.app,other,{'artifact_id':saved['id'],'page':0,'prompt':'Cambia'})
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':'Cambia'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],))
        def complete(*args,**kw):kw['on_text']('<main><h1>Parziale');raise Cancelled()
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete):self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'cancelled')
        result=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4])
        self.assertEqual(result['pages'][1],original['pages'][1]);self.assertEqual(result['pages'][0]['status'],'interrupted')

    def test_all_images_are_planned_then_generated_before_html_and_catalog_is_reused(self):
        chat=self.app.store.create_chat()['id']
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):
            sent=self.app.send(chat,{'prompt':'Crea 2 slide','slides':{'generate_images':True,'image_model':'fixture-image'}})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));generated=[]
        def complete(messages,settings,cancel,**kw):
            schema=kw.get('schema')
            if schema and 'slides' in schema['properties']:
                self.events.append('outline');return json.dumps({'title':'Corso','slides':[{'title':'A','purpose':'Introduzione'},{'title':'B','purpose':'Esempio'}]}),'stop'
            if schema and 'images' in schema['properties']:
                self.events.append('image-plan');self.assertIn('tag descrittivi in inglese',messages[-1]['content'])
                return json.dumps({'images':[{'slide':i,'prompt':'colorful illustration, abstract shapes','description':'Illustrazione '+str(i)} for i in (1,2)]}),'stop'
            self.events.append('html');self.assertEqual(len(generated),2);self.assertTrue(all(image['id'] in str(messages) for image in generated))
            repair=messages[-1]['content'].startswith('Questa pagina deve usare')
            index=1 if repair or 'Crea SOLO la pagina 2/' in messages[-1]['content'] else 0
            figure='' if index==1 and not repair else '<img data-asset-id="'+generated[index]['id']+'">'
            html='<main><h1>Slide</h1>'+figure+'</main>';kw['on_text'](html);return html,'stop'
        def generate(model,settings,prompt,refs,ident,cancel,stage):
            self.events.append('image');self.assertEqual(settings['memory_policy'],'on_demand');self.assertEqual(settings['ram_cache_gb'],0)
            image={'id':ident,'mime':'image/png','name':'image.png','path':'outputs/'+ident+'/image.png'};generated.append(image);return image
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama') as llm,patch.object(self.app.engine,'generate',side_effect=generate),patch.object(self.app.engine,'completion',side_effect=complete):self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        self.assertEqual(self.events,['outline','image-plan','image','image','html','html','html']);self.assertEqual(llm.call_count,2)
        self.assertEqual(len(answer['meta']['artifact']['media']),2)
        deck=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4])
        for index,image in enumerate(generated):self.assertIn(image['id'],deck['pages'][index]['html'])
        self.assertEqual([item['asset_id'] for item in deck['image_generation']['plan']],[image['id'] for image in generated])
        self.assertFalse(options('').get('generate_images',False))
        with self.assertRaises(ValueError):options('',{'generate_images':'yes'})


class NaturalVoiceTests(unittest.TestCase):
    def test_natural_voice_does_not_force_flat_prosody_and_other_controls_remain_explicit(self):
        _,natural=controls(copy.deepcopy(VOICE),'Leggi questo testo')
        self.assertNotIn('prosody:expressive_low',natural['tags']);self.assertNotIn('prosody:expressive_high',natural['tags'])
        _,warm=controls(VOICE|{'_voice_fields':{'expressiveness':'high','emotion':'affection'}},'Leggi il testo')
        self.assertIn('prosody:expressive_high',warm['tags']);self.assertIn('emotion:affection',warm['tags'])
        _,quiet=controls(VOICE|{'_voice_fields':{'expressiveness':'low'}},'Leggi il testo')
        self.assertIn('prosody:expressive_low',quiet['tags'])
        with self.assertRaises(ValueError):validate_fields({'expressiveness':'unknown'})
