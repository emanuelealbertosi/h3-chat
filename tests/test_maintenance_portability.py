"""Maintenance utilities must not assume another user's paths or activate GPU."""
import argparse
from contextlib import redirect_stderr,redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib

ROOT=Path(__file__).resolve().parents[1]


def script(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'scripts'/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class PortableMaintenanceTests(unittest.TestCase):
    def test_benchmark_requires_explicit_weights_before_gpu_or_writes(self):
        module=script('benchmark_llm_accelerator.py')
        with patch.object(module,'gpu') as gpu,redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:module.main(['--label','test'])
        self.assertEqual(error.exception.code,2);gpu.assert_not_called()

    def test_benchmark_accepts_explicit_inputs_outside_checkout(self):
        module=script('benchmark_llm_accelerator.py')
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);model=folder/module.PROFILES['ista-iq3s']['filename'];model.write_bytes(b'fixture')
            projector=folder/'custom-mmproj.gguf';projector.write_bytes(b'fixture')
            corpus=folder/'corpus.txt';corpus.write_text('Corpus specifico',encoding='utf-8')
            image=folder/'geometry.png';image.write_bytes(module.geometry_image())
            args=argparse.Namespace(model_path=model,model='ista-iq3s',vision=True,mmproj=projector,corpus=corpus,vision_image=image)
            with patch.object(module,'ROOT',folder/'absent-checkout'):
                actual=module.benchmark_inputs(args)
            self.assertEqual(actual,(model.resolve(),projector.resolve(),'Corpus specifico',image.read_bytes()))

    def test_default_geometry_is_valid_cpu_png_with_expected_colors(self):
        image=script('benchmark_llm_accelerator.py').geometry_image()
        self.assertEqual(image[:8],b'\x89PNG\r\n\x1a\n')
        pos=8;compressed=b''
        while pos<len(image):
            size=int.from_bytes(image[pos:pos+4],'big');kind=image[pos+4:pos+8];value=image[pos+8:pos+8+size]
            self.assertEqual(int.from_bytes(image[pos+8+size:pos+12+size],'big'),zlib.crc32(kind+value)&0xffffffff)
            if kind==b'IDAT':compressed+=value
            pos+=size+12
        pixels=zlib.decompress(compressed);row=1+256*3
        self.assertEqual(pixels[64*row+1+60*3:64*row+1+61*3],bytes((220,30,30)))
        self.assertEqual(pixels[64*row+1+190*3:64*row+1+191*3],bytes((30,60,220)))

    def test_accelerator_requires_explicit_source_paths(self):
        module=script('install_qwen27_accelerator.py')
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:module.main([])
        self.assertEqual(error.exception.code,2)

    def test_accelerator_rejects_unverified_engine_before_installing(self):
        module=script('install_qwen27_accelerator.py')
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source=folder/'source';cuda=folder/'cuda';system=folder/'system';app=folder/'app'
            for name in module.EXPECTED:
                p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'unverified')
            for name in ('cublas64_12.dll','cublasLt64_12.dll','cudart64_12.dll'):
                p=cuda/'bin'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fixture')
            system.mkdir()
            for name in ('vcomp140.dll','msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll'):(system/name).write_bytes(b'fixture')
            with patch.object(module,'ROOT',app):
                with self.assertRaisesRegex(RuntimeError,'Unverified source engine'):
                    module.main(['--source',str(source),'--cuda',str(cuda),'--license',str(folder/'LICENSE'),'--system32',str(system)])
            self.assertFalse(app.exists())

    def test_moss_verify_only_preserves_files_and_never_downloads(self):
        module=script('download-moss-bf16.py');content=b'verified official fixture'
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'renamed.safetensors';target.write_bytes(content);before=target.stat().st_mtime_ns
            output=io.StringIO()
            with patch.object(module,'SIZE',len(content)),patch.object(module,'SHA',hashlib.sha256(content).hexdigest()),patch.object(module,'transfer') as transfer,patch.object(module.shutil,'disk_usage') as disk,redirect_stdout(output):
                self.assertEqual(module.main(['--output',str(target),'--verify-only']),0)
            transfer.assert_not_called();disk.assert_not_called()
            self.assertEqual(target.stat().st_mtime_ns,before)
            self.assertEqual(list(Path(tmp).iterdir()),[target])
            result=json.loads(output.getvalue());self.assertTrue(result['verified']);self.assertFalse(result['gpu_used']);self.assertFalse(result['registered'])

    def test_missing_moss_verify_only_does_not_create_destination(self):
        module=script('download-moss-bf16.py')
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'missing'/'model.safetensors'
            with patch.object(module,'transfer') as transfer:
                with self.assertRaises(FileNotFoundError):module.main(['--output',str(target),'--verify-only'])
            transfer.assert_not_called();self.assertFalse(target.parent.exists())

    def test_bad_existing_moss_is_not_overwritten_or_downloaded(self):
        module=script('download-moss-bf16.py')
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'model.safetensors';target.write_bytes(b'bad')
            with patch.object(module,'SIZE',3),patch.object(module,'transfer') as transfer:
                with self.assertRaisesRegex(RuntimeError,'hash mismatch'):module.main(['--output',str(target)])
            transfer.assert_not_called();self.assertEqual(target.read_bytes(),b'bad')

    def test_moss_download_uses_requested_root_and_pinned_official_filename(self):
        module=script('download-moss-bf16.py');content=b'official fixture'
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'models';target=folder/'Stable-diffusion'/module.FILENAME
            def download(url,destination):
                self.assertTrue(url.endswith('/diffusion_models/'+module.FILENAME))
                self.assertEqual(destination,target.resolve());destination.write_bytes(content)
            with patch.object(module,'SIZE',len(content)),patch.object(module,'SHA',hashlib.sha256(content).hexdigest()),patch.object(module.shutil,'disk_usage',return_value=argparse.Namespace(free=100*1024**3)),patch.object(module,'transfer',side_effect=download) as transfer,redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(['--model-root',str(folder)]),0)
            transfer.assert_called_once();self.assertEqual(target.read_bytes(),content)


if __name__=='__main__':unittest.main()
