import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from h3chat.store import Store, DEFAULTS
from h3chat.service import Service
from h3chat.request_timing import start, finish

ROOT=Path(__file__).resolve().parents[1]


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
        self.chat=self.store.create_chat()['id']
        ident=self.store.enqueue(self.chat,'Richiesta sintetica',[],DEFAULTS)
        self.store.execute('UPDATE jobs SET created=100 WHERE id=?',(ident,))
        self.job=self.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
        self.wall=110;self.mono=5
        self.clock=patch('h3chat.request_timing.time',SimpleNamespace(time=lambda:self.wall,monotonic=lambda:self.mono))
        self.clock.start()

    def tearDown(self):
        self.clock.stop();self.tmp.cleanup()

    def timing(self):
        return self.store.chat(self.chat)['messages'][-1]['meta'].get('timing')

    def test_streaming_keeps_clock_and_final_time_survives_reopen(self):
        clock=start(self.store,self.job)
        for text,status in (('Prima parte','running'),('Risposta completa','done')):
            self.store.update_answer(self.job,text,status,meta={'intent':'chat','model':'Fixture'})
            self.assertEqual(self.timing()['started_at'],110)
        # Duration is monotonic even if the wall clock moves backwards.
        self.wall=109;self.mono=17.5;finish(self.store,self.job,clock)
        self.assertEqual((self.timing()['elapsed_seconds'],self.timing()['queue_seconds'],self.timing()['total_seconds']),(12.5,10,22.5))
        self.store.execute("UPDATE jobs SET status='done' WHERE id=?",(self.job['id'],))
        reopened=Store(self.tmp.name)
        message=reopened.chat(self.chat)['messages'][-1]
        self.assertEqual(message['content'],'Risposta completa');self.assertEqual(message['meta']['model'],'Fixture')
        self.assertEqual(message['meta']['timing']['elapsed_seconds'],12.5)

    def test_cancelled_queue_has_no_model_time_and_finalization_is_idempotent(self):
        self.wall=125;finish(self.store,self.job)
        self.assertEqual((self.timing()['started_at'],self.timing()['elapsed_seconds'],self.timing()['queue_seconds']),(None,0,25))
        self.wall=150;finish(self.store,self.job)
        self.assertEqual(self.timing()['finished_at'],125)

    def test_regenerate_resets_clock_and_old_finalizer_cannot_restore_it(self):
        clock=start(self.store,self.job)
        self.store.update_answer(self.job,'Prima risposta','done',meta={'intent':'chat'})
        self.store.execute("UPDATE jobs SET status='done' WHERE id=?",(self.job['id'],))
        ident=self.store.regenerate(self.chat)
        self.assertIsNone(self.timing())
        finish(self.store,self.job,clock)
        self.assertIsNone(self.timing())
        new_job=self.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
        new_clock=start(self.store,new_job);self.mono=8;finish(self.store,new_job,new_clock)
        self.assertEqual((self.timing()['job_id'],self.timing()['elapsed_seconds']),(ident,3))


class ServiceTimingTests(unittest.TestCase):
    def test_finalizer_covers_success_failure_and_cancellation_in_real_service(self):
        for outcome in ('done','failed','cancelled'):
            with self.subTest(outcome=outcome),tempfile.TemporaryDirectory() as folder:
                app=Service(ROOT,Path(folder),start_worker=False)
                try:
                    chat=app.store.create_chat()['id']
                    ident=app.store.enqueue(chat,'Test',[],DEFAULTS|{'_api_messages':[{'role':'user','content':'Test'}]})
                    job=app.store.one('SELECT * FROM jobs WHERE id=?',(ident,));cancel=threading.Event()
                    def complete(*args,**kwargs):
                        kwargs['on_text']('Risposta parziale')
                        self.assertIn('started_at',app.store.chat(chat)['messages'][-1]['meta']['timing'])
                        if outcome=='failed':raise RuntimeError('Errore sintetico')
                        if outcome=='cancelled':
                            from h3chat.downloads import Cancelled
                            cancel.set();raise Cancelled()
                        return 'Risposta finale','stop'
                    with patch.object(app.engine,'require_model',return_value={'name':'Fixture'}),patch.object(app.engine,'start_llama'),patch.object(app.engine,'completion',side_effect=complete),patch.object(app.engine,'abort_active'):
                        app.execute_job(job,cancel)
                    message=app.store.chat(chat)['messages'][-1]
                    self.assertEqual(message['status'],outcome)
                    self.assertGreaterEqual(message['meta']['timing']['elapsed_seconds'],0)
                    self.assertIsNotNone(message['meta']['timing']['finished_at'])
                    self.assertEqual(message['meta']['intent'],'chat')
                finally:app.close()

    def test_cancel_before_execution_records_wait_and_releases_user_slot(self):
        with tempfile.TemporaryDirectory() as folder:
            app=Service(ROOT,Path(folder),start_worker=False)
            try:
                chat=app.store.create_chat()['id'];ident=app.store.enqueue(chat,'In coda',[],DEFAULTS)
                app.cancel(ident)
                message=app.store.chat(chat)['messages'][-1]
                self.assertEqual(message['status'],'cancelled')
                self.assertIsNone(message['meta']['timing']['started_at'])
                self.assertEqual(message['meta']['timing']['elapsed_seconds'],0)
                self.assertTrue(app.store.enqueue(chat,'Prossima richiesta',[],DEFAULTS))
            finally:app.close()
