import ast,unittest
from pathlib import Path
from unittest.mock import Mock

class CaptureTests(unittest.TestCase):
    def helper(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'native/infographic-worker.py').read_text(encoding='utf-8'))
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='capture_frame');scope={}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'capture_frame','exec'),scope);return scope['capture_frame']
    def test_requests_lossless_fast_png(self):
        cdp=Mock(spec=['call']);cdp.call.return_value={'data':'png'}
        self.assertEqual(self.helper()(cdp),{'data':'png'});self.assertEqual(cdp.call.call_args.args[1],{'format':'png','captureBeyondViewport':False,'fromSurface':True,'optimizeForSpeed':True})
    def test_older_renderer_fallback_is_cached_but_crashes_are_not_retried(self):
        cdp=Mock(spec=['call']);cdp.call.side_effect=[RuntimeError('Renderer: Invalid parameters'),{'data':'old'},{'data':'old2'}]
        capture=self.helper();self.assertEqual(capture(cdp)['data'],'old');self.assertEqual(capture(cdp)['data'],'old2')
        self.assertEqual(cdp.call.call_count,3);self.assertNotIn('optimizeForSpeed',cdp.call.call_args.args[1])
        broken=Mock(spec=['call']);broken.call.side_effect=RuntimeError('Renderer disconnesso')
        with self.assertRaisesRegex(RuntimeError,'disconnesso'):capture(broken)
        self.assertEqual(broken.call.call_count,1)
