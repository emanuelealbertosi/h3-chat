"""Per-browser public-only HTTP proxy: pinned DNS, no direct/private fallback."""
import ipaddress
import select
import socket
import socketserver
import threading
import time
from urllib.parse import urlsplit


def public_endpoint(host,port):
    if port not in (80,443) or not host or any(ord(c)<33 for c in host):
        raise ValueError('Browser: destinazione non consentita.')
    addresses=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
    if not addresses:raise ValueError('Browser: DNS non disponibile.')
    for _,_,_,_,address in addresses:
        ip=ipaddress.ip_address(address[0])
        if not ip.is_global or ip.is_multicast or (ip.version==6 and ip.ipv4_mapped and not ip.ipv4_mapped.is_global):
            raise ValueError('Il browser Agent accetta soltanto destinazioni Internet pubbliche.')
    family,kind,proto,_,address=addresses[0]
    return family,kind,proto,address


class PublicProxy:
    def __init__(self,maximum=512*1024**2,resolver=public_endpoint):
        self.maximum=maximum;self.transferred=0;self.lock=threading.Lock();self.closed=threading.Event()
        self.resolver=resolver;self.connections=set();self.slots=threading.BoundedSemaphore(24)
        self.allowed=0;self.blocked=0
        owner=self
        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address=False;daemon_threads=True
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):owner.handle(self.request)
        self.server=Server(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    @property
    def address(self):return 'http://127.0.0.1:'+str(self.server.server_address[1])

    def account(self,size):
        with self.lock:
            self.transferred+=size
            if self.transferred>self.maximum:raise ValueError('Limite traffico browser raggiunto.')

    def handle(self,client):
        if not self.slots.acquire(blocking=False):return
        remote=None
        with self.lock:self.connections.add(client)
        try:
            client.settimeout(15);buffer=b''
            while b'\r\n\r\n' not in buffer:
                block=client.recv(4096)
                if not block:raise ValueError('Richiesta proxy incompleta.')
                buffer+=block
                if len(buffer)>32768:raise ValueError('Header proxy troppo grande.')
            header,body=buffer.split(b'\r\n\r\n',1)
            lines=header.decode('iso8859-1').split('\r\n');method,target,version=lines[0].split(' ',2)
            if method=='CONNECT':
                parsed=urlsplit('https://'+target)
                if parsed.path or parsed.query or parsed.fragment:raise ValueError('Tunnel non valido.')
                port=parsed.port or 443
            else:
                parsed=urlsplit(target);port=parsed.port or 80
                if parsed.scheme!='http':raise ValueError('Proxy richiede HTTP assoluto o CONNECT.')
            if parsed.username or parsed.password or port!=(443 if method=='CONNECT' else 80):raise ValueError('Destinazione proxy non valida.')
            family,kind,proto,address=self.resolver(parsed.hostname,port)
            remote=socket.socket(family,kind,proto);remote.settimeout(15)
            # Connect directly to the already validated numeric address; DNS is
            # never consulted again for the outgoing connection.
            remote.connect(address)
            with self.lock:self.allowed+=1;self.connections.add(remote)
            if method=='CONNECT':
                client.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                if body:remote.sendall(body);self.account(len(body))
            else:
                path=(parsed.path or '/')+('?' + parsed.query if parsed.query else '')
                forwarded=[f'{method} {path} HTTP/1.1']
                for line in lines[1:]:
                    key,sep,value=line.partition(':')
                    if not sep or key.strip().lower() in ('proxy-authorization','proxy-connection','connection','host'):continue
                    forwarded.append(line)
                forwarded.extend(['Host: '+parsed.netloc,'Connection: close','',''])
                remote.sendall('\r\n'.join(forwarded).encode('iso8859-1')+body)
                self.account(len(body))
            client.settimeout(15);remote.settimeout(15);deadline=time.monotonic()+180
            while not self.closed.is_set() and time.monotonic()<deadline:
                ready,_,_=select.select([client,remote],[],[],1)
                for source in ready:
                    block=source.recv(65536)
                    if not block:return
                    self.account(len(block));(remote if source is client else client).sendall(block)
        except (OSError,ValueError):
            with self.lock:self.blocked+=1
            try:client.sendall(b'HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n')
            except OSError:pass
        finally:
            for connection in (client,remote):
                if connection:
                    with self.lock:self.connections.discard(connection)
                    try:connection.close()
                    except OSError:pass
            self.slots.release()

    def close(self):
        if self.closed.is_set():return
        self.closed.set();self.server.shutdown();self.server.server_close()
        with self.lock:connections=list(self.connections)
        for connection in connections:
            try:connection.shutdown(socket.SHUT_RDWR);connection.close()
            except OSError:pass
        self.thread.join(timeout=3)
