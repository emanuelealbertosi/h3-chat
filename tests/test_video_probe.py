import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from h3chat.video_probe import request,render


class VideoProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.data=Path(self.temp.name);self.origin='a'*32
        self.payload={'settings':{'video_model':'original','video_overrides':{'original':{'seed':734}},
            '_video_edit':{'source':'c'*32,'versions':{'1':'original'},'patches':[{'clip':1,'mode':'video','images':[3]}]}},
            'media':[{'id':str(i),'path':f'image-{i}.png','mime':'image/png'} for i in range(3)]+[{'id':'audio','path':'audio.wav','mime':'audio/wav'}]}
        folder=self.data/'outputs'/self.origin/'scene-001';folder.mkdir(parents=True)
        (folder/'video-plan.json').write_text(json.dumps({'plan':{'prompt':'Saved plan','images':[{'index':1,'role':'reference','seconds':0}],
            'audios':[{'index':1,'role':'reuse','start':0}]},'parameters':{'attention':'veda','attention_chunks':8,'aspect':'16:9','seed':734}}))
        store=SimpleNamespace(chat=Mock(),one=Mock(return_value={'id':self.origin,'payload':json.dumps(self.payload)}),
            enqueue=Mock(return_value='b'*32),update_answer=Mock(),execute=Mock())
        session=Mock();session.wait.return_value={'parameters':{'completed_blocks':1,'report':'report.json'}}
        engine=SimpleNamespace(require_model=Mock(return_value={'id':'original','name':'Original'}),start_video=Mock(return_value=session),stop=Mock())
        self.app=SimpleNamespace(data=self.data,store=store,lock=threading.RLock(),wake=threading.Event(),engine=engine)
        self.session=session

    def tearDown(self):self.temp.cleanup()

    def test_queues_fresh_diagnostic_without_mutating_or_resuming_cancelled_job(self):
        result=request(self.app,'chat',{'source_job':self.origin,'head_chunks':56})
        self.assertEqual(result['job_id'],'b'*32)
        settings=self.app.store.enqueue.call_args.args[3]
        self.assertNotIn('_video_edit',settings);self.assertNotIn('_video_resume',settings)
        self.assertEqual(settings['video_overrides'],self.payload['settings']['video_overrides'])
        self.assertEqual(settings['_video_probe'],{'source_job':self.origin,'head_chunks':56})
        self.assertTrue(self.app.wake.is_set())
        for body in ({'source_job':'../bad','head_chunks':8},{'source_job':self.origin,'head_chunks':1},{'source_job':self.origin,'head_chunks':8,'code':'bad'}):
            with self.assertRaises(ValueError):request(self.app,'chat',body)

    def test_only_selected_reference_is_sent_and_worker_stops_after_diagnostic_event(self):
        settings=copy.deepcopy(self.payload['settings']);settings['_video_probe']={'source_job':self.origin,'head_chunks':56}
        with patch('h3chat.video_edit.source',return_value={}),patch('h3chat.video_edit.source_interval',return_value={'path':'source.mp4','frames':360,'start':0,'megapixels':.7}),patch('h3chat.video_versions.choices',return_value={}),patch('h3chat.video_versions.apply'):
            render(self.app,{'id':'b'*32,'chat_id':'chat'},{},settings,threading.Event(),Mock(),self.data/'log')
        sent=self.session.send.call_args.args[0]
        self.assertEqual(sent['images'],[str(self.data/'image-2.png')])
        self.assertEqual(sent['audios'],[str(self.data/'audio.wav')])
        self.assertEqual(sent['options']['attention_chunks'],56)
        self.assertEqual(sent['options']['seed'],734)
        self.assertEqual(json.loads((self.data/'outputs'/('b'*32)/'sampling-diagnostics.json').read_text()),{'first_block_probe':True})
        self.assertEqual(self.session.wait.call_args.args[0],'diagnostic_done')
        self.app.engine.stop.assert_called_once()
        self.assertEqual(self.app.store.update_answer.call_args.args[2],'done')


if __name__=='__main__':unittest.main()
