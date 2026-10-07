import http.cookiejar
import json
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from app import Handler,ThreadingHTTPServer
from h3chat.access import Access,LoginRequired,LoginLimited,password_matches
from h3chat.service import Service
from h3chat.workspaces import Workspaces

ROOT=Path(__file__).resolve().parents[1]
PASSWORD='Una password di prova 2026!'


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.access=Access(self.temp.name)
        self.owner=self.access.create({'name':'owner','password':PASSWORD},owner=True)
        self.guest=self.access.create({'name':'amico','password':PASSWORD})

    def tearDown(self):self.temp.cleanup()

    def test_hash_sessions_key_revocation_expiry_and_no_plain_secrets(self):
        with self.access.connect() as db:stored=db.execute('SELECT password FROM users WHERE id=?',(self.guest['id'],)).fetchone()[0]
        self.assertNotIn(PASSWORD,stored);self.assertTrue(password_matches(PASSWORD,stored))
        key=self.access.create_key(self.owner,{'user_id':self.guest['id'],'name':'Prova','days':7})
        self.assertEqual(self.access.key_user(key['key'])['id'],self.guest['id'])
        raw,csrf=self.access.login({'key':key['key']},'test')
        with self.access.connect() as db:
            self.assertNotIn(key['key'],str(db.execute('SELECT * FROM access_keys').fetchall()))
            self.assertNotIn(raw,str(db.execute('SELECT * FROM sessions').fetchall()))
        self.access.revoke_key(self.owner,key['id'])
        self.assertIsNone(self.access.key_user(key['key']))

    def test_key_sessions_do_not_outlive_key_and_stale_login_cannot_restore_access(self):
        key=self.access.create_key(self.guest,{})
        with self.access.connect() as db:db.execute('UPDATE access_keys SET expires=?',(time.time()+20,))
        self.access.login({'key':key['key']},'test')
        with self.access.connect() as db:
            expires=db.execute('SELECT expires FROM sessions').fetchone()[0]
            verified=dict(db.execute('SELECT * FROM users WHERE id=?',(self.guest['id'],)).fetchone())
        self.assertLess(expires,time.time()+21)
        self.access.change_password(self.guest['id'],PASSWORD+' new')
        with self.assertRaises(LoginRequired):self.access.session(verified)
        with self.access.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],0)
        key=self.access.create_key(self.guest,{'name':'Scadenza','days':1})
        with self.access.connect() as db:db.execute('UPDATE access_keys SET expires=?',(time.time()-1,))
        self.assertIsNone(self.access.key_user(key['key']))

    def test_failed_logins_limited_and_good_logins_do_not_exhaust_budget(self):
        for _ in range(10):self.access.login({'name':'amico','password':PASSWORD},'good-peer')
        for _ in range(8):
            with self.assertRaises(LoginRequired):self.access.login({'name':'amico','password':'wrong'},'bad-peer')
        with self.assertRaises(LoginLimited):self.access.login({'name':'amico','password':PASSWORD},'bad-peer')

    def test_guest_cannot_issue_owner_key_password_changes_revoke_access(self):
        with self.assertRaises(PermissionError):self.access.create_key(self.guest,{'user_id':'owner'})
        key=self.access.create_key(self.guest,{})
        self.access.change_password(self.guest['id'],PASSWORD+' new')
        self.assertIsNone(self.access.key_user(key['key']))
        with self.assertRaises(LoginRequired):self.access.login({'name':'amico','password':PASSWORD},'test')
        self.access.login({'name':'amico','password':PASSWORD+' new'},'test')
        self.access.enabled(self.guest['id'],False)
        with self.assertRaises(LoginRequired):self.access.login({'name':'amico','password':PASSWORD+' new'},'test')


class AccessHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=Service(ROOT,Path(self.temp.name),start_worker=False)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.app=self.app
        self.server.access=Access(self.app.data);self.server.workspaces=Workspaces(self.app,start_workers=False)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
        self.owner=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.guest=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.server.workspaces.close();self.app.close();self.temp.cleanup()

    def request(self,path,body=None,method=None,client=None,csrf=None,headers=None):
        headers=headers or {}
        if body is not None:headers['Content-Type']='application/json'
        if csrf is not None:headers['X-H3-Token']=csrf
        req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
        try:
            with (client or urllib.request.build_opener()).open(req,timeout=30) as response:
                raw=response.read();return response.status,json.loads(raw) if response.headers.get_content_type()=='application/json' else raw,response.headers
        except urllib.error.HTTPError as exc:return exc.code,json.load(exc),exc.headers

    def setup_owner(self):
        _,me,_=self.request('/api/auth/me')
        status,_,headers=self.request('/api/auth/setup',{'name':'owner','password':PASSWORD},client=self.owner,csrf=me['csrf'])
        self.assertEqual(status,201);self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie'])
        return self.request('/api/auth/me',client=self.owner)[1]['csrf']

    def test_bootstrap_and_maintenance_require_true_local_requests(self):
        _,me,_=self.request('/api/auth/me',headers={'Tailscale-User-Login':'external@example.com'})
        self.assertIsNone(me['user']);self.assertEqual(me['csrf'],'')
        self.assertEqual(self.request('/api/state',headers={'Tailscale-User-Login':'external@example.com'})[0],401)
        self.setup_owner()
        self.assertEqual(self.request('/api/maintenance/state',csrf=self.server.access.maintenance)[0],200)
        self.assertEqual(self.request('/api/maintenance/state',csrf=self.server.access.maintenance,headers={'Tailscale-User-Login':'external@example.com'})[0],401)

    def test_login_and_complete_workspace_isolation_including_files_and_api_ids(self):
        secret=self.app.store.create_chat('Chat privata amministratore')
        self.app.store.execute("INSERT INTO messages(id,chat_id,role,content,created) VALUES ('private',?,'user','documento privato',0)",(secret['id'],))
        private=self.app.data/'uploads/private.txt';private.parent.mkdir(exist_ok=True);private.write_text('segreto')
        csrf=self.setup_owner()
        self.assertEqual(self.request('/api/state')[0],401)
        self.assertEqual(self.request('/media/uploads/private.txt')[0],401)
        _,guest,_=self.request('/api/auth/users',{'name':'amico','password':PASSWORD},client=self.owner,csrf=csrf)
        self.assertEqual(self.request('/api/auth/login',{'name':'amico','password':PASSWORD},client=self.guest)[0],200)
        gcsrf=self.request('/api/auth/me',client=self.guest)[1]['csrf']
        _,state,_=self.request('/api/state',client=self.guest)
        self.assertEqual(state['chats'],[]);self.assertEqual(state['projects'],[])
        self.assertNotEqual(state['token'],self.app.token)
        self.assertEqual(self.request('/api/chats/'+secret['id'],client=self.guest)[0],400)
        self.assertEqual(self.request('/media/uploads/private.txt',client=self.guest)[0],404)
        self.assertEqual(self.request('/api/model-files/browse',{},client=self.guest,csrf=gcsrf)[0],403)
        self.assertEqual(self.request('/api/providers',{},client=self.guest,csrf=gcsrf)[0],403)
        self.assertEqual(self.request('/api/chats',{},client=self.guest)[0],403)
        _,chat,_=self.request('/api/chats',{},client=self.guest,csrf=gcsrf)
        self.assertIsNone(self.app.store.one('SELECT id FROM chats WHERE id=?',(chat['id'],)))
        _,project,_=self.request('/api/projects',{'name':'RAG ospite'},client=self.guest,csrf=gcsrf)
        self.assertIsNone(self.app.store.one('SELECT id FROM projects WHERE id=?',(project['id'],)))
        self.assertEqual(self.request('/api/projects/'+project['id']+'/sources',{'paths':[str(private)]},client=self.guest,csrf=gcsrf)[0],403)
        self.assertEqual(self.request('/api/settings',{'voice_model_path':str(private)},client=self.guest,csrf=gcsrf)[0],403)
        self.assertEqual(self.request('/api/settings',{'vision_enabled':False},client=self.guest,csrf=gcsrf)[0],200)
        self.assertTrue(self.app.store.settings()['vision_enabled'])
        self.assertEqual(self.request('/api/auth/users/'+guest['id'],{'enabled':False},method='PATCH',client=self.owner,csrf=csrf)[0],200)
        self.assertEqual(self.request('/api/state',client=self.guest)[0],401)
        self.assertTrue((self.app.data/'workspaces'/guest['id']/'chat.sqlite').exists())

    def test_bearer_key_access_scoped_and_immediately_revoked(self):
        csrf=self.setup_owner()
        _,guest,_=self.request('/api/auth/users',{'name':'amico','password':PASSWORD},client=self.owner,csrf=csrf)
        _,key,_=self.request('/api/auth/keys',{'user_id':guest['id']},client=self.owner,csrf=csrf)
        headers={'Authorization':'Bearer '+key['key']}
        self.assertEqual(self.request('/api/chats',{},headers=headers)[0],201)
        self.assertEqual(self.request('/api/shutdown',{},headers=headers)[0],403)
        self.assertEqual(self.request('/api/auth/keys/'+key['id'],{},method='DELETE',client=self.owner,csrf=csrf)[0],200)
        self.assertEqual(self.request('/api/state',headers=headers)[0],401)

    def test_cross_site_login_rejected(self):
        self.setup_owner()
        self.assertEqual(self.request('/api/auth/login',{'name':'owner','password':PASSWORD},headers={'Origin':'https://other.invalid'})[0],403)

    def test_https_login_cookie_secure_and_session_logout(self):
        self.setup_owner()
        self.server.network=SimpleNamespace(origins={'https://test.example.ts.net:8788'},status={})
        headers={'Host':'test.example.ts.net:8788','Origin':'https://test.example.ts.net:8788','Tailscale-User-Login':'friend@example.com'}
        status,_,response=self.request('/api/auth/login',{'name':'owner','password':PASSWORD},headers=headers)
        self.assertEqual(status,200);self.assertIn('; Secure',response['Set-Cookie'])
        self.assertEqual(self.request('/api/auth/logout',{},client=self.owner,csrf=self.request('/api/auth/me',client=self.owner)[1]['csrf'])[0],200)
        self.assertEqual(self.request('/api/state',client=self.owner)[0],401)


