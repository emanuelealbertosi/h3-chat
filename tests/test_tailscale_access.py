import json
import threading
import unittest
import urllib.error
import urllib.request
from types import SimpleNamespace
from unittest.mock import patch

from app import Handler, ThreadingHTTPServer
from h3chat.tailscale_access import TailscaleAccess

NAME = 'test-pc.tail123456.ts.net'
TARGET = 'http://127.0.0.1:8788'


def config(port=8788, target=TARGET):
    return {'TCP': {str(port): {'HTTPS': True}},
            'Web': {f'{NAME}:{port}': {'Handlers': {'/': {'Proxy': target}}}}}


class TailscaleTests(unittest.TestCase):
    def refresh(self, replies):
        access = TailscaleAccess(8788)
        with patch('h3chat.tailscale_access.executable', return_value='tailscale'), \
                patch('h3chat.tailscale_access.run', side_effect=[json.dumps(x) for x in replies]) as calls:
            result = access.refresh()
        return access, result, calls

    def state(self):
        return {'BackendState': 'Running', 'Self': {'DNSName': NAME + '.'}}

    def test_existing_private_proxy_is_reused_without_changing_any_service(self):
        existing = config()
        existing['TCP']['443'] = {'HTTPS': True}
        existing['Web'][NAME + ':443'] = {'Handlers': {'/': {'Proxy': 'http://127.0.0.1:3000'}}}
        access, status, calls = self.refresh([self.state(), existing])
        self.assertEqual(calls.call_count, 2)
        self.assertTrue(status['ready'])
        self.assertEqual(access.origins, {f'https://{NAME}:8788'})

    def test_other_apps_and_public_funnel_ports_are_preserved(self):
        existing = config(target='http://127.0.0.1:3000')
        existing['AllowFunnel'] = {NAME + ':8787': True}
        verified = config(port=8789)
        _, status, calls = self.refresh([self.state(), existing, {}, verified])
        self.assertTrue(status['ready'])
        self.assertEqual(calls.call_args_list[2].args,
                         ('tailscale', 'serve', '--bg', '--yes', '--https=8789', TARGET))

    def test_funnel_and_additional_paths_are_never_trusted_as_private_access(self):
        existing = config()
        existing['AllowFunnel'] = {NAME + ':8788': True}
        _, status, calls = self.refresh([self.state(), existing, {}, config(port=8787)])
        self.assertTrue(status['ready'])
        self.assertIn('--https=8787', calls.call_args_list[2].args)
        existing = config()
        existing['Web'][NAME + ':8788']['Handlers']['/other'] = {'Proxy': 'http://127.0.0.1:3000'}
        _, status, calls = self.refresh([self.state(), existing, {}, config(port=8787)])
        self.assertTrue(status['ready'])
        self.assertIn('--https=8787', calls.call_args_list[2].args)

    def test_missing_disconnected_or_failed_tailscale_keeps_local_app_available(self):
        with patch('h3chat.tailscale_access.executable', return_value=None):
            self.assertFalse(TailscaleAccess(8788).refresh()['ready'])
        _, status, calls = self.refresh([{'BackendState': 'Stopped'}])
        self.assertFalse(status['ready'])
        self.assertEqual(calls.call_count, 1)
        access = TailscaleAccess(8788)
        access.origins = frozenset([f'https://{NAME}:8788'])
        with patch('h3chat.tailscale_access.executable', return_value='tailscale'), \
                patch('h3chat.tailscale_access.run', side_effect=OSError('offline')):
            self.assertFalse(access.refresh()['ready'])
        self.assertFalse(access.origins)

    def test_only_verified_proxy_is_trusted_and_busy_ports_are_not_overwritten(self):
        _, status, _ = self.refresh([self.state(), {}, {}, {}])
        self.assertFalse(status['ready'])
        busy = {'TCP': {str(p): {'HTTPS': True} for p in range(8787, 8798)}}
        _, status, calls = self.refresh([self.state(), busy])
        self.assertFalse(status['ready'])
        self.assertEqual(calls.call_count, 2)

    def test_http_guard_allows_only_verified_https_origin_and_session_token(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.app = SimpleNamespace(token='session', state=lambda: {'token': 'session'})
        server.network = TailscaleAccess(server.server_port)
        remote = f'https://{NAME}:8788'
        server.network.origins = frozenset([remote])
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(path='/api/state', **headers):
            req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}' + path, headers=headers)
            return urllib.request.urlopen(req)
        try:
            with request(Host=NAME + ':8788', Origin=remote) as response:
                self.assertEqual(json.load(response)['token'], 'session')
            for headers in ({'Host': 'attacker.test:8788'},
                            {'Host': NAME + ':8788', 'Origin': 'http://' + NAME + ':8788'},
                            {'Host': NAME + ':8788', 'Origin': 'https://evil.test'},
                            {'Host': NAME + ':8788', 'Sec-Fetch-Site': 'cross-site'}):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request(**headers)
                self.assertEqual(error.exception.code, 403)
            for token, code in (('', 403), ('wrong', 403), ('session', 200)):
                req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/network/refresh',
                    data=b'{}', headers={'Host': NAME + ':8788', 'Origin': remote,
                    'Content-Type': 'application/json', 'X-H3-Token': token})
                with patch.object(server.network, 'refresh', return_value={'ready': True}):
                    if code == 200:
                        with urllib.request.urlopen(req) as response:
                            self.assertTrue(json.load(response)['ready'])
                    else:
                        with self.assertRaises(urllib.error.HTTPError) as error:
                            urllib.request.urlopen(req)
                        self.assertEqual(error.exception.code, code)
            with request() as response:
                self.assertEqual(response.status, 200)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
