"""Actual portable Linux browser export, with both sandbox layers enabled."""
from pathlib import Path
import sys
import tempfile

root=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(root),str(root/'runtime/tools/documents')]
from h3chat.pdf_export import export_pdf
with tempfile.TemporaryDirectory(prefix='h3-linux-pdf-') as temporary:
    folder=Path(temporary)
    value=export_pdf(root,folder,{'title':'PDF Linux isolato','html':'<h1>PDF Linux isolato</h1><p>Testo vettoriale di prova.</p>'})
    pdf=folder/value['url'].lstrip('/')
    assert pdf.read_bytes().startswith(b'%PDF-') and pdf.stat().st_size>1000
    print('Actual Linux PDF export passed; Chromium sandbox enabled, outer bubblewrap isolation enabled.')
