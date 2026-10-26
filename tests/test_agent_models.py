"""Catalog/preset tools use H3 validators, no actual model downloads or loading."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_visual_models as fixture
from h3chat.agent_model_tools import execute

class ModelToolsTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown
    def context(self):return SimpleNamespace(app=self.app,settings=self.app.store.settings())
    def test_catalog_local_download_is_not_fabricated_and_defaults_only_on_request(self):
        ctx=self.context();rows=execute(ctx,'list_model_catalog',{'query':self.qwen['id']})['models'];self.assertTrue(any(m['id']==self.qwen['id'] and not m['downloadable'] for m in rows))
        with patch.object(self.app.downloads,'start') as start:
            with self.assertRaises(ValueError):execute(ctx,'download_catalog_model',{'model_id':self.qwen['id']})
            start.assert_not_called()
        before=self.app.store.settings()['create_model']
        result=execute(ctx,'set_model_preset',{'model_id':self.ming['id'],'parameters':{'steps':12,'cfg':1,'sampler':'euler','scheduler':'simple','aspect':'16:9','megapixels':1.2}})
        self.assertFalse(result['inference_started']);self.assertEqual(self.app.store.settings()['create_model'],before);self.assertEqual(ctx.settings['image_overrides'][self.ming['id']]['megapixels'],1.2)
        with self.assertRaises(ValueError):execute(ctx,'set_model_preset',{'model_id':self.ming['id'],'parameters':{'scheduler':'invented'}})
        self.assertEqual(self.app.store.settings()['image_overrides'][self.ming['id']]['scheduler'],'simple')
    def test_catalog_download_uses_existing_manager_and_reuses_task(self):
        ctx=self.context();model=next(m for m in self.app.refresh_models() if not m.get('local') and m.get('files') and not m.get('ready'));task={'id':model['id'],'status':'running','received':123,'total':1000}
        with patch.object(self.app.downloads,'start',return_value=model['id']) as start:
            result=execute(ctx,'download_catalog_model',{'model_id':model['id']});self.assertTrue(result['started']);start.assert_called_once_with(model['id'])
        with patch.object(self.app.downloads,'snapshot',return_value=[task]),patch.object(self.app.downloads,'start') as start:
            result=execute(ctx,'download_catalog_model',{'model_id':model['id']});self.assertTrue(result['reused']);self.assertEqual(execute(ctx,'model_download_status',{'model_id':model['id']})['task']['received'],123);start.assert_not_called()
        with self.assertRaises(ValueError):execute(ctx,'download_catalog_model',{'model_id':'arbitrary-url'})

if __name__=='__main__':unittest.main()
