import base64,hashlib,json,socket,struct,threading,unittest
from h3chat.agent_browser_cdp import CDP


class CDPTransport(unittest.TestCase):
    def endpoint(self,handler):
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1);self.addCleanup(listener.close)
        errors=[]
        def server():
            try:
                connection,_=listener.accept()
                with connection:
                    connection.settimeout(3);header=b''
                    while b'\r\n\r\n' not in header:header+=connection.recv(4096)
                    key=next(line.split(b':',1)[1].strip() for line in header.split(b'\r\n') if line.lower().startswith(b'sec-websocket-key:'))
                    accept=base64.b64encode(hashlib.sha1(key+b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest())
                    connection.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n')
                    handler(connection)
            except Exception as exc:errors.append(exc)
        thread=threading.Thread(target=server,daemon=True);thread.start()
        self.addCleanup(thread.join,4)
        return f'ws://127.0.0.1:{listener.getsockname()[1]}/devtools/browser/test',errors,thread

    @staticmethod
    def request(connection):
        def read(size):
            value=b''
            while len(value)<size:
                block=connection.recv(size-len(value))
                if not block:raise OSError('closed')
                value+=block
            return value
        first,second=read(2);size=second&127
        if size==126:size=struct.unpack('!H',read(2))[0]
        elif size==127:size=struct.unpack('!Q',read(8))[0]
        assert second&128
        mask=read(4);body=read(size)
        return first&15,bytes(v^mask[i%4] for i,v in enumerate(body))

    @staticmethod
    def frame(value,opcode=1,final=True):
        body=value if isinstance(value,bytes) else json.dumps(value).encode();size=len(body)
        header=bytes([(128 if final else 0)|opcode,size if size<126 else 126 if size<65536 else 127])
        if size>=126:header+=struct.pack('!H',size) if size<65536 else struct.pack('!Q',size)
        return header+body

    def test_masked_command_events_ping_and_fragmented_response(self):
        def handler(connection):
            opcode,raw=self.request(connection);message=json.loads(raw)
            self.assertEqual(opcode,1);self.assertEqual(message['sessionId'],'owned-session')
            connection.sendall(self.frame({'method':'Browser.downloadProgress','params':{'state':'completed'}})+self.frame(b'hello',9))
            self.assertEqual(self.request(connection),(10,b'hello'))
            response=json.dumps({'id':message['id'],'result':{'value':'ok'}}).encode();middle=len(response)//2
            connection.sendall(self.frame(response[:middle],final=False)+self.frame(response[middle:],opcode=0))
        url,errors,thread=self.endpoint(handler);events=[]
        client=CDP(url,events.append);self.addCleanup(client.close)
        self.assertEqual(client.call('Page.enable',{'text':'x'*200},'owned-session'),{'value':'ok'})
        thread.join(4);self.assertFalse(errors);self.assertEqual(events[0]['method'],'Browser.downloadProgress')

    def test_native_error_is_reported_without_retry(self):
        def handler(connection):
            _,raw=self.request(connection);message=json.loads(raw)
            connection.sendall(self.frame({'id':message['id'],'error':{'code':-1,'message':'not found'}}))
        url,errors,thread=self.endpoint(handler);client=CDP(url);self.addCleanup(client.close)
        with self.assertRaisesRegex(RuntimeError,'not found'):client.call('Page.unknown')
        thread.join(4);self.assertFalse(errors)

    def test_local_endpoint_only(self):
        for url in ('ws://example.com:80/a','wss://127.0.0.1:5/a','ws://user@localhost:5/a','ws://localhost:5/a?secret=x','ws://localhost/a'):
            with self.subTest(url=url),self.assertRaises(ValueError):CDP(url)

    def test_evaluate_cannot_silently_accept_page_exception(self):
        def handler(connection):
            _,raw=self.request(connection);message=json.loads(raw)
            self.assertEqual(message['params']['expression'],'trusted fixture expression')
            connection.sendall(self.frame({'id':message['id'],'result':{'exceptionDetails':{'text':'stale'}}}))
        url,errors,thread=self.endpoint(handler);client=CDP(url);self.addCleanup(client.close)
        with self.assertRaisesRegex(ValueError,'pagina cambiato'):client.evaluate('trusted fixture expression','owned')
        thread.join(4);self.assertFalse(errors)
