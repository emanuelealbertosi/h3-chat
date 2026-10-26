"""Desktop Secret Service storage. Never store an API key in plain JSON."""
import secrets
import sys
from pathlib import Path


def protect(value,decode=False):
    if not value:return ''
    packages=Path(__file__).resolve().parents[1]/'runtime/tools/documents'
    sys.path.insert(0,str(packages))
    try:
        import secretstorage
        bus=secretstorage.dbus_init()
        collection=secretstorage.get_default_collection(bus)
        if collection.is_locked() and collection.unlock():raise ValueError('Portachiavi bloccato.')
        if decode:
            if not value.startswith('secretservice:'):raise ValueError('Chiave di un altro sistema: inseriscila di nuovo sul computer Linux.')
            ident=value.partition(':')[2]
            if len(ident)!=32 or any(c not in '0123456789abcdef' for c in ident):raise ValueError('Riferimento chiave non valido.')
            for item in collection.search_items({'application':'H3-Chat','id':ident}):return item.get_secret().decode('utf8')
            raise ValueError('Chiave non presente nel portachiavi di questo utente.')
        ident=secrets.token_hex(16)
        collection.create_item('H3-Chat API',{'application':'H3-Chat','id':ident},value.encode('utf8'),replace=False,content_type='text/plain')
        return 'secretservice:'+ident
    except ImportError as exc:raise ValueError('Portachiavi Linux non installato: reinstalla i componenti documenti H3.') from exc
    except Exception as exc:
        if isinstance(exc,ValueError):raise
        raise ValueError('Portachiavi Linux non disponibile o bloccato. Avvia GNOME Keyring/KWallet con Secret Service nella sessione desktop; nessuna chiave salvata in chiaro.') from exc
    finally:
        try:bus.close()
        except (NameError,AttributeError):pass
