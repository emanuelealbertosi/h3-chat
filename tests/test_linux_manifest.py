import hashlib
import io
import unittest
from unittest.mock import patch
from scripts.linux_manifest import archive_identity


class ManifestTests(unittest.TestCase):
    def response(self,data,declared=None):
        value=io.BytesIO(data);value.headers={'Content-Length':str(len(data) if declared is None else declared)}
        return value

    @patch('scripts.linux_manifest.urllib.request.urlopen')
    def test_missing_vendor_hash_is_computed_from_actual_bytes(self,open_url):
        data=b'vendor wheel contents';open_url.return_value=self.response(data)
        self.assertEqual(archive_identity({'url':'https://vendor.test/a.whl','archive_info':{}}),(len(data),hashlib.sha256(data).hexdigest()))

    @patch('scripts.linux_manifest.urllib.request.urlopen')
    def test_declared_hash_and_legacy_hash_remain_pinned(self,open_url):
        for archive in ({'hashes':{'sha256':'A'*64}},{'hash':'sha256='+'A'*64}):
            open_url.return_value=self.response(b'abc')
            self.assertEqual(archive_identity({'url':'https://vendor.test/a.whl','archive_info':archive}),(3,'a'*64))
            self.assertEqual(open_url.call_args.args[0].method,'HEAD')

    @patch('scripts.linux_manifest.urllib.request.urlopen')
    def test_incomplete_stream_and_insecure_sources_are_rejected(self,open_url):
        open_url.return_value=self.response(b'ab',declared=100)
        with self.assertRaisesRegex(ValueError,'Incomplete'):archive_identity({'url':'https://vendor.test/a.whl'})
        with self.assertRaisesRegex(ValueError,'HTTPS'):archive_identity({'url':'http://vendor.test/a.whl'})
