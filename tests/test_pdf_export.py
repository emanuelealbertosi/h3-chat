import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from h3chat.pdf_export import export_document


class ExportSizeTests(unittest.TestCase):
    def test_valid_slides_above_old_limit_keep_vector_markup_and_images(self):
        source='<article class="h3-slide-page"><p>'+('x'*(16*1024*1024))+'</p><svg><text>Dato vettoriale</text></svg><img src="data:image/png;base64,YQ=="></article>'
        with tempfile.TemporaryDirectory() as directory,patch('h3chat.pdf_export.embedded_css',return_value=''):
            _,file,_=export_document(Path(directory),Path(directory),{'title':'Presentazione','html':source,'slide_format':'16:9'})
            saved=file.read_text(encoding='utf-8')
            self.assertIn('Dato vettoriale',saved)
            self.assertIn('data:image/png;base64,YQ==',saved)
            self.assertIn('@page{size:1280px 720px;margin:0}',saved)

    def test_limit_counts_utf8_bytes_and_rejects_before_creating_files(self):
        with tempfile.TemporaryDirectory() as directory,patch('h3chat.pdf_export.MAX_EXPORT_HTML_BYTES',1024):
            for source in ('x'*1025,'è'*513):
                with self.assertRaisesRegex(ValueError,'limite di 64 MB'):
                    export_document(Path(directory),Path(directory),{'html':source})
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_invalid_content_and_title_have_distinct_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            for body,message in (({'html':[]},'deve essere HTML'),({'html':'<p>Valido</p>','title':'x'*151},'titolo')):
                with self.assertRaisesRegex(ValueError,message):
                    export_document(Path(directory),Path(directory),body)


if __name__=='__main__':unittest.main()
