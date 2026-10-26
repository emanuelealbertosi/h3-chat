"""Existing H3 PDF renderer behind the cancellable Agent worker boundary."""
import importlib.util
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('agent_pdf_capture',ROOT/'native/infographic-worker.py')
capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
def main():
    from h3chat.pdf_export import export_pdf
    capture.emit('hello',engine='agent-pdf-cpu')
    private_tree=capture.own_process_tree()
    request=json.loads(sys.stdin.readline())
    capture.emit('result',result=export_pdf(ROOT,Path(request['data']),request['body']))
if __name__=='__main__':
    try:main()
    except Exception as error:capture.emit('error',message=str(error))
