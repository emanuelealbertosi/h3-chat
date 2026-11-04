import json
import tempfile
import unittest
from pathlib import Path
from h3chat.downloads import Downloads

class InstallationInventoryTests(unittest.TestCase):
    def test_inventory_distinguishes_missing_partial_complete_without_opening_weights(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'tools-models.json').write_text(json.dumps({'sample':{'name':'Sample RAG','files':[{'path':'model.bin','size':4,'url':'https://example.test/private?token=hidden'}]}}))
            downloads=Downloads(root,{}, {})
            self.assertEqual(downloads.model_options(),[{'id':'sample','name':'Sample RAG','size':4,'ready':False}])
            (root/'model.bin').write_bytes(b'x')
            self.assertFalse(downloads.model_options()[0]['ready'])
            (root/'model.bin').write_bytes(b'data')
            self.assertTrue(downloads.model_options()[0]['ready'])
            self.assertNotIn('hidden',str(downloads.model_options()))
            self.assertEqual(downloads.snapshot(),[])
