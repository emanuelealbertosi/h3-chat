import socket
import unittest
from unittest.mock import patch
from h3chat.agent_browser_proxy import public_endpoint,PublicProxy


class BrowserProxy(unittest.TestCase):
    def test_private_mixed_and_mapped_dns_are_rejected(self):
        for ip in ('127.0.0.1','10.0.0.1','169.254.169.254','::1','::ffff:127.0.0.1'):
            rows=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443)),
                  (socket.AF_INET6 if ':' in ip else socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443))]
            with self.subTest(ip=ip),patch('socket.getaddrinfo',return_value=rows),self.assertRaises(ValueError):public_endpoint('example.com',443)

    def test_public_dns_returns_numeric_endpoint(self):
        rows=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]
        with patch('socket.getaddrinfo',return_value=rows):self.assertEqual(public_endpoint('example.com',443)[-1],('93.184.216.34',443))
        with self.assertRaises(ValueError):public_endpoint('example.com',22)

    def test_real_proxy_denies_loopback_and_credentials_without_connecting(self):
        proxy=PublicProxy();self.addCleanup(proxy.close)
        for target in ('127.0.0.1:443','localhost:443','user:secret@example.com:443','example.com:22'):
            with self.subTest(target=target),socket.create_connection(proxy.server.server_address,timeout=3) as client:
                client.sendall(('CONNECT '+target+' HTTP/1.1\r\nHost: ignored\r\n\r\n').encode())
                self.assertIn(b'403 Forbidden',client.recv(1024))
        self.assertEqual(proxy.allowed,0)

    def test_quota_is_shared_and_bounded(self):
        proxy=PublicProxy(maximum=10);self.addCleanup(proxy.close)
        proxy.account(8)
        with self.assertRaises(ValueError):proxy.account(3)
