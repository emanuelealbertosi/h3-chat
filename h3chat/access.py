"""Password sessions and revocable API keys, separate from the chat database."""
import hashlib
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from http.cookies import SimpleCookie
from pathlib import Path

COOKIE='h3_session'
SESSION_SECONDS=12*3600
ITERATIONS=600000


class LoginRequired(PermissionError):pass
class LoginLimited(ValueError):pass


def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),ITERATIONS).hex()


def password_matches(password,stored):
    salt,_=stored.split(':',1)
    return secrets.compare_digest(password_hash(password,salt),stored)


def digest(value):return hashlib.sha256(value.encode()).hexdigest()


def validate_password(value):
    if not isinstance(value,str) or not 12<=len(value)<=256:
        raise ValueError('Usa una password da 12 a 256 caratteri.')


def local_request(handler):
    # Serve reaches loopback too. Its identity / proxy headers must not turn
    # remote requests into local bootstrap or maintenance requests.
    host=handler.headers.get('Host','')
    return (host in (f'127.0.0.1:{handler.server.server_port}',f'localhost:{handler.server.server_port}')
        and handler.client_address[0] in ('127.0.0.1','::1')
        and not any(k.lower().startswith(('tailscale-','x-forwarded-')) or k.lower()=='forwarded' for k in handler.headers))


