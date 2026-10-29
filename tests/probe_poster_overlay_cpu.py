"""Opt-in real offline browser geometry probe. No LLM/image inference."""
import json,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'runtime/tools/documents')]
from test_visual_models import VisualModelsTests
from test_poster_overlay import prepared,fragments
from h3chat.poster_overlay import measure,measure_before_background
from h3chat.posters import options
import copy
from h3chat.slides import FORMATS

case=VisualModelsTests();case.setUp()
try:
    value=prepared();parts=fragments(value);out={'gpu_models':0,'llm_calls':0,'visual_review':False};cancel=threading.Event()
    log=case.app.data/'cpu-layout.log';folder=case.app.data/'outputs'/'cpu-proof'
    parts['title']='<p style="margin:0;font-family:BebasNeue;font-size:80px">OPEN LAB</p>'
    out['fits']=measure(case.app,value,parts,'A3',*FORMATS['A3'],folder/'fits',cancel,lambda _:None,log)
    out['fits_9_16']=measure(case.app,value,parts,'9:16',*FORMATS['9:16'],folder/'portrait',cancel,lambda _:None,log)
    growing=copy.deepcopy(value);growing['zones'][0]['bbox']=[60,60,500,150];grow_parts=fragments(growing);grow_parts['title']='<p style="margin:0;font-size:150px;white-space:nowrap">OPEN LAB</p>'
    out['growth_remeasured']=measure_before_background(case.app,growing,grow_parts,'A3',*FORMATS['A3'],folder/'growth',cancel,lambda _:None,log,options())
    parts['title']='<p style="margin:0;font-size:600px;white-space:nowrap">OPEN LAB</p>'
    try:measure(case.app,value,parts,'A3',*FORMATS['A3'],folder/'overflow',cancel,lambda _:None,log)
    except ValueError as error:out['overflow_rejected']=str(error)
    else:raise AssertionError('Huge lettering must be rejected inside the small reserved zone.')
    if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(out,ensure_ascii=False))
finally:
    case.app.close()
    # The private browser's Windows file handles may close just after IPC exits.
    for attempt in range(20):
        try:case.tmp.cleanup();break
        except PermissionError:
            if attempt==19:raise
            time.sleep(.1)
