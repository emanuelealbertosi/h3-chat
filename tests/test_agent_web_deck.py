"""Five-slide Web workflow through the real coordinator with simulated providers.

This verifies tool composition/source persistence, not online search quality or a
real LLM's autonomy. Existing H3 slide and image-lot builders are used unchanged.
"""
import json
import threading
import unittest
from unittest.mock import patch
from pathlib import Path
import test_agent_runtime as fixture
from test_agent_runtime import decision
from test_image_batch import PNG
from h3chat.agent_state import load
from h3chat.slides import PREFIX

class WebDeckTests(unittest.TestCase):
    setUp=fixture.AgentTests.setUp
    tearDown=fixture.AgentTests.tearDown
    ticket=fixture.AgentTests.ticket
    def test_h3_search_download_original_images_documents_and_make_exactly_five_slides(self):
        chat,job=self.ticket('agent: Crea una presentazione sulla macchina di Turing di 5 slide, scarica immagini e documenti e fonti da internet',confirm_writes=False)
        row={'title':'Turing paper','url':'https://example.org/turing','text':'A Turing machine has a tape, a head, a finite control and a transition function.','snippet':'Original paper','read':True}
        step=[0];page=[0];seen=[False];lot=[None];doc=[None]
        def completion(messages,settings,cancel,**kwargs):
            props=(kwargs.get('schema') or {}).get('properties',{})
            if 'action' in props:
                data=json.loads(messages[-1]['content']);step[0]+=1
                if step[0]==1:return decision('web_search',{'query':'Turing computing machines original paper'})
                if step[0]==2:return decision('download_web_document',{'url':'https://example.org/paper.pdf','name':'Turing.pdf'})
                if step[0]==3:
                    doc[0]=data['artifacts'][-1]['id'];return decision('read_attachment',{'artifact_id':doc[0],'number':1})
                if step[0]==4:return decision('search_web_images',{'query':'Turing machine diagram','count':1})
                if step[0]==5:
                    image=json.loads(data['observations'][-1]['data'])['images'][0]['id'];return decision('import_web_images',{'image_ids':[image],'lot_name':'Macchina di Turing'})
                if step[0]==6:
                    lot[0]=json.loads(data['observations'][-1]['data'])['lot_id'];return decision('create_slides',{'prompt':'Spiega la macchina di Turing in italiano usando le fonti e il diagramma scaricati.','count':5,'lot_ids':[lot[0]],'source_artifact_ids':[doc[0]]})
                return decision('finish',message='Cinque slide con fonti e immagini scaricate.')
            if 'slides' in props:
                seen[0]=any('example.org/turing' in m['content'] for m in messages)
                return json.dumps({'title':'Macchina di Turing','visual_direction':'Diagramma e spiegazioni','slides':[{'title':v,'purpose':v} for v in ['Idea','Nastro','Testina','Transizioni','Calcolabilità']]}),'stop'
            if 'content' in props:return json.dumps({'content':'Spiegazione del modello di calcolo','visual_plan':'Schema del nastro','notes':'Fonte originale [W1] e documento [D1].','sources':['W1','D1']}),'stop'
            page[0]+=1
            return '<style>body{font:32px Arial}</style><h1>Macchina di Turing</h1><p>Nastro, testina e stati finiti.</p>','stop'
        def worker(name,request,*a,**kw):
            self.assertEqual(name,'agent-web-image-worker.py');suffix='.pdf' if request.get('op')=='document' else '.png';p=self.app.data/request['folder']/(request['id']+suffix);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'%PDF-1.4\n%%EOF' if suffix=='.pdf' else PNG)
            return {'id':request['id'],'path':p.relative_to(self.app.data).as_posix(),'name':'Turing'+suffix,'mime':'application/pdf' if suffix=='.pdf' else 'image/png'}
        document={'pages':1,'blocks':[{'text':'Turing formalized effective computation using a tape and a finite table.','location':'p. 1','page':1}]}
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=completion),patch.object(self.app.engine,'tool_call',side_effect=worker),patch.object(self.app.engine,'read_document',return_value=document),patch('h3chat.web_search.search',return_value=[row]),patch('h3chat.web_search.fetch',return_value='<img src="/tape.png" alt="Tape diagram">'),patch('h3chat.web_search.public_url',side_effect=lambda url:url):
            self.app.execute_job(job,threading.Event())
        state=load(self.app,chat,job['id']);self.assertEqual(state['status'],'done',{'message':state['message'],'usage':state['usage']});self.assertTrue(all(a['status']=='done' for a in state['actions']),state['actions']);self.assertTrue(seen[0])
        artifact=self.app.store.canvas_history.get(chat,state['artifacts'][-1]['id']);deck=json.loads(artifact['content'][len(PREFIX):-4]);self.assertEqual(len(deck['pages']),5);self.assertGreaterEqual(page[0],5)
        self.assertTrue(any(v['mime']=='image/png' for v in artifact['media']));self.assertEqual(state['config']['scope'],'h3');self.assertFalse(state['config']['allow_images'])

if __name__=='__main__':unittest.main()
