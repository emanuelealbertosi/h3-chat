import copy,json,threading,unittest
from unittest.mock import patch
from h3chat import study
from test_visual_models import VisualModelsTests as _Fixture

SOURCE='La fotosintesi utilizza luce, acqua e anidride carbonica. Le piante producono ossigeno e zuccheri. Nel 1771 Priestley studiò gli scambi gassosi delle piante.'

def completion(messages,settings,cancel,**kw):
    count=kw['schema']['properties']['items']['minItems'];value=json.loads(messages[1]['content']);prior=value['posizione_iniziale']-1;source=value['fonti'][0]
    assert value['numero_elementi_di_questa_risposta']==count
    dialogue='Tipo: dialogue' in value['richiesta'];passage=source['passaggi'][0]['id']
    return json.dumps({'title':'Studiamo le piante','items':[{'question':('Conduttore A' if (prior+i)%2==0 else 'Conduttore B') if dialogue else f'Quale concetto botanico {prior+i+1}?','answer':'Le piante producono ossigeno e zuccheri.'+(f' Battuta {prior+i+1}.' if dialogue else ''),'citations':[{'source':source['id'],'passage':passage}]} for i in range(count)]}),'stop'

class StudyTests(unittest.TestCase):
    setUp=_Fixture.setUp
    tearDown=_Fixture.tearDown
    def launch(self,**values):
        self.app.save_settings({'context':32768,'max_tokens':8000})
        chat=self.app.store.create_chat('Studio')['id'];ticket=self.app.send(chat,{'prompt':'Prepara schede dalle fonti','lab':'study','study':{'source_text':SOURCE,**values},'rag':False})
        return chat,self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))
    def execute(self,job,cancel=None,complete=completion):
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'prepare_tools',side_effect=lambda h,*a,**k:(h,{},[],[])),patch.object(self.app.engine,'completion',side_effect=complete):self.app.execute_job(job,cancel or threading.Event())
    def test_batches_are_saved_grounded_and_all_kinds_work(self):
        for kind in study.KINDS:
            chat,job=self.launch(kind=kind,count=7);self.execute(job)
            self.assertEqual(self.app.store.one('SELECT status,error FROM jobs WHERE id=?',(job['id'],))['status'],'done')
            value=self.app.store.canvas_history.get(chat);deck=study.decode(value['content']);self.assertEqual(len(deck['items']),7);self.assertEqual(deck['status'],'ready')
            self.assertEqual(deck['sources'][0]['text'],SOURCE);self.assertIn('Fronte',study.csv_export(deck))
    def test_invalid_citations_are_repaired_once_and_rejected(self):
        chat,job=self.launch(count=1);calls=[]
        def invalid(*args,**kw):
            calls.append(1);raw,finish=completion(*args,**kw);v=json.loads(raw);v['items'][0]['citations'][0]={'source':'S1','quote':'Un fatto che la fonte non riporta'};return json.dumps(v),finish
        self.execute(job,complete=invalid);self.assertEqual(len(calls),2)
        row=self.app.store.one('SELECT status,error FROM jobs WHERE id=?',(job['id'],));self.assertEqual(row['status'],'failed');self.assertIn('citazione',row['error'])
        self.assertFalse(self.app.store.canvas_history.get(chat).get('content'))
    def test_batch_count_and_previous_items_are_explicit_and_dialogue_hosts_can_repeat(self):
        seen=[]
        def inspected(messages,*args,**kw):
            value=json.loads(messages[1]['content']);seen.append(value)
            return completion(messages,*args,**kw)
        chat,job=self.launch(kind='dialogue',count=7);self.execute(job,complete=inspected)
        deck=study.decode(self.app.store.canvas_history.get(chat)['content'])
        self.assertEqual([v['numero_elementi_di_questa_risposta'] for v in seen],[5,2]);self.assertEqual([v['posizione_iniziale'] for v in seen],[1,6])
        self.assertEqual(seen[1]['gia_creati'],[{'question':i['question'],'answer':i['answer']} for i in deck['items'][:5]])
        self.assertEqual([i['question'] for i in deck['items']],['Conduttore A','Conduttore B','Conduttore A','Conduttore B','Conduttore A','Conduttore B','Conduttore A']);self.assertEqual(len({i['answer'] for i in deck['items']}),7)
    def test_passage_ids_are_resolved_to_exact_original_text(self):
        chat,job=self.launch(count=1);self.execute(job)
        deck=study.decode(self.app.store.canvas_history.get(chat)['content']);citation=deck['items'][0]['citations'][0]
        self.assertEqual(citation,{'source':'S1','quote':SOURCE});self.assertNotIn('passage',citation)
    def test_unknown_passages_and_source_mismatch_are_rejected_after_one_repair(self):
        sources=[{'id':'S1','name':'Piante','location':'uno','text':SOURCE},{'id':'S2','name':'Seconda fonte','location':'due','text':'Una seconda fonte diversa descrive esclusivamente la respirazione cellulare.'}]
        for citation in ({'source':'S1','passage':'P999'},{'source':'S2','passage':'P1'}):
            calls=[]
            def bad(messages,settings,cancel,**kw):
                calls.append(1);raw,finish=completion(messages,settings,cancel,**kw);value=json.loads(raw);value['items'][0]['citations']=[citation.copy()];return json.dumps(value),finish
            with self.subTest(citation=citation),patch.object(self.app.engine,'completion',side_effect=bad):
                with self.assertRaisesRegex(ValueError,'Passaggio e fonte'):study.generate(self.app,self.app.store.settings(),{},threading.Event(),lambda s:None,sources,'Una flashcard',1)
                self.assertEqual(len(calls),2)
    def test_wrong_item_count_and_duplicate_dialogue_answers_are_rejected(self):
        sources=[{'id':'S1','name':'Piante','location':'uno','text':SOURCE}]
        for mode in ('wrong_count','repeated_answer'):
            calls=[]
            def bad(messages,settings,cancel,**kw):
                calls.append(1);raw,finish=completion(messages,settings,cancel,**kw);value=json.loads(raw)
                if mode=='wrong_count':value['items'].pop()
                else:value['items'][1]['answer']=value['items'][0]['answer']
                return json.dumps(value),finish
            with self.subTest(mode=mode),patch.object(self.app.engine,'completion',side_effect=bad):
                with self.assertRaisesRegex(ValueError,'Numero di schede|duplicato'):study.generate(self.app,self.app.store.settings(),{},threading.Event(),lambda s:None,sources,'Tipo: dialogue',2)
                self.assertEqual(len(calls),2)
    def test_progress_survives_explanation_but_resets_after_content_edit_and_is_chat_scoped(self):
        chat,job=self.launch(count=1);self.execute(job);value=self.app.store.canvas_history.get(chat);deck=study.decode(value['content']);item=deck['items'][0]
        result=study.progress(self.app,chat,value['id'],{'card_id':item['id'],'remembered':True});self.assertEqual(result['items'][item['id']]['attempts'],1)
        ticket=study.explain(self.app,chat,{'artifact_id':value['id'],'card_id':item['id']});explain=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));self.execute(explain)
        latest=self.app.store.canvas_history.get(chat);self.assertIn('explanation',study.decode(latest['content'])['items'][0]);self.assertEqual(study.progress(self.app,chat,latest['id'])['items'][item['id']]['remembered'],1)
        deck['items'][0]['answer']+=' Modifica manuale.';saved=self.app.store.canvas_history.save(chat,{'title':deck['title'],'content':study.encode(deck),'media':[]},edit_id=latest['id'],editable=True)
        self.assertEqual(study.progress(self.app,chat,saved['id'])['items'],{})
        other=self.app.store.create_chat('Altro')['id']
        with self.assertRaises(ValueError):study.loaded(self.app,other,value['id'])
    def test_stop_keeps_completed_batch_and_resume_uses_same_sources(self):
        chat,job=self.launch(count=7);cancel=threading.Event();calls=[]
        def stop(*args,**kw):
            result=completion(*args,**kw);calls.append(1);cancel.set();return result
        self.execute(job,cancel,stop);value=self.app.store.canvas_history.get(chat);deck=study.decode(value['content']);self.assertEqual(len(deck['items']),5)
        ticket=study.resume(self.app,chat,value['id']);job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));self.execute(job)
        latest=study.decode(self.app.store.canvas_history.get(chat)['content']);self.assertEqual(len(latest['items']),7);self.assertEqual(latest['id'],deck['id']);self.assertEqual(latest['sources'],deck['sources'])
    def test_no_sources_never_falls_back_to_general_knowledge(self):
        chat,job=self.launch(source_text='',count=1);self.execute(job)
        row=self.app.store.one('SELECT status,error FROM jobs WHERE id=?',(job['id'],));self.assertEqual(row['status'],'failed');self.assertIn('fonti',row['error'])
    def test_reviews_are_retained_for_each_revision_and_do_not_cross_chats(self):
        chat,job=self.launch(count=1);self.execute(job);original=self.app.store.canvas_history.get(chat);deck=study.decode(original['content']);item=deck['items'][0]
        study.progress(self.app,chat,original['id'],{'card_id':item['id'],'remembered':True})
        revised=copy.deepcopy(deck);revised['items'][0]['answer']+=' Versione corretta.'
        changed=self.app.store.canvas_history.save(chat,{'title':deck['title'],'content':study.encode(revised),'media':[]},edit_id=original['id'],editable=True)
        self.assertEqual(study.progress(self.app,chat,changed['id'])['items'],{})
        study.progress(self.app,chat,changed['id'],{'card_id':item['id'],'remembered':False})
        self.assertEqual(study.progress(self.app,chat,original['id'])['items'][item['id']]['remembered'],1)
        self.assertEqual(study.progress(self.app,chat,original['id'])['items'][item['id']]['attempts'],1)
        other=self.app.store.create_chat('Copia dello Studio')['id']
        copied=self.app.store.canvas_history.save(other,{'title':deck['title'],'content':study.encode(deck),'media':[]},editable=True)
        self.assertEqual(study.progress(self.app,other,copied['id'])['items'],{})
    def test_malformed_nested_imports_raise_validation_error(self):
        chat,job=self.launch(count=1);self.execute(job);deck=study.decode(self.app.store.canvas_history.get(chat)['content'])
        for invalid in (None,'not an explanation',[],123):
            with self.subTest(explanation=invalid):
                imported=copy.deepcopy(deck);imported['items'][0]['explanation']=invalid
                with self.assertRaises(ValueError):study.decode(study.encode(imported))
    def test_real_lexical_rag_preserves_integer_chunk_ids_and_project_provenance(self):
        import base64
        settings=self.app.save_settings({'context':32768,'max_tokens':8000,'rag_embedding_profile':'plain','rag_embedding_model':'','rag_visual':False})
        project=self.app.knowledge.save({'name':'Studio RAG','sources_only':True})
        source=self.app.knowledge.import_file(project['id'],{'name':'piante.txt','data':base64.b64encode(SOURCE.encode()).decode(),'defer':True})
        self.app.knowledge.index(project['id'],settings,threading.Event(),lambda s:None)
        chat=self.app.store.create_chat('Studio sulle piante',project_id=project['id'])['id']
        ticket=self.app.send(chat,{'prompt':'Prepara 1 flashcard sulla fotosintesi delle piante','lab':'study','study':{'count':1},'rag':True})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));self.execute(job)
        self.assertEqual(self.app.store.one('SELECT status,error FROM jobs WHERE id=?',(job['id'],))['status'],'done')
        deck=study.decode(self.app.store.canvas_history.get(chat)['content']);evidence=deck['sources'][0]
        self.assertEqual(deck['project_id'],project['id']);self.assertEqual(evidence['source_id'],source['id']);self.assertIs(type(evidence['chunk_id']),int)
        self.assertIn('fotosintesi',evidence['text']);self.assertIn(deck['items'][0]['citations'][0]['quote'],evidence['text'])
    def test_prompt_override_unknown_ids_truncation_and_invalid_options(self):
        self.assertEqual(study.options('Creami 4 flashcard',{'count':8})['count'],4)
        for value in ({'count':True},{'count':51},{'source_text':'x'*60001},{'kind':'unknown'}):
            with self.assertRaises(ValueError):study.options(value=value)
        chat,job=self.launch(count=1);self.execute(job);deck=study.decode(self.app.store.canvas_history.get(chat)['content']);deck['items'][0]['citations'][0]['source']='S999'
        with self.assertRaises(ValueError):study.validate(deck)

if __name__=='__main__':unittest.main()
