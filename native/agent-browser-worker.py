"""One run's private CPU browser; finite IPC operations, never generated code."""
import json,os,signal,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**value):wire.write(json.dumps({'event':event,**value},ensure_ascii=False)+'\n');wire.flush()

if __name__=='__main__':
    from h3chat.agent_browser_native import Browser
    browser=None
    if os.name!='nt':signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
    try:
        emit('hello')
        for line in sys.stdin:
            try:
                request=json.loads(line)
                if not browser:
                    if request.get('op')!='start':raise ValueError('Avvia prima il browser dedicato.')
                    folder=Path(request['folder']).resolve()
                    if folder.name!='browser' or folder.parent.name!='agent':raise ValueError('Cartella browser Agent non valida.')
                    browser=Browser(ROOT,folder);result={'started':True,'pid':browser.process.pid}
                elif request.get('op')=='close':browser.close();emit('result',result={'closed':True});break
                else:result=browser.run(request.get('op'),request.get('args',{}))
                emit('result',result=result)
            except Exception as exc:traceback.print_exc();emit('error',message=str(exc))
    finally:
        if browser:browser.close()
