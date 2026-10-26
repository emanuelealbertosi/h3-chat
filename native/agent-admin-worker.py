"""Unprivileged IPC endpoint, invoked only after a concrete human approval."""
import json
from pathlib import Path
import sys
import traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import os
if os.name=='nt':from h3chat.computer_admin import elevate
else:from h3chat.posix_admin import elevate
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**data):wire.write(json.dumps({'event':event,**data},ensure_ascii=False)+'\n');wire.flush()
if __name__=='__main__':
    emit('hello')
    for line in sys.stdin:
        try:
            value=json.loads(line);emit('stage',message='Agent · conferma amministratore del sistema richiesta');emit('result',result=elevate(ROOT,value['command'],value['folder'],value['timeout']))
        except Exception as error:traceback.print_exc();emit('error',message=str(error))
