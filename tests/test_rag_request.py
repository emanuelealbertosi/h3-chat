import json,unittest
from unittest.mock import patch
import test_visual_models as fixture
from h3chat.image_collections import enqueue_generation

class RagRequestTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown
    def test_request_depth_override_is_bounded_and_does_not_change_defaults(self):
        self.app.save_settings({'rag_top_k':6});chat=self.app.store.create_chat()['id']
        for depth in (1,12,None):
            ticket=self.app.send(chat,{'prompt':'Spiega le fonti','assistant':False,'rag':True,**({'rag_top_k':depth} if depth is not None else {})});job=self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ticket['job_id'],));self.assertEqual(json.loads(job['payload'])['settings']['rag_top_k'],depth or 6);self.assertEqual(self.app.store.settings()['rag_top_k'],6);self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(ticket['job_id'],))
        for value in (0,13,True,'12',1.5,None):
            with self.subTest(depth=value),self.assertRaisesRegex(ValueError,'Estratti RAG'):self.app.send(chat,{'prompt':'Spiega','rag_top_k':value})
    def test_source_selection_is_per_payload_empty_is_explicit_and_foreign_ids_fail(self):
        project=self.app.knowledge.save({'name':'Scelte'});other=self.app.knowledge.save({'name':'Altro'});chat=self.app.store.create_chat(project_id=project['id'])['id']
        self.app.store.execute('INSERT INTO project_sources(id,project_id,path,name) VALUES (?,?,?,?)',('chosen',project['id'],str(self.base/'chosen.txt'),'Scelta'));self.app.store.execute('INSERT INTO project_sources(id,project_id,path,name) VALUES (?,?,?,?)',('foreign',other['id'],str(self.base/'foreign.txt'),'Privata'))
        for selection in (['chosen'],[],None):
            ticket=self.app.send(chat,{'prompt':'Spiega le fonti','assistant':False,'rag':True,**({'rag_sources':selection} if selection is not None else {})});job=self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ticket['job_id'],));self.assertEqual(json.loads(job['payload'])['settings']['_rag_sources'],selection);self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(ticket['job_id'],))
        with self.assertRaisesRegex(ValueError,'Selezione fonti'):self.app.send(chat,{'prompt':'Spiega','rag_sources':['foreign']})
    def test_image_lot_forwards_the_same_request_selection_and_depth_contract(self):
        project=self.app.knowledge.save({'name':'Lotto'});chat=self.app.store.create_chat(project_id=project['id'])['id']
        with patch.object(self.app,'send',return_value={'job_id':'fixture'}) as send:
            enqueue_generation(self.app,chat,{'prompt':'Illustra le fonti','options':{'name':'Lotto','count':1,'rag':True},'rag_sources':[],'rag_top_k':12})
        body=send.call_args.args[1];self.assertEqual(body['rag_sources'],[]);self.assertEqual(body['rag_top_k'],12);self.assertTrue(body['rag'])
    def test_agent_depth_override_snapshot_inherits_into_project_search_without_saving(self):
        from types import SimpleNamespace
        from h3chat.agent_knowledge_tools import rag_settings
        self.app.save_settings({'rag_top_k':6});chat=self.app.store.create_chat()['id'];before=self.app.store.settings()
        for depth in (12,1,None):
            ticket=self.app.send(chat,{'prompt':'agent: Cerca nelle fonti','lab':'agent','rag':True,'rag_sources':[],**({'rag_top_k':depth} if depth is not None else {})});job=self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ticket['job_id'],));snapshot=json.loads(job['payload'])['settings'];self.assertEqual(snapshot['rag_top_k'],depth or 6);self.assertEqual(snapshot['_rag_sources'],[])
            ctx=SimpleNamespace(app=self.app,settings=snapshot,state={})
            with patch('h3chat.agent_knowledge_tools.model_options',return_value={'configured':{'available':True,'profile':'plain','path':'','name':'Fixture lessicale'}}):
                local,_=rag_settings(ctx,'project-fixture')
            self.assertEqual(local['rag_top_k'],depth or 6);self.assertEqual(self.app.store.settings(),before);self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(ticket['job_id'],))
        for value in (0,13,True,'12',1.5,None):
            with self.subTest(depth=value),self.assertRaisesRegex(ValueError,'Estratti RAG'):self.app.send(chat,{'prompt':'agent: Cerca nelle fonti','lab':'agent','rag_top_k':value})
        self.assertEqual(self.app.store.settings(),before)

if __name__=='__main__':unittest.main()
