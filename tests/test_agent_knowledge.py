"""Real workspace/project copies and lexical indexing; no inference or downloads."""
import json
import threading
import unittest
from unittest.mock import patch
import test_agent_inputs as inputs
from test_agent_runtime import decision
from h3chat.agent_state import load
from h3chat.agent_tools import permission,validate

class AgentKnowledgeTests(unittest.TestCase):
    setUp=inputs.AgentInputTests.setUp
    tearDown=inputs.AgentInputTests.tearDown
    ticket=inputs.AgentInputTests.ticket
    media=inputs.AgentInputTests.media
    save=inputs.AgentInputTests.save

    def run_chain(self,job,choose,*,vision=False):
        require=self.app.engine.require_model
        def model(ident,cap):return require(ident,cap)|({'vision':{'enabled':True}} if vision and cap=='chat' else {})
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'require_model',side_effect=model),patch.object(self.app.engine,'completion',side_effect=choose),patch.object(self.app.engine,'tool_call',return_value={'image_url':'data:image/jpeg;base64,AA=='}),patch.object(self.app.knowledge,'refresh') as background:
            self.app.execute_job(job,threading.Event())
        background.assert_not_called();state=load(self.app,job['chat_id'],job['id'])
        self.assertEqual(state['status'],'done',state);self.assertTrue(all(a['status']=='done' for a in state['actions']),state)
        return state

    def test_create_project_import_index_and_search_real_document(self):
        chat,job=self.ticket('agent: Metti il file nel progetto Logica e cercalo',allow_projects=True,confirm_writes=False)
        file=self.media('lezione.txt','text/plain');path=self.app.data/file['path'];path.write_text('La porta XOR vale uno quando gli ingressi sono diversi.',encoding='utf8')
        source=self.save(chat,'Lezione',media=[file]);before=path.read_bytes();steps=[0]
        payload=json.loads(job['payload']);payload['settings']['_rag']=True;job['payload']=json.dumps(payload);self.app.store.execute('UPDATE jobs SET payload=? WHERE id=?',(job['payload'],job['id']))
        def choose(messages,*args,**kwargs):
            data=json.loads(messages[-1]['content']);steps[0]+=1
            if steps[0]==1:return decision('ensure_project',{'name':'Logica','sources_only':True})
            project=data['observations'][0]['data'];ident=json.loads(project)['project_id']
            if steps[0]==2:return decision('import_project_files',{'project_id':ident,'artifact_id':source['id'],'numbers':[1,1]})
            if steps[0]==3:return decision('index_project',{'project_id':ident,'embedding_id':'lexical'})
            if steps[0]==4:return decision('project_search',{'query':'XOR ingressi diversi'})
            self.assertIn('XOR',data['observations'][-1]['data']);return decision('finish',message='File copiato e indicizzato.')
        original=self.app.store.settings();state=self.run_chain(job,choose)
        project=self.app.knowledge.project(state['active_project']);self.assertEqual(project['name'],'Logica');self.assertEqual(len(project['sources']),1)
        row=project['sources'][0];self.assertEqual(row['status'],'ready');self.assertGreater(row['chunks'],0)
        self.assertEqual(path.read_bytes(),before);self.assertTrue(row['imported']);self.assertNotEqual(row['path'],str(path))
        self.assertEqual(self.app.store.chat(chat)['project_id'],None);self.assertEqual(self.app.store.settings(),original)
        self.assertEqual(state['sources'][0]['citation'],'R1');self.assertEqual(state['project_models'][project['id']]['embedding_id'],'lexical')
        self.assertEqual(state['actions'][2]['result']['ready'],1);self.assertEqual(state['actions'][2]['result']['errors'],0)
        self.assertFalse(state['actions'][1]['result']['files'][0]['duplicate']);self.assertTrue(state['actions'][1]['result']['files'][1]['duplicate'])

    def test_catalog_image_copy_caption_and_index_with_text_embedding(self):
        chat,job=self.ticket('agent: Cataloga e aggiungi la figura al progetto',allow_projects=True,confirm_writes=False)
        image=self.media('figura.png','image/png');source=self.save(chat,'Figura',media=[image]);steps=[0];calls=[0]
        def choose(messages,*args,**kwargs):
            if 'action' not in (kwargs.get('schema') or {}).get('properties',{}):calls[0]+=1;return 'Una porta logica AND con due ingressi e una uscita.','stop'
            data=json.loads(messages[-1]['content']);steps[0]+=1
            if steps[0]==1:return decision('ensure_project',{'name':'Figure'})
            ident=json.loads(data['observations'][0]['data'])['project_id']
            if steps[0]==2:return decision('catalog_images',{'artifact_id':source['id'],'numbers':[1]})
            if steps[0]==3:return decision('import_project_files',{'project_id':ident,'artifact_id':source['id'],'numbers':[1]})
            if steps[0]==4:return decision('index_project',{'project_id':ident,'embedding_id':'lexical','visual':False})
            return decision('finish')
        state=self.run_chain(job,choose,vision=True);self.assertEqual(calls[0],1)
        rows=self.app.store.all('SELECT text,image_path FROM rag_chunks WHERE source_id IN (SELECT id FROM project_sources WHERE project_id=?)',(state['active_project'],))
        self.assertEqual(len(rows),1);self.assertIn('porta logica AND',rows[0]['text']);self.assertTrue(rows[0]['image_path'].startswith('project-imports/'))
        self.assertTrue(state['actions'][2]['result']['files'][0]['caption_preserved'])

    def test_missing_embedding_is_reported_without_download_and_defaults_unchanged(self):
        chat,job=self.ticket('agent: Usa modello inesistente',allow_projects=True,confirm_writes=False,max_steps=4)
        project=self.app.knowledge.save({'name':'Destinazione'});steps=[0];original=self.app.store.settings()
        def choose(*args,**kwargs):
            steps[0]+=1
            return decision('index_project',{'project_id':project['id'],'embedding_id':'not-installed'}) if steps[0]==1 else decision('finish',message='Modello non disponibile.')
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=choose),patch.object(self.app.knowledge,'index') as index:
            self.app.execute_job(job,threading.Event())
        index.assert_not_called();state=load(self.app,chat,job['id']);self.assertEqual(state['actions'][0]['status'],'failed');self.assertIn('Nessun download',state['actions'][0]['error'])
        self.assertEqual(self.app.store.settings(),original)

    def test_permission_and_schema_reject_paths_and_implicit_project_changes(self):
        for name in ('ensure_project','import_project_files','index_project','catalog_images'):
            with self.subTest(name=name),self.assertRaises(PermissionError):permission({'allow_projects':False},name,{})
        for name,args in [('import_project_files',{'project_id':'a'*32,'numbers':[1],'path':'C:/private.txt'}),('index_project',{'project_id':'a'*32,'embedding_path':'C:/weights.gguf'})]:
            with self.assertRaises(ValueError):validate(name,args)

    def test_existing_project_is_reused_without_overwriting_instructions(self):
        chat,job=self.ticket('agent: Trova il progetto',allow_projects=True,confirm_writes=False)
        existing=self.app.knowledge.save({'name':'Logica','instructions':'Istruzioni originali'});step=[0]
        def choose(*a,**kw):step[0]+=1;return decision('ensure_project',{'name':'LOGICA','instructions':'Non sovrascrivere'}) if step[0]==1 else decision('finish')
        state=self.run_chain(job,choose)
        self.assertFalse(state['actions'][0]['result']['created']);self.assertEqual(self.app.knowledge.project(existing['id'])['instructions'],'Istruzioni originali')
        self.assertEqual(len(self.app.knowledge.list()),1)

    def test_embedding_choice_is_used_for_index_and_next_search_without_global_change(self):
        chat,job=self.ticket('agent: Indicizza e cerca con il modello scelto',allow_projects=True,confirm_writes=False)
        project=self.app.knowledge.save({'name':'Ricerche'});folder=self.app.data/'project-imports'/'fixture';folder.mkdir(parents=True)
        source=folder/'testo.txt';source.write_text('Una porta XOR confronta due ingressi.',encoding='utf8')
        self.app.store.execute('INSERT INTO project_sources(id,project_id,path,name) VALUES (?,?,?,?)',('d'*32,project['id'],str(source),'Testo'))
        payload=json.loads(job['payload']);payload['settings']['_rag']=True;job['payload']=json.dumps(payload)
        self.app.store.execute('UPDATE jobs SET payload=? WHERE id=?',(job['payload'],job['id']))
        step=[0];seen=[];before=self.app.store.settings()
        def choose(*a,**kw):
            step[0]+=1
            if step[0]==1:return decision('index_project',{'project_id':project['id'],'embedding_id':'chosen'})
            if step[0]==2:return decision('project_search',{'query':'XOR ingressi'})
            return decision('finish')
        def key(settings):seen.append(settings['rag_embedding_model']);return 'embedding-test-key'
        choices={'chosen':{'name':'Embedding fixture','profile':'plain','path':'private-chosen.gguf','available':True}}
        with patch('h3chat.agent_knowledge_tools.model_options',return_value=choices),patch.object(self.app.knowledge.embeddings,'key',side_effect=key),patch.object(self.app.knowledge.embeddings,'encode_items',side_effect=lambda items,*a:[[1.0]+[0.0]*7 for _ in items]),patch.object(self.app.knowledge.embeddings,'encode',return_value=[[1.0]+[0.0]*7]):
            state=self.run_chain(job,choose)
        self.assertTrue(seen);self.assertEqual(set(seen),{'private-chosen.gguf'});self.assertEqual(state['actions'][0]['result']['ready'],1)
        self.assertEqual(self.app.store.settings(),before);self.assertIn('XOR',state['actions'][1]['result']['sources'][0]['text'])

if __name__=='__main__':unittest.main()
