import hashlib
import io
from pathlib import Path
import runpy
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
import test_visual_models as fixture
from test_loras_image_options import lora
from h3chat.agent_asset_tools import execute,filename


class AssetToolsTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown

    def context(self,family='anima'):
        self.app.catalog['test-anima']={'id':'test-anima','name':'Anima structural fixture','architecture':'anima','capabilities':['create']}
        source=lora(self.app.data/'outputs'/('a'*32)/'asset/input.safetensors',family)
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        worker=Mock(return_value={'path':source.relative_to(self.app.data).as_posix(),'bytes':source.stat().st_size,'sha256':digest})
        ctx=SimpleNamespace(app=self.app,settings=self.app.store.settings()|{'_web':True},action={'id':'a'*32},engine=SimpleNamespace(tool_call=worker),
            cancel=threading.Event(),stage=Mock(),log_path=self.base/'log',remaining=lambda:300,check=lambda:None)
        return ctx,source

    def test_install_validates_compatibility_indexes_and_does_not_select_or_overwrite(self):
        destination=self.base/'loras';destination.mkdir();self.app.save_settings({'lora_dirs':[str(destination)]})
        ctx,source=self.context();before=self.app.store.settings()['create_model']
        args={'url':'https://models.test/a.safetensors','name':'installed.safetensors','model_id':'test-anima'}
        result=execute(ctx,'install_lora_from_url',args)
        self.assertTrue(result['installed']);self.assertTrue(result['available_in_lora_library']);self.assertFalse(result['selected_for_generation'])
        self.assertEqual((destination/args['name']).read_bytes(),source.read_bytes());self.assertEqual(self.app.store.settings()['create_model'],before)
        with self.assertRaisesRegex(ValueError,'esiste'):execute(ctx,'install_lora_from_url',args)
        self.assertEqual(ctx.engine.tool_call.call_count,1)

    def test_wrong_family_and_missing_web_do_not_install(self):
        destination=self.base/'loras';destination.mkdir();self.app.save_settings({'lora_dirs':[str(destination)]})
        ctx,source=self.context('anima');args={'url':'https://models.test/a','name':'wrong.safetensors','model_id':self.qwen['id']}
        with self.assertRaisesRegex(ValueError,'compatibile'):execute(ctx,'install_lora_from_url',args)
        self.assertFalse((destination/args['name']).exists())
        ctx.settings['_web']=False
        with self.assertRaises(PermissionError):execute(ctx,'install_lora_from_url',args)
        for bad in ('../bad.bin','C:\\a.bin','CON.safetensors','a.exe:stream','a.txt.','/tmp/a'):
            with self.assertRaises(ValueError):filename(bad)


class StreamingDownloadTests(unittest.TestCase):
    def worker(self):
        previous=sys.stdout
        try:return runpy.run_path(str(Path(__file__).resolve().parents[1]/'native/agent-asset-worker.py'))
        finally:sys.stdout=previous

    def test_private_addresses_are_rejected_before_connecting(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            worker=self.worker()
            with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),patch('socket.create_connection') as connect:
                with self.assertRaisesRegex(ValueError,'pubblici'):worker['run']({'id':'b'*32,'data':folder,'name':'a.bin','url':'https://private.test/a'})
                connect.assert_not_called()

    def test_hash_mismatch_never_publishes_and_a_complete_file_is_not_executed(self):
        import tempfile
        raw=b'a downloaded file';response=io.BytesIO(raw);response.status=200
        response.getheader=lambda key,default=None:str(len(raw)) if key=='Content-Length' else default
        connection=Mock();connection.getresponse.return_value=response
        with tempfile.TemporaryDirectory() as folder:
            worker=self.worker();request={'id':'b'*32,'data':folder,'name':'a.bin','url':'http://public.test/a','sha256':'0'*64}
            with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('93.184.216.34',80))]),patch('socket.create_connection'),patch('http.client.HTTPConnection',return_value=connection):
                with self.assertRaisesRegex(ValueError,'SHA256'):worker['run'](request)
                self.assertFalse(list(Path(folder).rglob('a.bin')));self.assertFalse(list(Path(folder).rglob('*.partial')))
                response.seek(0);request['sha256']=hashlib.sha256(raw).hexdigest();result=worker['run'](request)
                self.assertEqual((Path(folder)/result['path']).read_bytes(),raw)
                with self.assertRaises(ValueError):worker['run'](request)
