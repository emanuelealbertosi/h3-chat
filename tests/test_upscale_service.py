"""Use a separate fixture store, never the live application's data."""
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from h3chat.upscale import request
from h3chat import upscale_runtime
import test_video as fixture

class UpscaleServiceTests(unittest.TestCase):
    setUp=fixture.VideoTests.setUp
    tearDown=fixture.VideoTests.tearDown

    def submit(self):
        chat=self.app.store.create_chat()['id'];media={'id':'a'*32,'name':'external.mp4','mime':'video/mp4','path':'uploads/external.mp4'}
        path=self.app.data/media['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\x00\x00\x00\x18ftypisom')
        self.app.store.gallery.register([media])
        with patch.object(upscale_runtime,'ready',return_value=True),patch.object(upscale_runtime,'describe',return_value={'ready':{'base':True}}):
            job=request(self.app,chat,{'media':[{'id':media['id']}]})['job_id']
        return chat,job

    def test_gpu_models_are_released_before_upscale_and_no_router_or_rag_runs(self):
        chat,job=self.submit();order=[]
        def call(worker,body,*args,**kw):
            order.append('upscale');self.assertEqual(order,['unload','upscale']);self.assertEqual(worker,'upscale-worker.py')
            Path(body['output']).write_bytes(b'\x00\x00\x00\x18ftypisom')
            return {'path':body['output'],'width':128,'height':96,'frames':48,'duration':2,'audio_preserved':True}
        with patch.object(self.app.engine,'stop',side_effect=lambda:order.append('unload')),patch.object(self.app.engine,'tool_call',side_effect=call),patch.object(self.app.engine,'route') as router,patch.object(self.app.knowledge,'retrieve') as rag:
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(job,)),threading.Event())
        router.assert_not_called();rag.assert_not_called()
        answer=self.app.store.chat(chat)['messages'][-1];self.assertEqual(answer['status'],'done',answer['meta'])
        self.assertEqual(self.app.store.one('SELECT status FROM jobs WHERE id=?',(job,))['status'],'done')
        self.assertTrue(self.app.store.gallery.get(job));self.assertNotIn('generation',answer['media'][0])

    def test_repeated_recovery_keeps_the_original_chunk_cache(self):
        chat,job=self.submit();path=self.app.data/'outputs'/job/'upscale/checkpoint.json';path.parent.mkdir(parents=True);path.write_text('{}')
        self.app.store.execute("UPDATE jobs SET status='failed' WHERE id=?",(job,))
        first=self.app.regenerate(chat)['job_id']
        self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(first,))
        second=self.app.regenerate(chat)['job_id']
        for ident in (first,second):
            payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ident,))['payload'])
            self.assertEqual(payload['settings']['_upscale_resume'],job)

if __name__=='__main__':unittest.main()
