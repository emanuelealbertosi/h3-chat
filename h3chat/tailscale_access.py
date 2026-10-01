"""Private HTTPS access through Tailscale Serve; the app stays on loopback."""
import json
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path


def executable():
    found = shutil.which('tailscale')
    if found:
        return found
    if os.name == 'nt':
        candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Tailscale/tailscale.exe'
        if candidate.is_file():
            return str(candidate)
    return None


def run(cli, *args):
    result = subprocess.run([cli, *args], capture_output=True, text=True, encoding='utf-8',
                            errors='replace', timeout=8, creationflags=0x08000000 if os.name == 'nt' else 0)
    if result.returncode:
        raise RuntimeError('Tailscale non ha completato la configurazione. Controlla accesso e permessi in Tailscale.')
    return result.stdout


def private_proxy(config, authority, target):
    """Require an exclusive HTTPS root proxy, without public Funnel access."""
    port = authority.rsplit(':', 1)[1]
    return (config.get('TCP', {}).get(port) == {'HTTPS': True}
            and config.get('Web', {}).get(authority, {}).get('Handlers') == {'/': {'Proxy': target}}
            and not config.get('AllowFunnel', {}).get(authority))


class TailscaleAccess:
    def __init__(self, port):
        self.port = port
        self.origins = frozenset()
        self.status = {'ready': False, 'url': '', 'message': 'Verifica Tailscale…'}
        self.lock = threading.Lock()

    def refresh(self):
        with self.lock:
            self.origins = frozenset()
            self.status = {'ready': False, 'url': '', 'message': 'Tailscale non installato. L’app è disponibile su questo computer.'}
            cli = executable()
            if not cli:
                return dict(self.status)
            try:
                state = json.loads(run(cli, 'status', '--json'))
                if state.get('BackendState') != 'Running':
                    self.status['message'] = 'Apri Tailscale e connettiti alla tua rete, poi premi Riprova.'
                    return dict(self.status)
                name = state.get('Self', {}).get('DNSName', '').rstrip('.').lower()
                if not re.fullmatch(r'[a-z0-9-]+\.[a-z0-9-]+\.ts\.net', name):
                    raise RuntimeError('Il nome HTTPS Tailscale non è disponibile. Verifica MagicDNS e HTTPS in Tailscale.')
                config = json.loads(run(cli, 'serve', 'status', '--json')) or {}
                target = f'http://127.0.0.1:{self.port}'
                # Preserve every unrelated service, path and Funnel setting.
                chosen = None
                candidates = list(dict.fromkeys([self.port, *range(8787, 8798)]))
                for port in candidates:
                    authority = f'{name}:{port}'
                    if private_proxy(config, authority, target):
                        chosen = port
                        break
                if chosen is None:
                    for port in candidates:
                        authority = f'{name}:{port}'
                        if (str(port) not in config.get('TCP', {})
                                and not any(key.rsplit(':', 1)[-1] == str(port) for key in config.get('Web', {}))
                                and not config.get('AllowFunnel', {}).get(authority)):
                            chosen = port
                            run(cli, 'serve', '--bg', '--yes', f'--https={port}', target)
                            config = json.loads(run(cli, 'serve', 'status', '--json')) or {}
                            break
                if chosen is None or not private_proxy(config, f'{name}:{chosen}', target):
                    raise RuntimeError('Nessuna porta Tailscale libera tra 8787 e 8797. I servizi esistenti sono stati conservati.')
                url = f'https://{name}:{chosen}'
                self.origins = frozenset([url])
                self.status = {'ready': True, 'url': url, 'message': 'Disponibile sui dispositivi autorizzati nella tua rete Tailscale.'}
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
                self.status['message'] = str(exc) if isinstance(exc, RuntimeError) else 'Tailscale non disponibile. Controlla che sia connesso, poi premi Riprova.'
            return dict(self.status)
