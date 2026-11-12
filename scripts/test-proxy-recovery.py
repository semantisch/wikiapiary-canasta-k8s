#!/usr/bin/env python3
"""Exercise the production Caddy proxy against recoverable and ambiguous failures."""
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request

import yaml


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def request(url, data=None):
    try:
        with urllib.request.urlopen(url, data=data, timeout=8) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def main():
    root = Path(__file__).resolve().parents[1]
    source = yaml.safe_load((root / 'values/prod.yaml').read_text())
    block = source['configData']['caddy']['Caddyfile'].split('reverse_proxy varnish:80 {', 1)[1]
    block = block.split('\n    }\n\n    log', 1)[0]
    upstream, frontend = port(), port()
    config = ('{\n admin off\n auto_https off\n}\n'
              f'http://127.0.0.1:{frontend} {{\n reverse_proxy 127.0.0.1:{upstream} {{'
              + block + '\n}\n')
    calls = []

    class Backend(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'healthy')

        def do_POST(self):
            calls.append(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            # The write succeeded, then its acknowledgement was lost.
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()

    with tempfile.TemporaryDirectory(prefix='wikiapiary-proxy-') as directory:
        path = Path(directory) / 'Caddyfile'
        path.write_text(config)
        with (Path(directory) / 'log').open('w+') as log:
            proxy = subprocess.Popen([os.environ.get('CADDY_BIN', 'caddy'), 'run', '--config', str(path)],
                                     stdout=log, stderr=log)
            server = None
            try:
                for _ in range(100):
                    if proxy.poll() is not None:
                        log.seek(0)
                        raise AssertionError(log.read())
                    try:
                        with socket.create_connection(('127.0.0.1', frontend), timeout=.1):
                            break
                    except OSError:
                        time.sleep(.05)
                url = f'http://127.0.0.1:{frontend}/'
                assert request(url)[0] == 502, 'A failed connection must remain an error'
                server = http.server.ThreadingHTTPServer(('127.0.0.1', upstream), Backend)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                started = time.monotonic()
                assert request(url) == (200, b'healthy'), 'Recovered Service must not remain quarantined'
                elapsed = time.monotonic() - started
                assert elapsed < 2, elapsed
                assert request(url, b'one-write')[0] == 502
                assert calls == [b'one-write'], 'Never replay a write with a lost acknowledgement'
                assert request(url) == (200, b'healthy'), 'Failed write must not block later reads'
                print(json.dumps({'recovery_seconds': elapsed, 'write_attempts': len(calls),
                                  'checks': 5, 'passed': True}))
            finally:
                proxy.terminate()
                proxy.wait(timeout=10)
                if server:
                    server.shutdown()
                    server.server_close()


if __name__ == '__main__':
    main()