class ComputeQueueTests(unittest.TestCase):
    def test_users_execute_serially_and_release_other_models(self):
        from unittest.mock import Mock
        entered=threading.Event();finish=threading.Event();second=threading.Event();compute=threading.RLock()
        def app(callback):
            return SimpleNamespace(compute_lock=compute,knowledge=SimpleNamespace(embeddings=Mock()),engine=Mock(),
                store=SimpleNamespace(execute=Mock(),settings=lambda:{'rag_device':'cpu'}),execute_job=callback)
        owner=app(lambda job,cancel:(entered.set(),finish.wait(5)))
        guest=app(lambda job,cancel:second.set());spaces=Workspaces(owner,start_workers=False);spaces.items['guest']=guest;spaces.wrap(guest)
        a=threading.Thread(target=owner.execute_job,args=({'id':'first'},threading.Event()))
        b=threading.Thread(target=guest.execute_job,args=({'id':'second'},threading.Event()))
        a.start();self.assertTrue(entered.wait(2));b.start();self.assertFalse(second.wait(.3));finish.set();a.join(3);b.join(3)
        self.assertTrue(second.is_set());self.assertTrue(guest.store.execute.called)
        owner.engine.stop.assert_called_once();guest.engine.stop.assert_called_once()


if __name__=='__main__':unittest.main()
