"""Small local-only CDP transport with event capture; no third-party runtime."""
import base64
import hashlib
import json
import os
import socket
import struct
import threading
import time
from urllib.parse import urlsplit


class CDP:
    def __init__(self,url,on_event=None):
        parsed=urlsplit(url)
        if parsed.scheme!='ws' or parsed.hostname not in ('127.0.0.1','localhost') or not parsed.port or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Endpoint del browser non valido.')
        self.sock=socket.create_connection(('127.0.0.1',parsed.port),timeout=30)
        self.buffer=b'';self.seq=0;self.lock=threading.Lock();self.on_event=on_event
        key=base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f'GET {parsed.path} HTTP/1.1\r\nHost: 127.0.0.1:{parsed.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        try:
            while b'\r\n\r\n' not in self.buffer:
                block=self.sock.recv(4096)
                if not block or len(self.buffer)>32768:raise ValueError('Handshake del browser incompleto.')
                self.buffer+=block
            header,self.buffer=self.buffer.split(b'\r\n\r\n',1)
            lines=header.decode('ascii').split('\r\n');headers={}
            for line in lines[1:]:
                name,_,value=line.partition(':');headers[name.strip().lower()]=value.strip()
            expected=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
            if not lines[0].startswith('HTTP/1.1 101 ') or headers.get('sec-websocket-accept')!=expected:
                raise ValueError('Handshake del browser non verificato.')
        except BaseException:self.sock.close();raise

    def read(self,count):
        while len(self.buffer)<count:
            block=self.sock.recv(max(4096,count-len(self.buffer)))
            if not block:raise OSError('Il browser si è chiuso.')
            self.buffer+=block
        value,self.buffer=self.buffer[:count],self.buffer[count:];return value

    def send(self,value,opcode=1):
        payload=value if isinstance(value,bytes) else value.encode();size=len(payload)
        if size>4*1024**2:raise ValueError('Comando browser troppo grande.')
        mask=os.urandom(4)
        header=bytes([128|opcode,128|(size if size<126 else 126 if size<65536 else 127)])
        if size>=126:header+=struct.pack('!H',size) if size<65536 else struct.pack('!Q',size)
        self.sock.sendall(header+mask+bytes(v^mask[i%4] for i,v in enumerate(payload)))

    def message(self):
        chunks=[];total=0
        while True:
            first,second=self.read(2);length=second&127;opcode=first&15
            if second&128:raise ValueError('Frame server browser non valido.')
            if length==126:length=struct.unpack('!H',self.read(2))[0]
            elif length==127:length=struct.unpack('!Q',self.read(8))[0]
            if length>32*1024**2:raise ValueError('Risposta browser troppo grande.')
            body=self.read(length)
            if opcode==9:self.send(body,10);continue
            if opcode==8:raise OSError('Browser disconnesso.')
            if opcode==10:continue
            if opcode not in (0,1):raise ValueError('Frame browser non testuale.')
            total+=len(body)
            if total>32*1024**2:raise ValueError('Risposta browser troppo grande.')
            chunks.append(body)
            if first&128:return json.loads(b''.join(chunks))

    def call(self,method,params=None,session=None,timeout=30):
        with self.lock:
            self.seq+=1;ident=self.seq
            request={'id':ident,'method':method,'params':params or {}}
            if session:request['sessionId']=session
            self.send(json.dumps(request));deadline=time.monotonic()+timeout
            try:
                while True:
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise TimeoutError('Risposta browser scaduta; verifica lo stato prima di ripetere azioni.')
                    self.sock.settimeout(remaining);value=self.message()
                    if value.get('id')==ident:
                        if value.get('error'):raise RuntimeError('Browser: '+str(value['error'])[:800])
                        return value.get('result',{})
                    if value.get('method') and self.on_event:self.on_event(value)
            finally:self.sock.settimeout(30)

    def evaluate(self,expression,session,await_promise=False):
        result=self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':await_promise},session)
        if result.get('exceptionDetails'):raise ValueError('Elemento della pagina cambiato o operazione browser non consentita. Osserva di nuovo la pagina.')
        return result.get('result',{}).get('value')

    def close(self):
        try:self.sock.close()
        except OSError:pass
