#!/usr/bin/env python3
"""Isolated NGINX regression, run with a rendered failover fragment as argv[1]."""
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request


def main():
    writes = []

    class Backend(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(self.server.answer)
            self.end_headers()
            self.wfile.write(b'backend')

        def do_POST(self):
            writes.append(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()

    servers = [http.server.ThreadingHTTPServer(('127.0.0.1', 0), Backend) for _ in range(2)]
    for server, answer in zip(servers, [503, 200]):
        server.answer = answer
        threading.Thread(target=server.serve_forever, daemon=True).start()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        frontend = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='wikiapiary-nginx-') as directory:
        path = Path(directory)
        upstreams = '\n'.join(f'server 127.0.0.1:{s.server_port} max_fails=0;' for s in servers)
        config = f'''daemon off;
master_process off;
pid {path}/pid;
error_log {path}/error.log;
events {{ worker_connections 32; }}
http {{
  access_log off;
  client_body_temp_path {path}/body;
  proxy_temp_path {path}/proxy;
  fastcgi_temp_path {path}/fastcgi;
  scgi_temp_path {path}/scgi;
  uwsgi_temp_path {path}/uwsgi;
  upstream test_backend {{ {upstreams} }}
  server {{
    listen 127.0.0.1:{frontend};
    {sys.argv[1]}
    location / {{ proxy_pass http://test_backend; proxy_connect_timeout 2s; }}
  }}
}}
'''
        (path / 'nginx.conf').write_text(config)
        with (path / 'output.log').open('w+') as log:
            proxy = subprocess.Popen([os.environ.get('NGINX_BIN', 'nginx'), '-p', directory,
                                      '-c', str(path / 'nginx.conf')], stdout=log, stderr=log)
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
                for _ in range(4):
                    with urllib.request.urlopen(url, timeout=6) as response:
                        assert response.status == 200
                try:
                    urllib.request.urlopen(url, data=b'one-write', timeout=6)
                except urllib.error.HTTPError as error:
                    assert error.code == 502
                else:
                    raise AssertionError('Lost acknowledgement must remain an error')
                assert writes == [b'one-write'], writes
                print(json.dumps({'read_failover_checks': 4, 'write_attempts': len(writes), 'passed': True}))
            finally:
                proxy.terminate()
                proxy.wait(timeout=5)
                for server in servers:
                    server.shutdown()
                    server.server_close()


if __name__ == '__main__':
    main()
