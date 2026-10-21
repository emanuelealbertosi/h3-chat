"""Execute the real native conditioning method with small CPU-only doubles."""
import ast
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch


class NativeExtensionConditionTests(unittest.TestCase):
    def test_short_video_guide_is_anchored_at_correct_end_of_native_latent(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'native/video-worker.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Worker')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='condition')
        namespace={'math':math,'emit':lambda *a,**k:None}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),'native/video-worker.py','exec'),namespace)
        for side,expected in [('before',360),('after',0)]:
            h3=SimpleNamespace(_empty_av_latent=Mock(return_value=({'samples':'latent'},379)))
            worker=SimpleNamespace(torch=SimpleNamespace(cat=lambda frames,dim:frames),comfy=None,h3=h3,
                images=lambda paths:[f'frame-{i}' for i in range(len(paths))],fit_frame=lambda frame,opts:frame,
                vae=SimpleNamespace(encode=lambda frames:frames),clip=SimpleNamespace(tokenize=lambda prompt,**kw:prompt,encode_from_tokens_scheduled=lambda tokens:tokens))
            helper=SimpleNamespace(conditioning_set_values=lambda positive,values:values)
            with patch.dict('sys.modules',{'node_helpers':helper}):
                positive,latent,master,grid=namespace['condition'](worker,{'options':{'width':128,'height':96,'frames':365},
                    'plan':{'images':[],'audios':[],'prompt':'Continue'},'images':[],
                    'extension_context':{'side':side,'paths':['a','b','c','d','e']}})
            h3._empty_av_latent.assert_called_once_with(128,96,365)
            self.assertEqual(positive['minimax_keyframes'],[{'resolved_frame_index':expected,'latent':[f'frame-{i}' for i in range(5)]}])
            self.assertNotIn('minimax_refs',positive);self.assertIsNone(master)

    def test_audio_trim_removes_context_without_shortening_new_clip(self):
        from h3chat.video_extension import window,trim_audio
        class Wave:
            def __getitem__(self,key):return list(range(365))[key[1]]
        for side,expected in [('after',list(range(5,365))),('before',list(range(360)))]:
            result=trim_audio({'sample_rate':24,'waveform':Wave()},window(360,side))
            self.assertEqual(result['waveform'],expected)


if __name__=='__main__':unittest.main()
