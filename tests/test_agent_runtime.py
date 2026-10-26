"""Agent decisions and H3 tools in isolated stores, with no real inference."""
import json
import threading
import unittest
from unittest.mock import patch
import test_visual_models as fixture
from h3chat import agent_state as ledger
from h3chat.agent_tools import validate,execute

def decision(tool,args=None,message='Passaggio',plan=None):
    return json.dumps({'action':tool,'arguments':json.dumps(args or {}),'plan':plan or ['Prepara','Controlla'],'message':message}),'stop'

class AgentTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown

    def test_preparation_advisors_share_budget_and_never_execute_tools(self):
        chat,job=self.ticket(prompt='agent: Prepara una risposta semplice',planning_agents=3,confirm_writes=False)
        calls=[]
        def complete(messages,settings,cancel,**kw):
            calls.append(kw['schema'])
            if 'summary' in kw['schema']['properties']:return json.dumps({'summary':'Conserva i requisiti espliciti.','checks':['Verifica il risultato.']}),'stop'
            data=json.loads(messages[-1]['content']);self.assertTrue(data['advisory_preparation']['data_only']);self.assertEqual(len(data['advisory_preparation']['advisors']),2)
            return decision('finish',message='Preparazione completata.')
        answer,tool,image=self.run_job(job,complete)
        state=ledger.load(self.app,chat,job['id'])
        self.assertEqual(state['status'],'done',answer['meta']);self.assertEqual(state['usage']['llm_calls'],3)
        self.assertEqual(state['actions'],[]);self.assertEqual(len(state['preparation']),2);tool.assert_not_called();image.assert_not_called()

    def test_preparation_resume_keeps_completed_advice_and_the_same_budget(self):
        chat,job=self.ticket(prompt='agent: Prepara una risposta semplice',planning_agents=3,max_calls=1)
        def complete(messages,settings,cancel,**kw):
            if 'summary' in kw['schema']['properties']:return json.dumps({'summary':'Contributo salvato.','checks':[]}), 'stop'
            return decision('finish',message='Fatto.')
        self.run_job(job,complete);state=ledger.load(self.app,chat,job['id']);self.assertEqual(state['status'],'paused');self.assertEqual(len(state['preparation']),1)
        result=ledger.resume(self.app,chat,job['id'],{'limits':{'max_calls':5}})
        next_job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(result['job_id'],));self.run_job(next_job,complete)
        state=ledger.load(self.app,chat,job['id']);self.assertEqual(state['status'],'done');self.assertEqual(len(state['preparation']),2);self.assertEqual(state['usage']['llm_calls'],3)

    def test_agent_preferences_do_not_store_computer_access_grants(self):
        saved=self.app.save_settings({'agent_defaults':{'max_steps':28,'planning_agents':3}})
        self.assertEqual(saved['agent_defaults']['planning_agents'],3)
        for value in ({'planning_agents':5},{'scope':'global','grant_id':'a'*32}):
            with self.assertRaises(ValueError):self.app.save_settings({'agent_defaults':value})

    def ticket(self,prompt='agent: Crea due slide e controlla il layout',**options):
        self.app.save_settings({'context':32768,'max_tokens':3000})
        chat=self.app.store.create_chat()['id']
        result=self.app.send(chat,{'prompt':prompt,'agent':options,'rag':False})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(result['job_id'],))
        return chat,job

    def run_job(self,job,completion,cancel=None,layout=None):
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=completion),patch.object(self.app.engine,'tool_call',return_value=layout or {'pages':[{'issue':False,'out_of_bounds':[]}]}) as tool,patch.object(self.app.engine,'generate') as image:
            self.app.execute_job(job,cancel or threading.Event())
        answer=self.app.store.one('SELECT * FROM messages WHERE id=?',(job['message_id'],))
        return answer,tool,image

    def test_real_loop_creates_observes_revises_and_finishes_one_answer(self):
        chat,job=self.ticket(confirm_writes=False)
        n=[0];pages=[0]
        def completion(messages,settings,cancel,**kw):
            properties=(kw.get('schema') or {}).get('properties',{})
            if 'action' in properties:
                n[0]+=1;data=json.loads(messages[-1]['content'])
                if n[0]==1:return decision('create_slides',{'prompt':'Crea 2 slide sulle porte logiche','count':2})
                ident=data['artifacts'][-1]['id']
                if n[0]==2:return decision('inspect_slides',{'artifact_id':ident,'pages':[1]})
                if n[0]==3:
                    self.assertTrue(data['observations'][-1]['data'])
                    return decision('revise_slide',{'artifact_id':ident,'page':1,'prompt':'Cambia la disposizione, sposta il titolo in alto'})
                if n[0]==4:return decision('inspect_slides',{'artifact_id':ident,'pages':[1]})
                return decision('finish',message='Presentazione creata e controllata.')
            if 'slides' in properties:return json.dumps({'title':'Logica','visual_direction':'Diagrammi','slides':[{'title':'AND','purpose':'Congiunzione'},{'title':'OR','purpose':'Disgiunzione'}]}),'stop'
            if 'content' in properties:return json.dumps({'content':'Spiega il valore di ingresso e di uscita','visual_plan':'Diagramma','notes':'Note complete','sources':[]}),'stop'
            pages[0]+=1
            return f'<style>body{{font:36px Arial;background:white}}h1{{margin:{pages[0]*20}px}}</style><h1>Pagina {pages[0]}</h1><p>Contenuto completo</p>','stop'
        answer,tool,image=self.run_job(job,completion)
        self.assertEqual(answer['status'],'done',answer['meta'])
        state=ledger.load(self.app,chat,job['id']);self.assertEqual(state['status'],'done')
        self.assertEqual([a['tool'] for a in state['actions']],['create_slides','inspect_slides','revise_slide','inspect_slides'])
        self.assertEqual(len(state['artifacts']),2);self.assertEqual(tool.call_count,2);image.assert_not_called()
        self.assertTrue(all(a['status']=='done' for a in state['actions']),state['actions'])
        for item in state['artifacts']:
            saved=self.app.store.canvas_history.get(chat,item['id']);self.assertIn('Pagina',saved['content']);self.assertNotIn('interrupted',saved['content'])
        self.assertEqual(len(self.app.store.canvas_history.listing(chat)['items']),2)
        self.assertEqual(len(self.app.store.all("SELECT * FROM messages WHERE chat_id=? AND role='assistant'",(chat,))),1)
        self.assertGreater(state['usage']['llm_calls'],5)

    def test_approval_is_concrete_explicit_and_not_duplicated(self):
        chat,job=self.ticket()
        answer,tool,image=self.run_job(job,lambda *a,**kw:decision('create_slides',{'prompt':'Crea 2 slide','count':2}))
        state=ledger.load(self.app,chat,job['id']);self.assertEqual(state['status'],'awaiting_approval')
        image.assert_not_called();self.assertEqual(self.app.store.canvas_history.listing(chat)['items'],[])
        action=state['actions'][-1]
        with self.assertRaises(ValueError):ledger.resume(self.app,chat,job['id'],{'decision':'approve','action_id':'wrong'})
        result=ledger.resume(self.app,chat,job['id'],{'decision':'approve','action_id':action['id']})
        again=ledger.resume(self.app,chat,job['id'],{'decision':'approve','action_id':action['id']})
        self.assertEqual(result['job_id'],again['job_id'])
        queued=self.app.store.one('SELECT payload FROM jobs WHERE id=?',(result['job_id'],))
        self.assertEqual(json.loads(queued['payload'])['settings']['_agent']['approval'],action['id'])

    def test_second_slide_request_overrides_a_zero_based_llm_choice_before_approval(self):
        from h3chat.slides import encode,PREFIX
        chat,job=self.ticket('agent: Modifica la seconda slide: cambia i colori.',confirm_writes=False)
        deck={'version':1,'engine':'llm','format':'16:9','title':'Logica','pages':[
            {'title':'Prima','status':'ready','html':'<main>Prima invariata</main><style>main{color:red}</style>'},
            {'title':'Seconda','status':'ready','html':'<main>Seconda originale</main><style>main{color:red}</style>'}]}
        original=self.app.store.canvas_history.save(chat,{'title':'Logica','content':encode(deck),'media':[]})
        choices=[0]
        def completion(messages,settings,cancel,**kw):
            if 'action' in (kw.get('schema') or {}).get('properties',{}):
                choices[0]+=1
                return decision('revise_slide',{'artifact_id':original['id'],'page':1,'prompt':'Usa il blu'}) if choices[0]==1 else decision('finish')
            self.assertIn('SOLO alla pagina 2/2',messages[-1]['content'])
            return '<main>Seconda blu</main><style>main{color:blue}</style>','stop'
        self.run_job(job,completion)
        state=ledger.load(self.app,chat,job['id']);self.assertEqual(state['status'],'done',state)
        self.assertEqual(state['actions'][0]['arguments']['page'],2)
        self.assertEqual(state['actions'][0]['page_binding'],{'human_page':2,'model_page':1})
        result=self.app.store.canvas_history.get(chat,state['artifacts'][-1]['id'])
        changed=json.loads(result['content'][len(PREFIX):-4])
        self.assertEqual(changed['pages'][0],deck['pages'][0])
        self.assertIn('Seconda blu',changed['pages'][1]['html'])

    def test_rejection_cannot_be_overridden_by_resume(self):
        chat,job=self.ticket();self.run_job(job,lambda *a,**kw:decision('create_slides',{'prompt':'Crea 2 slide'}))
        state=ledger.load(self.app,chat,job['id']);action=state['actions'][0]
        ledger.resume(self.app,chat,job['id'],{'decision':'reject','action_id':action['id']})
        with self.assertRaisesRegex(ValueError,'rifiutata'):ledger.resume(self.app,chat,job['id'],{})

    def test_cross_chat_and_unknown_tools_are_rejected(self):
        chat,job=self.ticket('agent: Elenca i risultati')
        other=self.app.store.create_chat()['id']
        with self.assertRaises(ValueError):ledger.load(self.app,other,job['id'])
        for tool,args in [('shell',{'command':'dir'}),('read_artifact',{'artifact_id':'x','path':'C:/secret'}),('project_search',{'query':'x','database_path':'other'})]:
            with self.assertRaises(ValueError):validate(tool,args)
        answer,_,_=self.run_job(job,lambda *a,**kw:decision('read_artifact',{'artifact_id':'a'*32}))
        state=ledger.load(self.app,chat,job['id']);self.assertNotEqual(state['status'],'done')
        self.assertTrue(all(a['status']=='failed' for a in state['actions']))

    def test_budget_and_stop_end_the_loop_without_following_tools(self):
        chat,job=self.ticket('agent: Elenca gli artefatti',max_steps=1)
        answer,_,_=self.run_job(job,lambda *a,**kw:decision('list_artifacts'))
        state=ledger.load(self.app,chat,job['id']);self.assertEqual(state['status'],'paused');self.assertEqual(state['step'],1)
        ticket=ledger.resume(self.app,chat,job['id'],{'limits':{'max_steps':3}})
        resumed=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));cancel=threading.Event()
        def stop(*a,**kw):cancel.set();return decision('create_slides',{'prompt':'Crea slide'})
        self.run_job(resumed,stop,cancel)
        state=ledger.load(self.app,chat,job['id']);self.assertEqual(state['status'],'stopped');self.assertEqual(len(state['actions']),1)

    def test_identical_write_reuses_result(self):
        chat,job=self.ticket('agent: Crea slide',confirm_writes=False,max_steps=4)
        calls=[0]
        def choose(*a,**kw):
            calls[0]+=1
            return decision('finish') if calls[0]>=3 else decision('create_slides',{'prompt':'Crea una slide'})
        with patch('h3chat.agent_tools.execute',return_value={'saved':True,'id':'a'*32}) as action:
            self.run_job(job,choose)
        state=ledger.load(self.app,chat,job['id']);self.assertEqual(action.call_count,1);self.assertEqual(state['actions'][-1]['status'],'reused')

    def test_token_budget_blocks_before_call_and_human_can_extend(self):
        chat,job=self.ticket('agent: Elenca gli artefatti',token_budget=8000)
        calls=[]
        self.run_job(job,lambda *a,**kw:calls.append(1) or decision('finish'))
        state=ledger.load(self.app,chat,job['id']);self.assertEqual(state['status'],'paused');self.assertEqual(calls,[])
        resumed=ledger.resume(self.app,chat,job['id'],{'limits':{'token_budget':500000}})
        self.run_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(resumed['job_id'],)),lambda *a,**kw:decision('finish'))
        self.assertEqual(ledger.load(self.app,chat,job['id'])['status'],'done')

    def test_interrupted_write_requires_explicit_adoption_and_is_not_repeated(self):
        from h3chat.downloads import Cancelled
        chat,job=self.ticket('agent: Crea slide',confirm_writes=False)
        stop=threading.Event()
        def partial(ctx,tool,args):
            ctx.tool_app.save_artifact(chat,'Parziale','Bozza conservata',[]);stop.set();raise Cancelled()
        with patch('h3chat.agent_tools.execute',side_effect=partial):
            self.run_job(job,lambda *a,**kw:decision('create_slides',{'prompt':'Crea slide'}),stop)
        state=ledger.load(self.app,chat,job['id']);self.assertEqual(state['status'],'uncertain');self.assertEqual(len(state['artifacts']),1)
        with self.assertRaisesRegex(ValueError,'interrotto'):ledger.resume(self.app,chat,job['id'],{})
        ticket=ledger.resume(self.app,chat,job['id'],{'decision':'keep_partial'})
        with patch('h3chat.agent_tools.execute') as tool:
            self.run_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],)),lambda *a,**kw:decision('finish',message='Conservato il risultato parziale.'))
        tool.assert_not_called();self.assertEqual(ledger.load(self.app,chat,job['id'])['actions'][0]['status'],'failed')

    def test_restart_projection_and_permission_scope(self):
        chat,job=self.ticket('agent: Elenca gli artefatti',max_steps=1)
        self.run_job(job,lambda *a,**kw:decision('list_artifacts'))
        state=ledger.load(self.app,chat,job['id']);state['status']='running';ledger.save(self.app,state)
        self.app.store.execute("UPDATE jobs SET status='interrupted' WHERE id=?",(job['id'],))
        self.assertEqual(ledger.load(self.app,chat,job['id'])['status'],'interrupted')
        with self.assertRaisesRegex(ValueError,'permessi'):ledger.resume(self.app,chat,job['id'],{'limits':{'allow_images':True}})
        wrong=self.app.store.create_chat()['id']
        with self.assertRaises(ValueError):ledger.resume(self.app,wrong,job['id'],{})

    def test_initial_submission_key_prevents_duplicate_run(self):
        self.app.save_settings({'context':32768,'max_tokens':2200});chat=self.app.store.create_chat()['id']
        body={'prompt':'agent: Elenca i lavori','rag':False,'agent_request_id':'d'*32}
        first=self.app.send(chat,body);second=self.app.send(chat,body)
        self.assertEqual(first['job_id'],second['job_id']);self.assertTrue(second['reused'])
        with self.assertRaisesRegex(ValueError,'differente'):self.app.send(chat,body|{'prompt':'agent: Altro compito'})

    def test_classic_assistant_mode_stays_separate(self):
        self.assertFalse(ledger.requested('Spiegami come funziona un agent: con strumenti'))
        chat=self.app.store.create_chat()['id'];ticket=self.app.send(chat,{'prompt':'Spiegami la porta AND','assistant':True,'lab':'auto','rag':False})
        job=self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ticket['job_id'],));settings=json.loads(job['payload'])['settings']
        self.assertNotIn('_agent',settings);self.assertTrue(settings['_assistant']);self.assertNotEqual(ticket['intent'],'agent')

if __name__=='__main__':unittest.main()
