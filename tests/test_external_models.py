import json
import struct
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from h3chat.external_models import browse, suggest, valid_weight, validate_config
from h3chat.models import inspect_model, model_path
from h3chat.service import Service
from h3chat.store import DEFAULTS
from app import Handler,ThreadingHTTPServer
from test_models_hardware import gguf

ROOT=Path(__file__).resolve().parents[1]


def safetensors(path):
    header=json.dumps({'weight':{'dtype':'F16','shape':[1],'data_offsets':[0,2]}}).encode()
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(struct.pack('<Q',len(header))+header+b'\0\0')
    return path


class ExternalModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name).resolve()
        self.weights=self.base/'Existing models à'
        self.llm=gguf(self.weights/'chat.gguf',**{'general.architecture':'qwen3','general.name':'Existing Qwen','tokenizer.chat_template':'enable_thinking'})
        self.projector=gguf(self.weights/'mmproj.gguf',**{'general.architecture':'clip'})
        self.app=Service(ROOT,self.base/'data',start_worker=False)

    def tearDown(self):
        self.app.close();self.tmp.cleanup()

    def chat(self,**patch):
        return self.app.external_model({'profile':'chat','files':{'model':str(self.llm)},'projector_mode':'auto'}|patch)

    def test_absolute_llm_vision_and_thinking_use_original_files_without_copy(self):
        before=self.llm.read_bytes(),self.projector.read_bytes()
        model=self.chat()
        self.assertTrue(model['ready']);self.assertTrue(model['vision']['enabled']);self.assertTrue(model['thinking']['supported'])
        paths=self.app.engine.model_files(model)
        self.assertEqual(Path(paths['model']),self.llm)
        self.assertEqual(Path(paths['mmproj']),self.projector)
        self.assertFalse(self.llm.is_relative_to(ROOT))
        self.assertFalse((self.base/'data/models').exists())
        self.app.save_settings({'chat_model':model['id']})
        self.app.close();self.app=Service(ROOT,self.base/'data',start_worker=False)
        restored=next(m for m in self.app.state()['models'] if m['id']==model['id'])
        self.assertEqual(restored['external_config']['files']['model'],str(self.llm))
        self.assertEqual(before,(self.llm.read_bytes(),self.projector.read_bytes()))

    def test_automatic_projector_ambiguous_manual_off_and_missing(self):
        model=self.chat()
        extra=gguf(self.weights/'mmproj-other.gguf',**{'general.architecture':'clip'})
        fresh=next(m for m in self.app.state()['models'] if m['id']==model['id'])
        self.assertFalse(fresh['vision']['enabled']);self.assertIn('Più mmproj',fresh['vision']['warning'])
        manual=self.chat(id=model['id'],projector_mode='manual',files={'model':str(self.llm),'mmproj':str(extra)})
        self.assertEqual(Path(manual['vision']['projector']),extra)
        off=self.chat(id=model['id'],projector_mode='off');self.assertFalse(off['vision']['enabled'])
        extra.unlink();self.projector.unlink()
        auto=self.chat(id=model['id']);self.assertTrue(auto['ready']);self.assertFalse(auto['vision']['enabled'])
        self.assertIn('mmproj assente',auto['vision']['warning'])
        gguf(self.projector,**{'general.architecture':'clip'})
        fresh=next(m for m in self.app.state()['models'] if m['id']==model['id'])
        self.assertTrue(fresh['vision']['enabled'])

    def test_images_components_in_different_directories_and_shared_create_edit(self):
        main=gguf(self.weights/'diffusion/flux.gguf',**{'general.architecture':'flux'})
        encoder=safetensors(self.weights/'text_encoders/qwen.safetensors')
        vae=safetensors(self.weights/'vae/ae.safetensors')
        model=self.app.external_model({'profile':'flux2','name':'Existing FLUX','files':{'diffusion':str(main),'llm':str(encoder),'vae':str(vae)},'steps':8,'cfg':1.5})
        self.assertTrue(model['ready']);self.assertEqual(model['steps'],8);self.assertEqual(model['max_refs'],4)
        self.assertEqual(self.app.engine.model_files(model),{'diffusion':str(main),'llm':str(encoder),'vae':str(vae)})
        self.app.save_settings({'create_model':model['id'],'edit_model':model['id']})
        vae.unlink()
        unavailable=next(m for m in self.app.state()['models'] if m['id']==model['id'])
        self.assertFalse(unavailable['ready']);self.assertIn('VAE',unavailable['external_problems'][0])
        with self.assertRaisesRegex(ValueError,'Collegamento non disponibile'):self.app.engine.require_model(model['id'],'create')
        new=safetensors(self.weights/'new/vae.safetensors')
        repaired=self.app.external_model(model['external_config']|{'files':model['external_config']['files']|{'vae':str(new)}})
        self.assertTrue(repaired['ready']);self.assertEqual(repaired['id'],model['id'])
        self.app.remove_external_model(model['id'])
        self.assertTrue(main.exists() and encoder.exists() and new.exists())
        self.assertEqual(self.app.store.settings()['create_model'],'');self.assertEqual(self.app.store.settings()['edit_model'],'')

    def test_missing_llm_remains_visible_and_unlink_never_deletes_weights(self):
        model=self.chat();self.llm.rename(self.weights/'moved.gguf')
        current=next(m for m in self.app.state()['models'] if m['id']==model['id'])
        self.assertFalse(current['ready'])
        self.app.remove_external_model(model['id'])
        self.assertTrue((self.weights/'moved.gguf').exists());self.assertTrue(self.projector.exists())
        self.assertFalse(any(m['id']==model['id'] for m in self.app.state()['models']))

    def test_split_files_are_required_and_all_paths_retained(self):
        first=gguf(self.weights/'split-00001-of-00002.gguf',**{'general.architecture':'qwen3','split.count':2})
        with self.assertRaises(ValueError):self.chat(files={'model':str(first)})
        second=gguf(self.weights/'split-00002-of-00002.gguf',**{'general.architecture':'qwen3','split.count':2})
        model=self.chat(files={'model':str(first)})
        self.assertTrue(model['ready']);self.assertIn(str(second),self.app.engine.model_files(model).values())
        with self.assertRaisesRegex(ValueError,'prima parte'):self.chat(files={'model':str(second)})

    def test_browse_suggestions_and_invalid_input_boundaries(self):
        listed=browse({'path':str(self.weights)})
        self.assertEqual(listed['path'],str(self.weights));self.assertEqual(len(listed['entries']),2)
        result=suggest({'profile':'chat','path':str(self.llm)})
        self.assertEqual(result['candidates']['mmproj'],[str(self.projector)])
        for body in ({'profile':'chat','files':{'model':'relative.gguf'}},
                     {'profile':'chat','files':{'model':str(self.projector)}},
                     {'profile':'flux2','files':{'diffusion':str(self.llm)}},
                     {'profile':'chat','files':{'model':str(self.llm)},'external':True}):
            with self.assertRaises(ValueError):validate_config(body)
        bad=self.weights/'bad.safetensors';bad.write_bytes(struct.pack('<Q',2**40))
        self.assertFalse(valid_weight(bad))
        with self.assertRaises(ValueError):model_path(ROOT,{'local':True},str(self.llm))

    def test_external_download_and_mutation_during_jobs_rejected(self):
        model=self.chat()
        with self.assertRaisesRegex(ValueError,'collegamenti'):self.app.downloads.start(model['id'])
        c=self.app.store.create_chat();self.app.store.enqueue(c['id'],'Hello',[],DEFAULTS)
        with self.assertRaisesRegex(ValueError,'Attendi'):self.app.remove_external_model(model['id'])
        with self.assertRaisesRegex(ValueError,'Attendi'):self.chat(id=model['id'])
        self.assertTrue(self.llm.exists())

    def test_type_change_clears_incompatible_role_and_unlink_releases_cached_projector(self):
        model=self.chat();self.app.save_settings({'chat_model':model['id']})
        image=safetensors(self.weights/'checkpoint.safetensors')
        changed=self.app.external_model({'id':model['id'],'profile':'sd','files':{'model':str(image)}})
        self.assertEqual(self.app.store.settings()['chat_model'],'')
        self.assertTrue(changed['ready'])
        self.app.engine.cache.configure(2);self.app.engine.cache.remember([self.projector])
        self.assertGreater(self.app.engine.cache.snapshot()['mapped_bytes'],0)
        self.app.remove_external_model(model['id'])
        self.assertEqual(self.app.engine.cache.snapshot()['mapped_bytes'],0)
        self.assertTrue(image.exists() and self.projector.exists())

    def test_browsing_requires_session_and_keeps_media_guard(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.app=self.app
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            body=json.dumps({'path':str(self.weights)}).encode()
            req=urllib.request.Request(base+'/api/model-files/browse',data=body,headers={'Content-Type':'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(req)
            self.assertEqual(cm.exception.code,403)
            req.add_header('X-H3-Token',self.app.token)
            with urllib.request.urlopen(req) as response:self.assertEqual(len(json.load(response)['entries']),2)
            with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+'/media/uploads/../../../'+urllib.parse.quote(self.llm.as_posix()))
        finally:server.shutdown();server.server_close()


if __name__=='__main__':unittest.main()
