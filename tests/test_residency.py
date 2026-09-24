import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from h3chat.engine import Engine
from h3chat.hardware import assess_selection
from h3chat.residency import FileCache
from h3chat.service import Service
from h3chat.store import DEFAULTS

ROOT=Path(__file__).resolve().parents[1]


class ResidencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.models={}
        for name,cap in [('llm',['chat']),('image',['create','edit']),('edit',['edit'])]:
            p=self.root/(name+'.bin');p.write_bytes(b'weights')
            self.models[name]={'id':name,'name':name,'capabilities':cap,'architecture':'sd',
                'files':[{'role':'model','path':p.name,'size':p.stat().st_size}]}
        self.engine=Engine(self.root,self.root/'data',self.models)
        self.settings=DEFAULTS|{'profile':'cpu','backend':'cpu','chat_model':'llm','create_model':'image','edit_model':'image'}
        self.cancel=threading.Event()

    def tearDown(self):
        self.engine.stop();self.tmp.cleanup()

    def loaded(self,kind,name,settings=None):
        settings=settings or self.settings
        s=self.engine._activate(kind,self.models[name],settings,self.root/(name+'.log'),self.cancel)
        if not s.process:
            class Process:
                pid=123;stdin=None;stdout=None
                ended=False
                def poll(self):return 0 if self.ended else None
                def terminate(self):self.ended=True
                def wait(self,timeout):return 0
            s.process=Process();s.ready=True
        return s

    def test_on_demand_reuses_image_for_create_edit_and_evicts_before_chat(self):
        llm=self.loaded('chat','llm')
        create=self.loaded('image','image')
        self.assertFalse(llm.alive());self.assertEqual(len(self.engine.sessions),1)
        edit=self.loaded('image','image')
        self.assertIs(create,edit);self.assertTrue(edit.alive())
        again=self.loaded('chat','llm')
        self.assertFalse(edit.alive());self.assertIsNot(llm,again)
        self.assertGreater(self.engine.cache.snapshot()['mapped_bytes'],0)

    def test_resident_retains_distinct_models_and_deduplicates_shared_image(self):
        settings=self.settings|{'memory_policy':'resident','edit_model':'edit'}
        llm=self.loaded('chat','llm',settings)
        image=self.loaded('image','image',settings)
        edit=self.loaded('image','edit',settings)
        self.assertTrue(all(s.alive() for s in (llm,image,edit)))
        self.assertEqual(len(self.engine.sessions),3)
        self.assertIs(self.loaded('image','image',settings),image)
        self.engine.abort_active()
        self.assertFalse(image.alive());self.assertTrue(llm.alive());self.assertTrue(edit.alive())

    def test_think_sampling_do_not_reload_but_context_policy_and_files_do(self):
        llm=self.loaded('chat','llm')
        changed=self.settings|{'think_level':'high','temperature':1.2,'max_tokens':512}
        self.assertIs(self.loaded('chat','llm',changed),llm)
        larger=self.loaded('chat','llm',changed|{'context':65536})
        self.assertFalse(llm.alive());self.assertIsNot(larger,llm)
        resident=self.loaded('chat','llm',changed|{'memory_policy':'resident'})
        self.assertFalse(larger.alive());self.assertIsNot(resident,larger)
        (self.root/'llm.bin').write_bytes(b'changed weights')
        reloaded=self.loaded('chat','llm',changed|{'memory_policy':'resident'})
        self.assertFalse(resident.alive());self.assertIsNot(resident,reloaded)
        self.engine.stop()
        self.assertFalse(reloaded.alive());self.assertEqual(self.engine.snapshot()['models'],[])
        self.assertEqual(self.engine.cache.snapshot()['mapped_bytes'],0)

    def test_cache_is_bounded_and_can_be_disabled_without_deleting_weights(self):
        cache=FileCache();cache.configure(10/1024**3)
        cache.remember([self.root/'image.bin',self.root/'edit.bin'])
        self.assertLessEqual(cache.snapshot()['mapped_bytes'],10)
        self.assertEqual(cache.snapshot()['files'],1)
        cache.configure(0);self.assertEqual(cache.snapshot()['mapped_bytes'],0)
        self.assertEqual((self.root/'image.bin').read_bytes(),b'weights')

    def test_resident_aggregate_detects_oom_and_shared_context_counts_once(self):
        model=self.models['image']|{'files':[{'role':'model','path':'image.bin','size':2*1024**3}]}
        llm=self.models['llm']|{'files':[{'role':'model','path':'llm.bin','size':2*1024**3}]}
        hardware={'ram':{'free_mb':7000,'total_mb':16000},'gpu':[]}
        demand=assess_selection([llm,model,model],self.settings,hardware)
        resident=assess_selection([llm,model,model],self.settings|{'memory_policy':'resident'},hardware)
        self.assertEqual(resident['unique_models'],2)
        self.assertEqual(demand['status'],'ok');self.assertEqual(resident['status'],'oom')
        self.assertGreater(resident['ram_gb'],demand['ram_gb'])

    def test_direct_image_assistant_off_never_loads_llm_and_keeps_context_after_job(self):
        app=Service(ROOT,self.root/'service',start_worker=False)
        try:
            c=app.store.create_chat()
            jid=app.store.enqueue(c['id'],'Crea una foto di un gatto',[],DEFAULTS|{'chat_model':'qwen3-06','create_model':'sd15','_assistant':False})
            job=app.store.one('SELECT * FROM jobs WHERE id=?',(jid,))
            with patch.object(app.engine,'start_llama') as start,patch.object(app.engine,'require_model',side_effect=lambda mid,cap:app.catalog[mid]),patch.object(app.engine,'generate',return_value={'id':jid,'path':'test.png','mime':'image/png','name':'test.png'}),patch.object(app.engine,'stop') as stop:
                app.execute_job(job,threading.Event())
                start.assert_not_called();stop.assert_not_called()
            self.assertEqual(app.store.one('SELECT status FROM jobs WHERE id=?',(jid,))['status'],'done')
            self.assertEqual(app.release_memory()['models'],[])
            app.store.enqueue(c['id'],'Ciao',[],DEFAULTS)
            with self.assertRaisesRegex(ValueError,'Attendi'):app.release_memory()
        finally:app.close()

    def test_invalid_memory_settings_rejected(self):
        app=Service(ROOT,self.root/'service',start_worker=False)
        try:
            for values in ({'memory_policy':'auto'},{'ram_cache_gb':-1},{'ram_cache_gb':True},{'ram_cache_gb':33}):
                with self.assertRaises(ValueError):app.validate_settings(values)
        finally:app.close()


if __name__=='__main__':unittest.main()
