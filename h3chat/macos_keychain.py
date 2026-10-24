"""API credentials in the user's macOS Keychain, never in process arguments."""
import ctypes as C
import re
import uuid

SERVICE=b'org.h3-chat.api-credentials'
PREFIX='keychain:'


def library():
    lib=C.CDLL('/System/Library/Frameworks/Security.framework/Security')
    lib.SecKeychainAddGenericPassword.argtypes=[C.c_void_p,C.c_uint32,C.c_char_p,C.c_uint32,C.c_char_p,C.c_uint32,C.c_void_p,C.c_void_p]
    lib.SecKeychainAddGenericPassword.restype=C.c_int32
    lib.SecKeychainFindGenericPassword.argtypes=[C.c_void_p,C.c_uint32,C.c_char_p,C.c_uint32,C.c_char_p,C.POINTER(C.c_uint32),C.POINTER(C.c_void_p),C.c_void_p]
    lib.SecKeychainFindGenericPassword.restype=C.c_int32
    lib.SecKeychainItemFreeContent.argtypes=[C.c_void_p,C.c_void_p]
    lib.SecKeychainItemFreeContent.restype=C.c_int32
    return lib


def protect(value,decode=False):
    lib=library()
    if not decode:
        account=uuid.uuid4().hex.encode('ascii');raw=value.encode('utf-8');buffer=C.create_string_buffer(raw)
        code=lib.SecKeychainAddGenericPassword(None,len(SERVICE),SERVICE,len(account),account,len(raw),buffer,None)
        if code:raise ValueError('Impossibile salvare la chiave API nel Portachiavi macOS. Sblocca il Portachiavi e riprova (codice '+str(code)+').')
        return PREFIX+account.decode('ascii')
    if not re.fullmatch(PREFIX+r'[a-f0-9]{32}',value):
        raise ValueError('Questa chiave API proviene da un altro sistema. Inseriscila nuovamente nelle impostazioni del Mac.')
    account=value[len(PREFIX):].encode('ascii');size=C.c_uint32();pointer=C.c_void_p()
    code=lib.SecKeychainFindGenericPassword(None,len(SERVICE),SERVICE,len(account),account,C.byref(size),C.byref(pointer),None)
    if code:raise ValueError('Chiave API non accessibile nel Portachiavi macOS. Sbloccalo o inserisci nuovamente la chiave (codice '+str(code)+').')
    try:return C.string_at(pointer,size.value).decode('utf-8')
    finally:lib.SecKeychainItemFreeContent(None,pointer)
