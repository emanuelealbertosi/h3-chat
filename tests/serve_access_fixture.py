"""Temporary accounts and synthetic documents; never opens production data."""
import json
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import Handler,ThreadingHTTPServer
from h3chat.service import Service
from h3chat.access import Access
from h3chat.workspaces import Workspaces


with tempfile.TemporaryDirectory(prefix='h3-access-') as folder:
    app=Service(ROOT,Path(folder),start_worker=False)
    app.store.save_settings({'setup_done':True})
    private=app.store.create_chat('Chat privata amministratore')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.app=app
    server.access=Access(app.data);server.workspaces=Workspaces(app,start_workers=False)
    print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','private_chat':private['id']}),flush=True)
    try:server.serve_forever()
    finally:server.server_close();server.workspaces.close();app.close()
