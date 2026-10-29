import base64,json,threading,unittest
from unittest.mock import patch
from test_agent_media import AgentMediaTests as _Fixture
from test_agent_runtime import decision
from test_study import SOURCE,completion
from h3chat.study import decode
from h3chat.agent_state import load

class AgentStudyTests(unittest.TestCase):
    setUp=_Fixture.setUp
    tearDown=_Fixture.tearDown
    def test_agent_reads_source_then_builds_study_with_preserved_evidence(self):
        self.app.save_settings({'context':32768,'max_tokens':8000,'vision_enabled':False})
        media=self.app.upload({'name':'lezione.txt','data':base64.b64encode(SOURCE.encode()).decode()});chat=self.app.store.create_chat()['id']
        ticket=self.app.send(chat,{'prompt':'agent: Leggi il file e crea due flashcard con citazioni','media':[media],'rag':False,'agent':{'confirm_writes':False}});job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));step=[0]
        def complete(messages,settings,cancel,**kw):
            if 'action' in (kw.get('schema') or {}).get('properties',{}):
                step[0]+=1
                if step[0]==1:return decision('read_attachment',{'number':1})
                if step[0]==2:return decision('create_study',{'prompt':'Due flashcard dalle fonti appena lette','count':2})
                return decision('finish',message='Schede pronte.')
            return completion(messages,settings,cancel,**kw)
        doc={'blocks':[{'text':SOURCE,'location':'pagina 1','page':1}],'pages':1,'warnings':[]}
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'read_document',return_value=doc),patch.object(self.app.engine,'completion',side_effect=complete):self.app.execute_job(job,threading.Event())
        state=load(self.app,chat,job['id']);self.assertEqual(state['status'],'done',state)
        artifact=self.app.store.canvas_history.get(chat,state['artifacts'][-1]['id']);deck=decode(artifact['content']);self.assertEqual(len(deck['items']),2);self.assertEqual(deck['sources'][0]['text'],SOURCE);self.assertEqual(deck['sources'][0]['page'],1)
    def test_agent_imports_public_source_indexes_searches_then_builds_study(self):
        self.app.save_settings({'context':32768,'max_tokens':8000,'rag_embedding_profile':'plain','rag_embedding_model':'','rag_visual':False,'vision_enabled':False})
        project=self.app.knowledge.save({'name':'Notebook pubblico','sources_only':True});chat=self.app.store.create_chat()['id']
        ticket=self.app.send(chat,{'prompt':'agent: Importa la pagina pubblica, cerca la fotosintesi e prepara due flashcard','rag':False,'agent':{'allow_projects':True,'confirm_writes':False}})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));payload=json.loads(job['payload']);payload['settings'].update({'_web':True,'_rag':True});job['payload']=json.dumps(payload);self.app.store.execute('UPDATE jobs SET payload=? WHERE id=?',(job['payload'],job['id']));step=[0]
        def complete(messages,settings,cancel,**kw):
            if 'action' in (kw.get('schema') or {}).get('properties',{}):
                step[0]+=1
                if step[0]==1:return decision('import_public_study_source',{'project_id':project['id'],'kind':'web','name':'Botanica','url':'https://example.com/plants'})
                if step[0]==2:return decision('project_search',{'query':'fotosintesi piante ossigeno','project_id':project['id']})
                if step[0]==3:return decision('create_study',{'prompt':'Prepara due flashcard dalle fonti ricercate','count':2})
                return decision('finish',message='Fonti indicizzate e flashcard pronte.')
            return completion(messages,settings,cancel,**kw)
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete),patch('h3chat.web_search.fetch',return_value='<p>'+SOURCE+'</p>') as fetch:
            self.app.execute_job(job,threading.Event())
        state=load(self.app,chat,job['id']);self.assertEqual(state['status'],'done',state);self.assertTrue(all(a['status']=='done' for a in state['actions']),state)
        sources=self.app.knowledge.project(project['id'])['sources'];self.assertEqual(len(sources),1);self.assertEqual(sources[0]['status'],'ready');self.assertEqual(sources[0]['source_url'],'https://example.com/plants');fetch.assert_called_once()
        artifact=self.app.store.canvas_history.get(chat,state['artifacts'][-1]['id']);deck=decode(artifact['content']);self.assertEqual(len(deck['items']),2);self.assertEqual(deck['sources'][0]['source_id'],sources[0]['id']);self.assertEqual(deck['project_id'],project['id'])
    def test_public_source_import_requires_both_project_and_web_permissions(self):
        from types import SimpleNamespace
        from h3chat.agent_tools import permission
        from h3chat.agent_knowledge_tools import execute
        with self.assertRaises(PermissionError):permission({'allow_projects':False},'import_public_study_source',{})
        ctx=SimpleNamespace(app=self.app,settings={'_web':False})
        with patch('h3chat.web_search.fetch') as fetch:
            with self.assertRaisesRegex(PermissionError,'Web'):execute(ctx,'import_public_study_source',{})
            fetch.assert_not_called()

if __name__=='__main__':unittest.main()
