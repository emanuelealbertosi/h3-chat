import unittest
from h3chat.video_memory import should_trim_sampling_cache,diffuser_placement
from types import SimpleNamespace


class SamplingMemoryTests(unittest.TestCase):
    def test_placement_reports_streaming_without_claiming_system_paging(self):
        model=type('MiniMaxH3',(),{})()
        patcher=SimpleNamespace(model=model,model_size=lambda:20*1024**3,loaded_size=lambda:0)
        self.assertTrue(diffuser_placement([patcher])['streaming_from_ram'])
        patcher.loaded_size=lambda:10*1024**3
        self.assertFalse(diffuser_placement([patcher])['streaming_from_ram'])
        self.assertIsNone(diffuser_placement([]))
    def test_nearly_full_but_unused_pool_is_trimmed(self):
        observed={'reserved_mb':14560,'allocated_mb':265.17,'free_mb':0}
        self.assertTrue(should_trim_sampling_cache(observed,True))
        self.assertFalse(should_trim_sampling_cache(observed,False))

    def test_resident_weights_and_adequate_headroom_are_preserved(self):
        self.assertFalse(should_trim_sampling_cache({'reserved_mb':14000,'allocated_mb':13500,'free_mb':0},True))
        self.assertFalse(should_trim_sampling_cache({'reserved_mb':12192,'allocated_mb':7697,'free_mb':2410},True))
        self.assertFalse(should_trim_sampling_cache(None,True))


if __name__=='__main__':unittest.main()
