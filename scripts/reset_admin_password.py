"""Local interactive owner recovery; no password in arguments or logs."""
import getpass
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from h3chat.access import password_hash,validate_password


def main():
    path=ROOT/'data/access.sqlite'
    if not path.is_file():raise SystemExit('Configura prima l’amministratore in Accessi.')
    password=getpass.getpass('Nuova password amministratore (almeno 12 caratteri): ')
    validate_password(password)
    if password!=getpass.getpass('Ripeti password: '):raise SystemExit('Le password non coincidono.')
    with sqlite3.connect(path) as db:
        user=db.execute("SELECT id FROM users WHERE role='owner'").fetchone()
        if not user:raise SystemExit('Account amministratore non trovato.')
        db.execute('UPDATE users SET password=?,epoch=epoch+1 WHERE id=?',(password_hash(password),user[0]))
        db.execute('DELETE FROM sessions WHERE user_id=?',(user[0],));db.execute('DELETE FROM access_keys WHERE user_id=?',(user[0],))
    print('Password aggiornata. Chat e documenti conservati.')


if __name__=='__main__':main()
