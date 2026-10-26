"""Durable Agent→H3 video handoff, no GPU inference or production database."""
import json
import threading
import unittest
from unittest.mock import patch
from test_agent_runtime import AgentTests,decision
from test_external_models import safetensors
from h3chat import agent_state as ledger
from h3chat.agent_video_tools import reconcile_pending,reconcile
from h3chat.agent_tools import permission


class VideoAgentTests(unittest.TestCase):
    setUp=AgentTests.setUp
    tearDown=AgentTests.tearDown
    ticket=AgentTests.ticket
    run_job=AgentTests.run_job

    def test_fast_h3_request_keeps_its_profile_during_service_preflight(self):
        files={r:str(safetensors(self.base/('fast-'+r+'.safetensors'))) for r in ('diffusion','llm','vae','audio_vae')}
        model=self.app.external_model({'profile':'fasth3-omni','files':files})
        chat,job=self.ticket('agent: Crea un video FastH3 di prova',allow_video=True,confirm_writes=False)
        self.run_job(job,lambda *a,**k:decision('create_video',{'prompt':'A ceramic teapot on a table','model_id':model['id'],'parameters':{'duration':5,'aspect':'16:9','megapixels':.7,'seed':42}}))
        state=ledger.load(self.app,chat,job['id']);self.assertEqual(state['status'],'awaiting_video',state)
        child=self.app.store.one('SELECT payload FROM jobs WHERE id=?',(state['current_job_id'],))
        settings=json.loads(child['payload'])['settings'];self.assertEqual(settings['video_model'],model['id'])
        from h3chat.video_options import options
        self.assertEqual(options(model,settings,False)['attention'],'vsa')

    def timeline(self):
        files={r:str(safetensors(self.base/('clip-'+r+'.safetensors'))) for r in ('diffusion','llm','vae','audio_vae')}
        self.model=self.app.external_model({'profile':'minimax-h3','files':files})
        self.app.save_settings({'video_model':self.model['id'],'context':32768,'max_tokens':3000})
        from test_video_edit import VideoEditTests
        return VideoEditTests.original(self)

    def test_edit_adapter_preserves_memory_end_frame_and_whole_clip(self):
        chat,source,refs,outputs,parameters=self.timeline()
        ident=self.app.send(chat,{'prompt':'agent: Rigenera il secondo clip intero','rag':False,'agent':{'allow_video':True,'confirm_writes':False}})['job_id']
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
        self.run_job(job,lambda *a,**k:decision('edit_video',{'source':source,'remount':False,'patches':[
            {'clip':2,'prompt':'Preserva il personaggio, nuova luce','recover_memory':True,'end_frame':'next'}]}))
        state=ledger.load(self.app,chat,ident);self.assertEqual(state['status'],'awaiting_video',state)
        child=self.app.store.one('SELECT payload FROM jobs WHERE id=?',(state['current_job_id'],))
        recipe=json.loads(child['payload'])['settings']['_video_edit']['patches'][0]
        self.assertTrue(recipe['recover_memory']);self.assertEqual(recipe['end_frame'],'next')
        self.assertEqual(recipe['clip'],2);self.assertNotIn('start',recipe);self.assertNotIn('end',recipe)

    def test_assembly_uses_the_existing_cpu_mount_queue(self):
        chat,source,refs,outputs,parameters=self.timeline()
        path=self.app.data/'outputs'/source/'scenes.json';value=json.loads(path.read_text());value['working_timeline']=True;path.write_text(json.dumps(value))
        ident=self.app.send(chat,{'prompt':'agent: Monta la timeline','rag':False,'agent':{'allow_video':True,'confirm_writes':False}})['job_id']
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
        self.run_job(job,lambda *a,**k:decision('assemble_video',{'source':source}))
        state=ledger.load(self.app,chat,ident);self.assertEqual(state['status'],'awaiting_video',state)
        child=self.app.store.one('SELECT payload FROM jobs WHERE id=?',(state['current_job_id'],))
        settings=json.loads(child['payload'])['settings'];self.assertEqual(settings['_video_assemble'],source)
        self.assertFalse(settings['_assistant']);self.assertNotIn('_agent',settings)

    def begin(self):
        files={r:str(safetensors(self.base/('video-'+r+'.safetensors'))) for r in ('diffusion','llm','vae','audio_vae')}
        model=self.app.external_model({'profile':'minimax-h3','files':files})
        self.app.save_settings({'video_model':model['id']})
        chat,job=self.ticket('agent: Crea tre versioni del video',allow_video=True,confirm_writes=False)
        self.run_job(job,lambda *a,**k:decision('create_video',{'prompt':'Panorama estivo','model_id':model['id'],
            'parameters':{'duration':10,'aspect':'16:9','seed':42,'variants':3,'variants_mode':'clip'}}))
        state=ledger.load(self.app,chat,job['id'])
        self.assertEqual(state['status'],'awaiting_video',state)
        child=self.app.store.one('SELECT * FROM jobs WHERE id=?',(state['current_job_id'],))
        self.assertNotEqual(child['id'],job['id']);self.assertEqual(child['status'],'queued')
        return chat,job,child,state

    def test_handoff_has_real_queue_ticket_and_exact_recipe_and_no_duplicate(self):
        chat,job,child,state=self.begin()
        payload=json.loads(child['payload']);settings=payload['settings']
        self.assertNotIn('_agent',settings);self.assertTrue(settings['_video']);self.assertFalse(settings['_assistant'])
        self.assertEqual(settings['_agent_video_origin'],{'run_id':job['id'],'action_id':state['actions'][0]['id']})
        self.assertEqual(settings['_video_request']['parameters']['seed'],42)
        self.assertEqual(settings['_video_request']['parameters']['variants'],3)
        reconcile_pending(self.app);reconcile_pending(self.app)
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),2)
        with self.assertRaisesRegex(ValueError,'attende il lavoro video'):ledger.resume(self.app,chat,job['id'],{})

    def test_done_resumes_agent_same_budget_and_returns_saved_video(self):
        chat,job,child,state=self.begin();usage=state['usage']['reserved_tokens']
        self.app.store.update_answer(child,'Video pronto','done',meta={'artifact':{'title':'Panorama','content':'','media':[]}})
        self.app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(child['id'],))
        reconcile_pending(self.app)
        resumed=ledger.load(self.app,chat,job['id']);self.assertEqual(resumed['status'],'queued')
        self.assertEqual(resumed['config'],state['config']);self.assertEqual(resumed['usage']['reserved_tokens'],usage)
        self.assertEqual(resumed['usage']['video_jobs_started'],1)
        self.assertEqual(resumed['actions'][0]['result']['job_id'],child['id'])
        reconcile_pending(self.app);self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),3)
        ticket=self.app.store.one('SELECT * FROM jobs WHERE id=?',(resumed['current_job_id'],))
        self.run_job(ticket,lambda *a,**k:decision('finish',message='Video salvato.'))
        final=ledger.load(self.app,chat,job['id']);self.assertEqual(final['status'],'done');self.assertEqual(len(final['artifacts']),1)

    def test_stop_queued_video_stops_agent_without_resume_or_retry(self):
        chat,job,child,state=self.begin();self.app.cancel(child['id'])
        final=ledger.load(self.app,chat,job['id']);self.assertEqual(final['status'],'stopped')
        reconcile_pending(self.app);self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),2)

    def test_stop_from_stale_agent_ticket_cancels_its_real_video(self):
        chat,job,child,state=self.begin();self.app.cancel(job['id'])
        self.assertEqual(self.app.store.one('SELECT status FROM jobs WHERE id=?',(child['id'],))['status'],'cancelled')
        self.assertEqual(ledger.load(self.app,chat,job['id'])['status'],'stopped')
        reconcile_pending(self.app);self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),2)

    def test_stop_during_handoff_never_submits_a_video(self):
        files={r:str(safetensors(self.base/('stop-'+r+'.safetensors'))) for r in ('diffusion','llm','vae','audio_vae')}
        model=self.app.external_model({'profile':'minimax-h3','files':files});self.app.save_settings({'video_model':model['id']})
        chat,job=self.ticket('agent: Crea video',allow_video=True,confirm_writes=False)
        cancel=threading.Event()
        from h3chat import agent_video_tools
        original=agent_video_tools.execute
        def stopped(ctx,name,args):
            try:return original(ctx,name,args)
            finally:cancel.set()
        with patch('h3chat.agent_video_tools.execute',side_effect=stopped):
            self.run_job(job,lambda *a,**k:decision('create_video',{'prompt':'Un panorama'}),cancel=cancel)
        self.assertEqual(ledger.load(self.app,chat,job['id'])['status'],'stopped')
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),1)

    def test_error_stops_agent_and_retains_job(self):
        chat,job,child,state=self.begin()
        self.app.store.execute("UPDATE jobs SET status='failed',error='fixture memory limit' WHERE id=?",(child['id'],))
        reconcile_pending(self.app);final=ledger.load(self.app,chat,job['id'])
        self.assertEqual(final['status'],'failed');self.assertIn('memory limit',final['actions'][0]['error'])
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),2)

    def test_uncertain_submission_does_not_guess_or_retry(self):
        chat,job,child,state=self.begin()
        state['actions'][0]['video'].pop('job_id');state['actions'][0]['video']['phase']='uncertain_submission'
        self.app.store.execute('DELETE FROM jobs WHERE id=?',(child['id'],));ledger.save(self.app,state)
        reconcile(self.app,job['id'],chat)
        final=ledger.load(self.app,chat,job['id']);self.assertEqual(final['status'],'uncertain')
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),1)

    def test_video_permission_and_foreign_source(self):
        with self.assertRaises(PermissionError):permission({},'create_video',{})
        chat,job=self.ticket('agent: Leggi timeline',allow_video=True,confirm_writes=False)
        other=self.app.store.create_chat()['id'];foreign=self.app.store.canvas_history.save(other,{'title':'Video','content':'','media':[]})
        n=[0]
        def completion(*a,**k):
            n[0]+=1
            return decision('inspect_video_timeline',{'source':foreign['id']}) if n[0]==1 else decision('finish')
        self.run_job(job,completion);state=ledger.load(self.app,chat,job['id'])
        self.assertEqual(state['actions'][0]['status'],'failed');self.assertIn('questa chat',state['actions'][0]['error'])
