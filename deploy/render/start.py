"""Restricted, fictional-data-only Render staging. Not a production server.

Render terminates HTTPS. nginx gates requests and proxies to the existing local
Python app. Runtime credentials must be independent randomly generated values.
No real personal information is permitted.
"""
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from prototype.app_server import bootstrap, validate_staging_config

SAFE = re.compile(r'[A-Za-z0-9_-]{32,128}\Z')
RENDER_ORIGIN = re.compile(r'https://[a-z0-9](?:[a-z0-9-]{0,60}[a-z0-9])?\.onrender\.com\Z')


def settings(env):
    origin = env.get('LL_STAGING_ORIGIN', '')
    if not RENDER_ORIGIN.fullmatch(origin):
        raise ValueError('LL_STAGING_ORIGIN must be the exact HTTPS onrender.com origin')
    proxy_secret = env.get('LIVING_LITERACY_STAGING_PROXY_SECRET', '')
    gateway_password = env.get('LL_GATEWAY_PASSWORD', '')
    demo_password = env.get('LL_DEMO_PASSWORD', '')
    for value in (proxy_secret, gateway_password, demo_password):
        if not SAFE.fullmatch(value):
            raise ValueError('Each staging secret must be 32–128 URL-safe characters')
    if len({proxy_secret, gateway_password, demo_password}) != 3:
        raise ValueError('Use three different staging secrets')
    validate_staging_config(origin, proxy_secret)
    try:
        port = int(env.get('PORT', '10000'))
    except ValueError as exc:
        raise ValueError('PORT must be an integer') from exc
    if port < 1024 or port > 65535 or port == 8765:
        raise ValueError('PORT must be an unprivileged port other than 8765')
    return {'origin': origin, 'host': urlsplit(origin).netloc, 'port': port,
            'proxy_secret': proxy_secret, 'gateway_password': gateway_password,
            'demo_password': demo_password}


def nginx_config(cfg, directory):
    # Values in these positions have already passed strict allowlist validation.
    return f'''worker_processes 1;
pid {directory}/nginx.pid;
error_log stderr warn;
events {{ worker_connections 128; }}
http {{
  access_log off;
  server_tokens off;
  client_max_body_size 4k;
  client_body_temp_path {directory}/body;
  proxy_temp_path {directory}/proxy;
  fastcgi_temp_path {directory}/fastcgi;
  uwsgi_temp_path {directory}/uwsgi;
  scgi_temp_path {directory}/scgi;
  limit_req_zone $server_name zone=staging_all:1m rate=1r/s;
  limit_req_zone $server_name zone=staging_login:1m rate=5r/m;
  server {{
    listen 0.0.0.0:{cfg['port']};
    server_name {cfg['host']};
    auth_basic "Fictional data only - restricted staging";
    auth_basic_user_file {directory}/users;
    location = /api/login {{
      limit_req zone=staging_all burst=15 nodelay;
      limit_req zone=staging_login burst=3 nodelay;
      include {directory}/proxy.conf;
    }}
    location / {{
      limit_req zone=staging_all burst=15 nodelay;
      include {directory}/proxy.conf;
    }}
  }}
}}
'''


def proxy_config(cfg):
    return f'''proxy_pass http://127.0.0.1:8765;
proxy_set_header Host $http_host;
proxy_set_header X-Living-Literacy-Gateway {cfg['proxy_secret']};
proxy_set_header Authorization "";
proxy_set_header X-Forwarded-For "";
proxy_set_header X-Forwarded-Host "";
proxy_set_header X-Forwarded-Proto "";
'''


def main():
    try:
        cfg = settings(os.environ)
    except ValueError as exc:
        print(f'Staging configuration error: {exc}', file=sys.stderr)
        return 1

    signal.signal(signal.SIGTERM, lambda _signum, _frame: sys.exit(0))
    # A private runtime directory holds nginx config and a salted password hash.
    # This is not durable data or a substitute for a managed secret store.
    with tempfile.TemporaryDirectory(prefix='ll-render-') as directory:
        run = Path(directory)
        try:
            password_hash = subprocess.run(['openssl', 'passwd', '-6', '-stdin'],
                input=cfg['gateway_password'] + '\n', text=True, check=True,
                capture_output=True).stdout.strip()
            if not password_hash.startswith('$6$'):
                raise ValueError('Could not create a supported gateway password hash')
            (run / 'users').write_text('demo:' + password_hash + '\n', encoding='utf-8')
            (run / 'users').chmod(0o600)
            (run / 'nginx.conf').write_text(nginx_config(cfg, directory), encoding='utf-8')
            (run / 'nginx.conf').chmod(0o600)
            (run / 'proxy.conf').write_text(proxy_config(cfg), encoding='utf-8')
            (run / 'proxy.conf').chmod(0o600)
            db = run / 'synthetic.sqlite3'
            bootstrap(db, 'synthetic-parent-1', cfg['demo_password'])
            # Do not pass gateway or demo credentials to child process environments.
            app_env = {k: v for k, v in os.environ.items() if k not in ('LL_GATEWAY_PASSWORD', 'LL_DEMO_PASSWORD')}
            app = subprocess.Popen([sys.executable, '-m', 'prototype.app_server', '--db', str(db),
                                    '--private-staging-origin', cfg['origin']], env=app_env)
            try:
                nginx_env = {k: v for k, v in os.environ.items() if k not in ('LL_GATEWAY_PASSWORD', 'LL_DEMO_PASSWORD', 'LIVING_LITERACY_STAGING_PROXY_SECRET')}
                gateway = subprocess.Popen(['nginx', '-c', str(run / 'nginx.conf'), '-g', 'daemon off;'], env=nginx_env)
                try:
                    # Stop the remaining process as soon as either child exits.
                    while app.poll() is None and gateway.poll() is None:
                        time.sleep(0.5)
                finally:
                    if gateway.poll() is None:
                        gateway.terminate()
                    gateway.wait(timeout=10)
            finally:
                if app.poll() is None:
                    app.terminate()
                app.wait(timeout=10)
            return 1
        except (OSError, subprocess.CalledProcessError, ValueError):
            # No credentials or exception content are echoed.
            print('Unable to initialize restricted staging.', file=sys.stderr)
            return 1


if __name__ == '__main__':
    raise SystemExit(main())
