import unittest
from types import SimpleNamespace
from h3chat.veda_memory import available_workspace,install,head_chunks_for_edit

GIB=1024**3

class VedaMemoryTests(unittest.TestCase):
    def test_long_aligned_edit_uses_measured_small_batches_without_changing_other_workflows(self):
        config=dict(aligned=True,width=1152,height=672,frames=360,total_bytes=16*GIB)
        self.assertEqual(head_chunks_for_edit(8,**config),56)
        for changes in ({'aligned':False},{'frames':240},{'total_bytes':24*GIB},{'diagnostic':True}):
            self.assertEqual(head_chunks_for_edit(8,**(config|changes)),8)
        self.assertEqual(head_chunks_for_edit(56,**config),56)
        self.assertEqual(head_chunks_for_edit(8,**(config|{'width':960,'height':544})),8)
    def test_unused_cache_is_available_without_counting_live_tensors(self):
        cuda=SimpleNamespace(mem_get_info=lambda device:(0,16*GIB),memory_reserved=lambda device:14*GIB,memory_allocated=lambda device:6*GIB)
        self.assertEqual(available_workspace(cuda,None),(8*GIB,0,8*GIB))

    def test_full_resolution_reference_video_gets_same_head_budget_as_aligned_guide(self):
        config=dict(aligned=False,width=1344,height=768,frames=240,total_bytes=16*GIB)
        self.assertEqual(head_chunks_for_edit(8,**config,source_shape=(1376,768,240)),56)
        self.assertEqual(head_chunks_for_edit(8,**config,source_shape=(768,448,240)),8)
        self.assertEqual(head_chunks_for_edit(8,**(config|{'diagnostic':True}),source_shape=(1376,768,240)),8)

    def test_budget_never_adds_negative_cache_or_exceeds_total_memory(self):
        cuda=SimpleNamespace(mem_get_info=lambda device:(GIB,16*GIB),memory_reserved=lambda device:4*GIB,memory_allocated=lambda device:5*GIB)
        self.assertEqual(available_workspace(cuda,None),(GIB,GIB,0))
        cuda.memory_reserved=lambda device:30*GIB
        self.assertEqual(available_workspace(cuda,None)[0],16*GIB)

    def test_lazy_engine_keeps_vendor_limits_and_cpu_fallback(self):
        cuda=SimpleNamespace(mem_get_info=lambda device:(0,16*GIB),memory_reserved=lambda device:14*GIB,memory_allocated=lambda device:6*GIB)
        module=SimpleNamespace(_CHUNK_SHARE=8,_MIN_CHUNK_BYTES=128*1024**2,_MAX_CHUNK_BYTES=GIB)
        engine=SimpleNamespace(device=SimpleNamespace(type='cuda'),chunking={},_chunk_bytes=lambda:128*1024**2)
        patch=SimpleNamespace(_engine=lambda device:engine)
        install(patch,SimpleNamespace(cuda=cuda),module)
        self.assertIs(patch._engine(None),engine)
        self.assertEqual(engine._chunk_bytes(),GIB)
        self.assertEqual(engine.chunking['driver_free_bytes'],0)
        self.assertEqual(engine.chunking['reusable_cache_bytes'],8*GIB)
        adapted=engine._chunk_bytes
        patch._engine(None)
        self.assertIs(engine._chunk_bytes,adapted)
        engine.device.type='cpu'
        self.assertEqual(engine._chunk_bytes(),128*1024**2)
        absent=SimpleNamespace(_engine=lambda device:None)
        install(absent,SimpleNamespace(cuda=cuda),module)
        self.assertIsNone(absent._engine(None))

if __name__=='__main__':unittest.main()
