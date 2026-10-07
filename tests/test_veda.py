import ast
import json
import logging
import struct
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import ModuleType,SimpleNamespace
from unittest.mock import Mock,patch
from h3chat.veda import predictor_path,preflight,status,mark_ready,report,release,REVISION
from h3chat.video_options import validate

ROOT=Path(__file__).resolve().parents[1]

class VedaTests(unittest.TestCase):
    def test_opt_in_and_validation_preserve_existing_presets(self):
        self.assertEqual(validate({'steps':12})['attention'],'auto')
        self.assertEqual(validate({'attention':'veda'})['veda_sparsity'],90)
        self.assertEqual(validate({'attention':'veda','veda_reference_sparsity':0})['veda_reference_sparsity'],0)
        for value in (100,-1,True,'90%',float('nan')):
            with self.subTest(value=value),self.assertRaises(ValueError):validate({'veda_sparsity':value})
        for value in ('relative.safetensors','F:/wrong.gguf',False):
            with self.subTest(value=value),self.assertRaises(ValueError):validate({'veda_predictor':value})

    def test_original_path_and_bounded_predictor_header(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'original.safetensors'
            header=json.dumps({'__metadata__':{'format':'miowtion-veda-predictor-v1'}}).encode()
            path.write_bytes(struct.pack('<Q',len(header))+header+b'weights')
            self.assertEqual(predictor_path(root,str(path)),path.resolve())
            path.write_bytes(struct.pack('<Q',4_000_001)+b'{}')
            with self.assertRaisesRegex(ValueError,'Header'):predictor_path(root,str(path))
            path.write_bytes(struct.pack('<Q',2)+b'{}')
            with self.assertRaisesRegex(ValueError,'non è un predictor'):predictor_path(root,str(path))
            with self.assertRaisesRegex(ValueError,'mancante'):predictor_path(root)

    def test_ready_requires_finished_verified_install_and_base_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'runtimes.json').write_text(json.dumps({'veda':{'files':[{'path':'fixture','sha256':'a'*64}]}}))
            for name in ('veda_comfy/comfy_patch.py','veda_comfy/core/bundle.py','veda_comfy/kernels/sage/sparse_int8.py','LICENSE','NOTICE.md'):
                path=root/'runtime/veda'/REVISION/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
            with patch('h3chat.veda.vision_status',return_value={'accelerated':True}):
                self.assertFalse(status(root)['ready']);mark_ready(root);self.assertTrue(status(root)['ready'])
                (root/'runtimes.json').write_text(json.dumps({'veda':{'files':[]}}));self.assertFalse(status(root)['ready'])
            preflight(root,{'attention':'auto'})
            with self.assertRaisesRegex(ValueError,'Installa VEDA'):preflight(root,{'attention':'veda'})

    def test_actual_calls_and_partial_fallback_are_reported(self):
        self.assertEqual(report(None),{})
        patcher=SimpleNamespace(h3_result={'sparse_calls':0,'dense_calls':0,'fallback_reason':'','summary':''},run=SimpleNamespace(calls=Counter(),failed=None),_summary=lambda:'summary')
        self.assertFalse(report(patcher)['active']);self.assertIn('Nessuna chiamata',report(patcher)['fallback_reason'])
        patcher.run.calls.update(sparse=5,error=2);patcher.run.failed='kernel error'
        result=report(patcher);self.assertTrue(result['active']);self.assertEqual(result['sparse_calls'],5);self.assertEqual(result['dense_calls'],2);self.assertEqual(result['fallback_reason'],'kernel error')
        self.assertEqual(patcher.h3_result['sparse_calls'],0)

    def test_resident_switch_restores_base_and_does_not_stack_veda(self):
        tree=ast.parse((ROOT/'native/video-worker.py').read_text(encoding='utf-8'))
        definition=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Worker')
        base,clone=Mock(),Mock();attn=Mock(SAGE_ATTENTION_IS_AVAILABLE=True)
        module=ModuleType('comfy.ldm.modules');module.attention=attn
        namespace={'ROOT':ROOT,'logging':logging,'emit':Mock(),'chunked_attention':lambda torch,attention,chunks:attn.attention_sage}
        exec(compile(ast.Module(body=[definition],type_ignores=[]),'<worker>','exec'),namespace)
        worker=namespace['Worker']();worker.model=base
        worker.torch=SimpleNamespace(cuda=SimpleNamespace(get_device_properties=lambda _:SimpleNamespace(total_memory=16*1024**3)))
        with patch.dict('sys.modules',{'comfy.ldm.modules':module}),patch('h3chat.veda.attach',return_value=(clone,object())) as attach,patch('h3chat.veda.release') as release_mock:
            self.assertEqual(worker.configure_attention('veda',8,{'veda_reference_sparsity':0}),'veda')
            self.assertIs(worker.veda_base_model,base);self.assertIs(worker.model,clone)
            worker.configure_attention('veda',8,{})
            self.assertIs(attach.call_args.args[1],base)
            worker.configure_attention('sage',8)
            self.assertIs(worker.model,base);self.assertIsNone(worker.veda_patch);self.assertIsNone(worker.veda_base_model)
            self.assertEqual(release_mock.call_count,2)

    def test_release_frees_predictor_and_gpu_workspaces(self):
        patcher=SimpleNamespace(_engines={'gpu':object()},_timers={'gpu':object()},bundle=object(),installed={object()})
        release(patcher);release(None)
        self.assertIsNone(patcher.bundle);self.assertEqual(patcher._engines,{});self.assertEqual(patcher._timers,{});self.assertEqual(patcher.installed,set())

if __name__=='__main__':unittest.main()
