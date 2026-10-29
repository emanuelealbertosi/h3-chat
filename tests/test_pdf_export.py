import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from h3chat.pdf_export import export_document


class ExportSizeTests(unittest.TestCase):
    def test_svg_fragment_paints_survive_without_enabling_remote_urls(self):
        source='<svg><defs><linearGradient id="paint"><stop offset="0" stop-color="red"/></linearGradient><filter id="blur"><feGaussianBlur stdDeviation="2"/></filter></defs><rect id="local" style="fill:url(#paint);filter:url(#blur)"/><rect id="remote" style="fill:url(https://example.invalid/x.svg#paint)" onload="alert(1)"/></svg>'
        with tempfile.TemporaryDirectory() as directory,patch('h3chat.pdf_export.embedded_css',return_value=''):
            _,file,_=export_document(Path(directory),Path(directory),{'html':source})
            saved=file.read_text(encoding='utf8');self.assertIn('fill:url(#paint);filter:url(#blur)',saved);self.assertIn('fegaussianblur',saved);self.assertNotIn('example.invalid',saved);self.assertNotIn('onload=',saved)

    def test_vertical_slides_keep_portrait_page_dimensions(self):
        from h3chat.slides import FORMATS
        width,height=FORMATS['9:16']
        self.assertAlmostEqual(width/height,9/16)
        with tempfile.TemporaryDirectory() as directory,patch('h3chat.pdf_export.embedded_css',return_value=''):
            _,file,_=export_document(Path(directory),Path(directory),{'title':'Verticale','html':'<article class="h3-slide-page">Verticale</article>','slide_format':'9:16'})
            self.assertIn(f'@page{{size:{width}px {height}px;margin:0}}',file.read_text(encoding='utf-8'))

    def test_valid_slides_above_old_limit_keep_vector_markup_and_images(self):
        source='<article class="h3-slide-page"><p>'+('x'*(16*1024*1024))+'</p><svg><text>Dato vettoriale</text></svg><img src="data:image/png;base64,YQ=="></article>'
        with tempfile.TemporaryDirectory() as directory,patch('h3chat.pdf_export.embedded_css',return_value=''):
            _,file,_=export_document(Path(directory),Path(directory),{'title':'Presentazione','html':source,'slide_format':'16:9'})
            saved=file.read_text(encoding='utf-8')
            self.assertIn('Dato vettoriale',saved)
            self.assertIn('data:image/png;base64,YQ==',saved)
            self.assertIn('@page{size:1280px 720px;margin:0}',saved)

    def test_slides_above_64_mib_are_exported(self):
        source='<p>'+('x'*(65*1024*1024))+'</p>'
        with tempfile.TemporaryDirectory() as directory,patch('h3chat.pdf_export.embedded_css',return_value=''):
            _,file,_=export_document(Path(directory),Path(directory),{'html':source,'slide_format':'16:9'})
            self.assertGreater(file.stat().st_size,64*1024*1024)

    def test_export_http_routes_accept_large_bodies_without_raising_general_limits(self):
        from app import Handler
        from types import SimpleNamespace
        import io
        for path in ('/api/export/pdf','/api/export/html'):
            request=SimpleNamespace(path=path,headers={'Content-Type':'application/json','Content-Length':str(100*1024*1024)},rfile=io.BytesIO(b'{}'))
            self.assertEqual(Handler.read_body(request),{})
        for path in ('/api/chats/abc/messages','/api/auth/login'):
            request=SimpleNamespace(path=path,headers={'Content-Type':'application/json','Content-Length':str(100*1024*1024)},rfile=io.BytesIO(b'{}'))
            with self.assertRaisesRegex(ValueError,'troppo grande'):Handler.read_body(request)

    def test_invalid_content_and_title_have_distinct_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            for body,message in (({'html':[]},'deve essere HTML'),({'html':'<p>Valido</p>','title':'x'*151},'titolo')):
                with self.assertRaisesRegex(ValueError,message):
                    export_document(Path(directory),Path(directory),body)


if __name__=='__main__':unittest.main()
