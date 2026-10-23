"""Authenticated local API context. Calls have effects only when explicitly made.

Example: with Client() as c: state = c.call('/state')
Use writes only for the current human-authorized operation. Never print secrets.
"""
import json,sys,threading,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from h3_root import find_root

class Client:
    def __init__(self,root=None):
        self.root=find_root(root)
    def __enter__(self):
        sys.path.insert(0,str(self.root))
        from h3chat.access import Access,digest
        self.digest=digest;self.access=Access.__new__(Access);self.access.data=self.root/'data';self.access.path=self.access.data/'access.sqlite';self.access.lock=threading.RLock()
        self.port=json.loads((self.root/'data/port.json').read_text(encoding='utf-8'))
        with self.access.connect() as db:
            row=db.execute("SELECT id,name,role,epoch FROM users WHERE role='owner' AND enabled=1").fetchone()
            if row is None:raise ValueError('No enabled owner; use the correct authenticated account.')
            user=dict(row)
        self.raw,self.csrf=self.access.session(user)
        return self
    def __exit__(self,*args):
        with self.access.connect() as db:db.execute('DELETE FROM sessions WHERE hash=?',(self.digest(self.raw),))
        self.raw=self.csrf=None
    def call(self,path,body=None,*,method=None):
        if not isinstance(path,str) or not path.startswith('/') or path.startswith('//'):raise ValueError('Expected a local API path, without /api prefix.')
        req=urllib.request.Request(f'http://127.0.0.1:{self.port}/api'+path,data=None if body is None else json.dumps(body).encode('utf-8'),method=method,headers={'Cookie':'h3_session='+self.raw,'X-H3-Token':self.csrf,'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=120) as response:return json.load(response)
