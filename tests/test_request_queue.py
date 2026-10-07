import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from h3chat.service import Service
from h3chat.store import DEFAULTS
from h3chat.workspaces import Workspaces

ROOT=Path(__file__).resolve().parents[1]


class QueueTests(unittest.TestCase):
    def test_one_request_per_user_across_chats_atomic_and_stop_frees_slot(self):
        with tempfile.TemporaryDirectory() as folder:
            app=Service(ROOT,folder,start_worker=False)
            try:
                chats=[app.store.create_chat()['id'] for _ in range(2)];barrier=threading.Barrier(2);accepted=[];rejected=[]
                def submit(chat):
                    barrier.wait()
                    try:accepted.append(app.store.enqueue(chat,'Hello',[],DEFAULTS))
                    except ValueError as error:rejected.append(str(error))
                threads=[threading.Thread(target=submit,args=(chat,)) for chat in chats]
                for thread in threads:thread.start()
                for thread in threads:thread.join(5)
                self.assertEqual(len(accepted),1);self.assertEqual(len(rejected),1)
                with self.assertRaises(ValueError):app.store.regenerate(chats[1])
                app.cancel(accepted[0]);next_job=app.store.enqueue(chats[1],'Next',[],DEFAULTS)
                self.assertEqual(app.store.one('SELECT status FROM jobs WHERE id=?',(next_job,))['status'],'queued')
            finally:app.close()

    def app(self,compute,ident,callback):
        return SimpleNamespace(compute_lock=compute,knowledge=SimpleNamespace(embeddings=Mock()),engine=Mock(),current_id=None,
            store=SimpleNamespace(execute=Mock(),settings=lambda:{'rag_device':'cpu'},enqueue=lambda *args,**kwargs:ident,regenerate=lambda *args:ident),
            execute_job=callback,cancel=lambda ident:{'ok':True})

    def test_fifo_is_submission_order_even_when_worker_threads_start_in_reverse(self):
        compute=threading.RLock();order=[];entered=threading.Event();finish=threading.Event()
        def first(job,cancel):order.append('a');entered.set();finish.wait(5)
        apps=[self.app(compute,'a',first),self.app(compute,'b',lambda *args:order.append('b')),self.app(compute,'c',lambda *args:order.append('c'))]
        spaces=Workspaces(apps[0],start_workers=False)
        for ident,app in zip(('b','c'),apps[1:]):spaces.items[ident]=app;spaces.wrap(app)
        for app in apps:app.store.enqueue('chat','request',[],{})
        threads=[threading.Thread(target=app.execute_job,args=({'id':ident},threading.Event())) for app,ident in zip(apps,('a','b','c'))]
        threads[2].start();threads[1].start();threads[0].start()
        self.assertTrue(entered.wait(3));self.assertEqual(order,['a']);finish.set()
        for thread in threads:thread.join(3)
        self.assertEqual(order,['a','b','c']);self.assertEqual(spaces.pending,[])

    def test_stopping_request_before_worker_claim_does_not_block_following_user(self):
        compute=threading.RLock();order=[]
        owner=self.app(compute,'a',lambda *args:order.append('a'));guest=self.app(compute,'b',lambda *args:order.append('b'))
        spaces=Workspaces(owner,start_workers=False);spaces.items['b']=guest;spaces.wrap(guest)
        owner.store.enqueue();guest.store.enqueue();owner.cancel('a')
        thread=threading.Thread(target=guest.execute_job,args=({'id':'b'},threading.Event()));thread.start();thread.join(3)
        self.assertFalse(thread.is_alive());self.assertEqual(order,['b']);self.assertEqual(spaces.pending,[])


if __name__=='__main__':unittest.main()
