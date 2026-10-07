import json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.embeddinggemma2 import checkpoint,formatted,memory_assessment
from h3chat.rag import Embeddings,validate
from h3chat.rag_profiles import visual_enabled
from h3chat.store import DEFAULTS
from h3chat.downloads import Cancelled

class Gemma2Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.folder=self.root/'gemma';self.folder.mkdir()
        for name in ('model.safetensors','tokenizer.json','tokenizer_config.json','processor_config.json','preprocessor_config.json'):(self.folder/name).write_text('{}')
        (self.folder/'config.json').write_text(json.dumps({'model_type':'embedding_gemma2','text_config':{'embedding_dim':768}}))
        self.settings=DEFAULTS|{'rag_embedding_model':str(self.folder),'rag_embedding_profile':'embeddinggemma2'}

    def test_local_checkpoint_and_defaults_do_not_replace_existing_embedding(self):
        validate(self.settings);self.assertEqual(checkpoint(self.folder)[0],self.folder)
        self.assertEqual(DEFAULTS['rag_embedding_profile'],'embeddinggemma');self.assertEqual(DEFAULTS['rag_embedding_model'],'')
        with self.assertRaises(ValueError):checkpoint('relative')
        (self.folder/'processor_config.json').unlink()
        with self.assertRaisesRegex(ValueError,'incompleta'):validate(self.settings)

    def test_new_vector_space_has_own_key_and_invalidates_visual_device_and_weights(self):
        engine=Embeddings(self.root,self.root/'data');key=engine.key(self.settings)
        self.assertNotEqual(key,engine.key(self.settings|{'rag_visual':False}))
        self.assertNotEqual(key,engine.key(self.settings|{'rag_device':'gpu'}))
        (self.folder/'model.safetensors').write_text('new weights')
        self.assertNotEqual(key,engine.key(self.settings))
        self.assertTrue(visual_enabled(self.settings));self.assertFalse(visual_enabled(self.settings|{'rag_visual':False}))

    def test_retrieval_prefixes_and_visual_placeholder_match_official_contract(self):
        self.assertEqual(formatted('tema',True),'task: search result | query: tema')
        self.assertEqual(formatted('fonte'),'title: none | text: fonte')
        self.assertEqual(formatted('',image=True),'<|image|>')
        self.assertEqual(formatted('didascalia',image=True),'<|image|> title: none | text: didascalia')

    def test_cpu_gpu_memory_estimates_and_text_only_tower_selection(self):
        hardware={'ram':{'free_mb':16*1024},'gpu':[{'vendor':'NVIDIA','free_mb':8*1024}]}
        result=memory_assessment(self.settings,hardware)
        self.assertEqual(result['status'],'ok');self.assertEqual(result['vram_gb'],0)
        self.assertLess(memory_assessment(self.settings|{'rag_visual':False},hardware)['ram_gb'],result['ram_gb'])
        self.assertEqual(memory_assessment(self.settings|{'rag_device':'gpu'},hardware)['status'],'ok')
        self.assertEqual(memory_assessment(self.settings|{'rag_device':'gpu'},hardware|{'gpu':[{'vendor':'NVIDIA','free_mb':200}]})['status'],'oom')

    def test_worker_routing_dimension_validation_and_cancellation_release(self):
        sessions=[]
        class Fake:
            def __init__(inner,*args):inner.key=args[0];inner.sent=[];inner.stopped=False;sessions.append(inner)
            def alive(inner):return not inner.stopped
            def start(inner,args,**kw):self.assertTrue(str(args[-1]).endswith('embeddinggemma-worker.py'))
            def send(inner,value):inner.sent.append(value)
            def stop(inner):inner.stopped=True
            def wait(inner,target,cancel,*args):
                if cancel.is_set():raise Cancelled()
                if target=='result':return {'vectors':[[1.]+[0.]*767 for _ in inner.sent[-1].get('texts',inner.sent[-1].get('items',[]))]}
                return {}
        engine=Embeddings(self.root,self.root/'data');cancel=threading.Event()
        with patch('h3chat.embeddinggemma2.runtime_ready',return_value=True),patch('h3chat.rag.Session',Fake):
            vectors=engine.encode(['document']*9,self.settings,cancel,lambda _:None)
            self.assertEqual(len(vectors),9);self.assertEqual(len(sessions),1)
            self.assertEqual([len(x['texts']) for x in sessions[0].sent if 'texts' in x],[8,1])
            self.assertEqual(sessions[0].sent[0]['device'],'cpu');self.assertTrue(sessions[0].sent[0]['visual'])
            image=self.root/'data/image.png';image.parent.mkdir();image.write_bytes(b'fixture')
            engine.encode_items([{'text':'caption','image_path':'image.png'}],self.settings,cancel,lambda _:None)
            self.assertEqual(sessions[0].sent[-1]['items'][0]['image'],str(image))
            engine.encode(['query'],self.settings,cancel,lambda _:None,query=True);self.assertTrue(sessions[0].sent[-1]['query'])
            cancel.set()
            with self.assertRaises(Cancelled):engine.encode(['query'],self.settings,cancel,lambda _:None)
            self.assertTrue(sessions[0].stopped);self.assertIsNone(engine.session)

if __name__=='__main__':unittest.main()