class Access:
    def __init__(self,data):
        self.data=Path(data);self.data.mkdir(parents=True,exist_ok=True)
        self.path=self.data/'access.sqlite';self.lock=threading.RLock();self.verifiers=threading.BoundedSemaphore(2)
        self.maintenance=secrets.token_hex(32)
        (self.data/'maintenance-token.txt').write_text(self.maintenance,encoding='ascii')
        self.dummy=password_hash(secrets.token_hex(32))
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,role TEXT NOT NULL,password TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,created REAL NOT NULL,epoch INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,csrf TEXT NOT NULL,expires REAL NOT NULL,key_id TEXT,epoch INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS access_keys(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,hash TEXT UNIQUE NOT NULL,expires REAL NOT NULL,created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS login_limits(bucket TEXT PRIMARY KEY,count INTEGER NOT NULL,until REAL NOT NULL);
            ''')
            for table in ('users','sessions'):
                if 'epoch' not in {r['name'] for r in db.execute('PRAGMA table_info('+table+')')}:db.execute('ALTER TABLE '+table+' ADD COLUMN epoch INTEGER NOT NULL DEFAULT 0')
            db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:yield db
        finally:db.close()

    def configured(self):
        with self.connect() as db:return bool(db.execute("SELECT 1 FROM users WHERE role='owner'").fetchone())

    def identity(self,handler):
        if not self.configured() and local_request(handler):
            return {'id':'bootstrap','name':'Sul tuo PC','role':'owner','csrf':handler.server.app.token,'bootstrap':True}
        authorization=handler.headers.get('Authorization','')
        if authorization:
            if not authorization.startswith('Bearer '):return None
            user=self.key_user(authorization[7:])
            return user|{'csrf':'','bearer':True} if user else None
        cookie=SimpleCookie()
        try:cookie.load(handler.headers.get('Cookie',''));value=cookie[COOKIE].value if COOKIE in cookie else ''
        except Exception:return None
        if not 20<=len(value)<=200:return None
        with self.connect() as db:
            now=time.time()
            row=db.execute('SELECT u.id,u.name,u.role,s.csrf,s.hash FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.hash=? AND s.expires>? AND u.enabled=1 AND s.epoch=u.epoch AND (s.key_id IS NULL OR EXISTS (SELECT 1 FROM access_keys k WHERE k.id=s.key_id AND k.expires>?))',(digest(value),now,now)).fetchone()
        return dict(row) if row else None

    def key_user(self,key):
        if not isinstance(key,str) or not 20<=len(key)<=200:return None
        with self.connect() as db:
            row=db.execute('SELECT u.id,u.name,u.role,u.epoch,k.id AS key_id FROM access_keys k JOIN users u ON u.id=k.user_id WHERE k.hash=? AND k.expires>? AND u.enabled=1',(digest(key),time.time())).fetchone()
        return dict(row) if row else None

    def session(self,user,key_id=None):
        raw=secrets.token_urlsafe(32);csrf=secrets.token_hex(32)
        with self.connect() as db:
            current=db.execute('SELECT epoch FROM users WHERE id=? AND enabled=1',(user['id'],)).fetchone()
            if not current or user.get('epoch',0)!=current['epoch']:raise LoginRequired('Accesso revocato. Accedi di nuovo.')
            expires=time.time()+SESSION_SECONDS
            if key_id:
                key=db.execute('SELECT expires FROM access_keys WHERE id=? AND user_id=? AND expires>?',(key_id,user['id'],time.time())).fetchone()
                if not key:raise LoginRequired('Chiave scaduta o revocata.')
                expires=min(expires,key['expires'])
            db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?)',(digest(raw),user['id'],csrf,expires,key_id,user.get('epoch',0)))
        return raw,csrf

    def cookie(self,raw,secure=False):
        return f'{COOKIE}={raw}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_SECONDS if raw else 0}'+('; Secure' if secure else '')

    def login(self,body,peer):
        name=body.get('name','');password=body.get('password','');key=body.get('key')
        if not isinstance(name,str) or not isinstance(password,str) or len(name)>80 or len(password)>256:
            raise LoginRequired('Credenziali non valide.')
        buckets=['name:'+digest(name.lower() if not key else 'key-login'),'peer:'+digest(peer)]
        with self.lock:
            now=time.time()
            with self.connect() as db:
                db.execute('DELETE FROM login_limits WHERE until<?',(now,))
                for bucket in buckets:
                    row=db.execute('SELECT count FROM login_limits WHERE bucket=?',(bucket,)).fetchone()
                    if row and row['count']>=8:raise LoginLimited('Troppi tentativi. Riprova tra 10 minuti.')
        if not self.verifiers.acquire(blocking=False):raise LoginLimited('Accessi in verifica. Riprova tra pochi secondi.')
        try:
            if key:user=self.key_user(key)
            else:
                with self.connect() as db:row=db.execute('SELECT * FROM users WHERE name=? COLLATE NOCASE',(name.strip(),)).fetchone()
                match=password_matches(password,row['password'] if row else self.dummy)
                user=dict(row) if match and row and row['enabled'] else None
            if not user:
                with self.lock,self.connect() as db:
                    for bucket in buckets:db.execute('INSERT INTO login_limits VALUES (?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1',(bucket,time.time()+600))
                raise LoginRequired('Nome, password o chiave non validi.')
            # Do not reset the peer bucket: rotating guessed names must remain bounded.
            with self.connect() as db:db.execute('DELETE FROM login_limits WHERE bucket=?',(buckets[0],))
            return self.session(user,user.get('key_id'))
        finally:self.verifiers.release()

    def create(self,body,owner=False):
        name=body.get('name','');password=body.get('password','')
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,50}',name):raise ValueError('Nome utente: 3–50 lettere, numeri, punti, trattini o underscore.')
        validate_password(password);hashed=password_hash(password)
        with self.lock,self.connect() as db:
            if owner and db.execute("SELECT 1 FROM users WHERE role='owner'").fetchone():raise ValueError('Amministratore già configurato.')
            if db.execute('SELECT COUNT(*) FROM users').fetchone()[0]>=20:raise ValueError('Massimo 20 account.')
            ident='owner' if owner else secrets.token_hex(16)
            try:db.execute('INSERT INTO users(id,name,role,password,enabled,created) VALUES (?,?,?,?,1,?)',(ident,name.lower(),'owner' if owner else 'guest',hashed,time.time()))
            except sqlite3.IntegrityError:raise ValueError('Nome utente già presente.')
        return {'id':ident,'name':name.lower(),'role':'owner' if owner else 'guest'}

    def users(self):
        with self.connect() as db:return [dict(r) for r in db.execute('SELECT id,name,role,enabled,created FROM users ORDER BY created')]

    def enabled(self,ident,value):
        if type(value) is not bool:raise ValueError('Stato account non valido.')
        with self.lock,self.connect() as db:
            user=db.execute('SELECT * FROM users WHERE id=?',(ident,)).fetchone()
            if not user or user['role']=='owner':raise ValueError('Scegli un account ospite.')
            db.execute('UPDATE users SET enabled=?,epoch=epoch+1 WHERE id=?',(value,ident))
            if not value:self.revoke_user(db,ident)

    @staticmethod
    def revoke_user(db,ident):
        db.execute('DELETE FROM sessions WHERE user_id=?',(ident,));db.execute('DELETE FROM access_keys WHERE user_id=?',(ident,))

    def change_password(self,ident,password):
        validate_password(password);hashed=password_hash(password)
        with self.lock,self.connect() as db:
            if not db.execute('SELECT 1 FROM users WHERE id=?',(ident,)).fetchone():raise ValueError('Account non trovato.')
            db.execute('UPDATE users SET password=?,epoch=epoch+1 WHERE id=?',(hashed,ident));self.revoke_user(db,ident)

    def keys(self,identity):
        with self.connect() as db:
            query='SELECT k.id,k.user_id,k.name,k.expires,u.name AS username FROM access_keys k JOIN users u ON u.id=k.user_id'
            return [dict(r) for r in db.execute(query if identity['role']=='owner' else query+' WHERE k.user_id=?',() if identity['role']=='owner' else (identity['id'],))]

    def create_key(self,identity,body):
        user_id=body.get('user_id',identity['id']);days=body.get('days',7);name=body.get('name','Chiave API')
        if identity['role']!='owner' and user_id!=identity['id']:raise PermissionError('Account non consentito.')
        if type(days) is not int or not 1<=days<=90 or not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('Nome chiave e scadenza (1–90 giorni) non validi.')
        raw='h3_'+secrets.token_urlsafe(32);ident=secrets.token_hex(16);now=time.time()
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM users WHERE id=? AND enabled=1',(user_id,)).fetchone():raise ValueError('Account non disponibile.')
            if db.execute('SELECT COUNT(*) FROM access_keys WHERE user_id=?',(user_id,)).fetchone()[0]>=20:raise ValueError('Massimo 20 chiavi per account.')
            db.execute('INSERT INTO access_keys VALUES (?,?,?,?,?,?)',(ident,user_id,name.strip(),digest(raw),now+days*86400,now))
        return {'id':ident,'key':raw,'expires':now+days*86400}

    def revoke_key(self,identity,ident):
        with self.connect() as db:
            row=db.execute('SELECT user_id FROM access_keys WHERE id=?',(ident,)).fetchone()
            if not row or identity['role']!='owner' and row['user_id']!=identity['id']:raise PermissionError('Chiave non disponibile.')
            db.execute('DELETE FROM access_keys WHERE id=?',(ident,));db.execute('DELETE FROM sessions WHERE key_id=?',(ident,))

    def logout(self,identity):
        with self.connect() as db:db.execute('DELETE FROM sessions WHERE hash=?',(identity.get('hash',''),))
