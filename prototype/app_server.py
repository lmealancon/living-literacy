"""Local synthetic-family demonstration. NOT safe to expose on a network.

The identity, guardian authority, consent and review fixtures are simulated. This
is not a production service and must never be used for real student data.
"""
import argparse
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import sqlite3
from dataclasses import asdict
from getpass import getpass
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote

from prototype.instructional_content import CONTENT_PATH
from prototype.lesson_engine import PolicyError, ConflictError
from prototype.persistent_store import SyntheticSQLiteStore
from prototype.synthetic_auth import SyntheticParentAuth, resolve
from prototype.family_insights import SyntheticFamilyInsights
from prototype.synthetic_narration_store import SyntheticNarrationStore
from prototype.curriculum_overview import candidate_domains
from prototype.assessment_service import SyntheticAssessmentService
from prototype.assessment_workflow import SyntheticAssessmentWorkflow

WEB = Path(__file__).parent / 'web'
MAX_REQUEST = 4096


def validate_staging_config(origin, proxy_secret):
    """Validate opt-in private HTTPS staging configuration, never real-data auth."""
    if not isinstance(origin, str) or not re.fullmatch(
            r'https://[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::[0-9]{1,5})?', origin):
        raise ValueError('Staging origin must be an exact lowercase HTTPS origin')
    parsed = urlsplit(origin)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError('Invalid staging port') from exc
    host = parsed.hostname
    if (not host or '.' not in host or '..' in host or host.endswith('.local')
            or any(not label or len(label) > 63 or label.startswith('-') or label.endswith('-')
                   for label in host.split('.')) or port == 0):
        raise ValueError('Staging requires a valid public DNS name')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError('Staging origin must use a DNS name, not an IP address')
    # Restrict the syntax so the shared value cannot break common gateway
    # configuration files. This check does not establish secret entropy.
    if not isinstance(proxy_secret, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', proxy_secret):
        raise ValueError('A 32–256 character URL-safe gateway secret is required')
    return parsed.netloc


def bootstrap(filename, identity, password):
    """Create fictional account and simulated review fixtures in a fresh database."""
    if not identity.startswith('synthetic-'):
        raise ValueError('Identity must begin with synthetic-')
    store = SyntheticSQLiteStore(filename)
    token = store.provision_synthetic_family('synthetic-family-1', identity, 'synthetic-student-1')
    SyntheticParentAuth(store).enroll(token, password)
    lesson = json.loads(CONTENT_PATH.read_text(encoding='utf-8'))
    registry = store.content_registry()
    registry.create_draft(lesson, 'synthetic-author')
    registry.transition(lesson['lesson_id'], lesson['version'], 'submit', 'synthetic-author', 'fixture')
    registry.transition(lesson['lesson_id'], lesson['version'], 'approve_prototype', 'synthetic-reviewer', 'fixture')


class App:
    def __init__(self, filename, *, staging_origin=None, proxy_secret=None,
                 synthetic_audio_enabled=False):
        self.staging_origin = staging_origin
        self.proxy_secret = proxy_secret
        self.staging_host = validate_staging_config(staging_origin, proxy_secret) if staging_origin else None
        if not staging_origin and proxy_secret is not None:
            raise ValueError('Gateway secret requires private staging mode')
        self.store = SyntheticSQLiteStore(filename)
        self.auth = SyntheticParentAuth(self.store)
        self.family_insights = SyntheticFamilyInsights(self.store)
        self.assessment_service = SyntheticAssessmentService(self.store)
        self.assessment_workflow = SyntheticAssessmentWorkflow(self.store)
        # Prototype-only opt-in for in-process tests and future reviewed local
        # fixtures. The shipped CLI never enables this, and no audio is seeded.
        if type(synthetic_audio_enabled) is not bool:
            raise ValueError('Invalid synthetic audio flag')
        self.synthetic_narration = SyntheticNarrationStore(self.store) if synthetic_audio_enabled else None
        self.csrf_secret = secrets.token_bytes(32)

    def csrf(self, token):
        return hmac.new(self.csrf_secret, token.encode(), hashlib.sha256).hexdigest()

    def identity(self, token):
        with self.store._connect() as db:
            return resolve(db, token)

    def profiles(self, token):
        with self.store._connect() as db:
            identity = resolve(db, token)
            ids = [row[0] for row in db.execute('SELECT student_id FROM grants WHERE identity_id=?', (identity,))]
            profiles = []
            for student_id in ids:
                try:
                    actor = self.store._actor(db, token, student_id, 'profile')
                    profiles.append({'id': student_id, 'workspace_id': actor.workspace_id, 'synthetic': True})
                except PolicyError:
                    pass
            return profiles

    def history(self, token, student_id):
        with self.store._connect() as db:
            self.store._actor(db, token, student_id, 'lesson')
            return [json.loads(row[0]) for row in db.execute('SELECT payload FROM sessions WHERE student_id=? ORDER BY rowid DESC', (student_id,))]

    def lessons(self):
        # Registry listing verifies status and integrity in one snapshot. The
        # detail and session endpoints independently re-check on every use.
        return self.store.content_registry().list_for_synthetic_demo()


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send_body(self, status, body, content_type='application/json; charset=utf-8', cookie=None, extra_headers=None):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            if cookie:
                self.send_header('Set-Cookie', cookie)
            if extra_headers:
                for name, value in extra_headers.items():
                    self.send_header(name, str(value))
            self.end_headers()
            self.wfile.write(body)

        def token(self):
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie', ''))
                return cookie['ll_session'].value if 'll_session' in cookie else ''
            except Exception:
                return ''

        def valid_host(self):
            if getattr(app, 'staging_origin', None):
                return self.headers.get('Host') == app.staging_host
            return self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)

        def valid_origin(self):
            if getattr(app, 'staging_origin', None):
                return self.headers.get('Origin') == app.staging_origin
            return self.headers.get('Origin') == 'http://127.0.0.1:' + str(self.server.server_port)

        def valid_gateway(self):
            if not getattr(app, 'staging_origin', None):
                return True
            try:
                peer = ipaddress.ip_address(self.client_address[0])
                received = self.headers.get('X-Living-Literacy-Gateway', '')
                return (peer.is_loopback and isinstance(received, str) and received.isascii()
                        and hmac.compare_digest(received, app.proxy_secret))
            except (ValueError, IndexError, TypeError, AttributeError):
                return False

        def do_GET(self):
            if not self.valid_gateway() or not self.valid_host():
                return self.send_body(403, {'error': 'Forbidden'})
            path = urlsplit(self.path).path
            static = {'/': ('index.html', 'text/html; charset=utf-8'), '/index.html': ('index.html', 'text/html; charset=utf-8'), '/styles.css': ('styles.css', 'text/css; charset=utf-8'), '/app.js': ('app.js', 'application/javascript; charset=utf-8')}
            if path in static:
                name, mime = static[path]
                return self.send_body(200, (WEB / name).read_bytes(), mime)
            try:
                token = self.token()
                identity = app.identity(token)
                if path == '/api/me':
                    return self.send_body(200, {'identity': identity, 'csrf': app.csrf(token)})
                if path == '/api/profiles':
                    return self.send_body(200, {'profiles': app.profiles(token)})
                if path == '/api/lessons':
                    return self.send_body(200, {'lessons': app.lessons()})
                if path == '/api/curriculum/domains':
                    return self.send_body(200, candidate_domains())
                parts = path.strip('/').split('/')
                if len(parts) == 5 and parts[:3] == ['api', 'v1', 'students'] and parts[4] == 'assessment-forms':
                    return self.send_body(200, app.assessment_service.list_forms(token, unquote(parts[3])))
                if len(parts) == 5 and parts[:3] == ['api', 'v1', 'students'] and parts[4] == 'assessment-history':
                    return self.send_body(200, app.assessment_workflow.history(token, unquote(parts[3])))
                if len(parts) == 4 and parts[:3] == ['api', 'v1', 'assessment-runs']:
                    return self.send_body(200, app.assessment_workflow.get_run(token, unquote(parts[3])))
                if len(parts) == 4 and parts[:2] == ['api', 'profiles'] and parts[3] == 'interests':
                    return self.send_body(200, app.family_insights.get_interests(token, unquote(parts[2])))
                if len(parts) == 4 and parts[:2] == ['api', 'profiles'] and parts[3] == 'activity':
                    return self.send_body(200, app.family_insights.activity_summary(token, unquote(parts[2])))
                if len(parts) == 4 and parts[:2] == ['api', 'lessons']:
                    lesson = app.store.content_for_demo(unquote(parts[2]), unquote(parts[3]))
                    return self.send_body(200, {'lesson': lesson})
                if len(parts) == 3 and parts[:2] == ['api', 'sessions']:
                    return self.send_body(200, {'session': asdict(app.store.get_session(token, unquote(parts[2])))})
                if len(parts) == 3 and parts[:2] == ['api', 'history']:
                    return self.send_body(200, {'sessions': app.history(token, unquote(parts[2]))})
                return self.send_body(404, {'error': 'Not found'})
            except PolicyError:
                return self.send_body(403, {'error': 'Access denied'})
            except sqlite3.OperationalError:
                return self.send_body(503, {'error': 'Service unavailable'})

        def do_POST(self):
            if not self.valid_gateway() or not self.valid_host() or not self.valid_origin():
                return self.send_body(403, {'error': 'Forbidden'})
            if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                return self.send_body(415, {'error': 'JSON required'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length <= 0 or length > MAX_REQUEST:
                    return self.send_body(413, {'error': 'Invalid request size'})
                data = json.loads(self.rfile.read(length).decode('utf-8'))
                if not isinstance(data, dict):
                    raise ValueError('Invalid body')
                path = urlsplit(self.path).path
                if path == '/api/login':
                    identity, password = data.get('identity'), data.get('passphrase')
                    if not isinstance(identity, str) or len(identity) > 100:
                        raise ValueError('Invalid identity')
                    token = app.auth.login(identity, password)
                    secure = '; Secure' if app.staging_origin else ''
                    return self.send_body(200, {'identity': identity, 'csrf': app.csrf(token)}, cookie='ll_session=' + token + '; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600' + secure)
                token = self.token()
                app.identity(token)
                if not hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), app.csrf(token)):
                    return self.send_body(403, {'error': 'Forbidden'})
                if path == '/api/logout':
                    app.auth.logout(token)
                    secure = '; Secure' if app.staging_origin else ''
                    return self.send_body(200, {'ok': True}, cookie='ll_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0' + secure)
                if path == '/api/profiles':
                    profile = app.store.create_synthetic_profile(token, data['anchor_id'], data['student_id'])
                    return self.send_body(201, {'profile': profile})
                if path == '/api/sessions':
                    key = data.get('idempotency_key')
                    if not isinstance(key, str) or not 16 <= len(key) <= 100 or not key.isascii():
                        raise ValueError('Invalid idempotency key')
                    session = app.store.start(token, data['student_id'], data['lesson_id'], data['version'], key)
                    return self.send_body(201, {'session': asdict(session)})
                if path == '/api/v1/assessment-runs':
                    result = app.assessment_workflow.start(token, data['student_id'], data['form_id'],
                                                           data['version'], data['idempotency_key'])
                    return self.send_body(200, {'run': result})
                parts = path.strip('/').split('/')
                if len(parts) == 5 and parts[:3] == ['api', 'v1', 'assessment-runs']:
                    run_id = unquote(parts[3])
                    if parts[4] == 'responses':
                        result = app.assessment_workflow.record_response(
                            token, run_id, data['item_id'], data['response'], data['assisted'],
                            data['narration'], data['revision'], data['idempotency_key'])
                        return self.send_body(200, {'response': result})
                    if parts[4] == 'complete':
                        result = app.assessment_workflow.complete(token, run_id, data['revision'],
                                                                  data['idempotency_key'])
                        return self.send_body(200, {'run': result})
                if len(parts) == 4 and parts[:2] == ['api', 'profiles'] and parts[3] == 'interests':
                    result = app.family_insights.set_interests(token, unquote(parts[2]), data['interests'])
                    return self.send_body(200, result)
                if len(parts) == 4 and parts[:2] == ['api', 'sessions'] and parts[3] == 'narration':
                    # No fixture installation or simulated-review API is exposed.
                    # This route remains unavailable in all shipped CLI modes.
                    if app.synthetic_narration is None:
                        raise PolicyError('NARRATION_UNAVAILABLE')
                    asset_id, version, revision = data.get('asset_id'), data.get('asset_version'), data.get('revision')
                    if (not isinstance(asset_id, str) or not asset_id.startswith('synthetic-') or len(asset_id) > 100
                            or not isinstance(version, str) or not 1 <= len(version) <= 100
                            or type(revision) is not int or revision < 0):
                        raise ValueError('Invalid narration request')
                    result = app.synthetic_narration.playback(token, unquote(parts[2]), asset_id, version, revision)
                    return self.send_body(200, result['data'], result['content_type'],
                                          extra_headers={'X-Living-Literacy-Revision': result['revision']})
                if len(parts) == 4 and parts[:2] == ['api', 'sessions'] and parts[3] == 'action':
                    sid = unquote(parts[2]); action = data['action']; revision = data['revision']
                    if not isinstance(revision, int) or isinstance(revision, bool):
                        raise ValueError('Invalid revision')
                    if action in ('activate', 'resume', 'pause', 'complete'):
                        target = {'activate': 'active', 'resume': 'active', 'pause': 'paused', 'complete': 'completed'}[action]
                        app.store.transition(token, sid, target, revision)
                    elif action == 'next':
                        app.store.advance_stage(token, sid, revision)
                    elif action == 'respond':
                        response = data.get('response', '')
                        if not isinstance(response, str) or len(response) > 500 or not isinstance(data.get('assisted'), bool):
                            raise ValueError('Invalid response')
                        current = app.store.get_session(token, sid)
                        app.store.record_response(token, sid, revision, response, {'audio_or_modeling': data['assisted']}, independent_task=(current.stage_index == 4))
                    else:
                        raise ValueError('Invalid action')
                    return self.send_body(200, {'session': asdict(app.store.get_session(token, sid))})
                return self.send_body(404, {'error': 'Not found'})
            except ConflictError:
                return self.send_body(409, {'error': 'Conflicting change'})
            except PolicyError:
                return self.send_body(403, {'error': 'Action unavailable'})
            except sqlite3.OperationalError:
                return self.send_body(503, {'error': 'Service unavailable'})
            except (ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError, sqlite3.IntegrityError):
                return self.send_body(400, {'error': 'Invalid request'})

    return Handler


def main():
    parser = argparse.ArgumentParser(description='Local-only, synthetic-data prototype')
    parser.add_argument('--db', default='living-literacy-demo.sqlite3')
    parser.add_argument('--init', action='store_true', help='Initialize an empty synthetic demo database')
    parser.add_argument('--identity', default='synthetic-parent-1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--container-demo', action='store_true',
                        help='Allow container-network access; only use with a loopback-published local demo')
    parser.add_argument('--private-staging-origin', help='Exact HTTPS origin for staging behind a same-host private gateway')
    args = parser.parse_args()
    if args.private_staging_origin and (args.container_demo or args.init):
        parser.error('Private staging cannot be combined with --container-demo or --init')
    proxy_secret = os.environ.get('LIVING_LITERACY_STAGING_PROXY_SECRET') if args.private_staging_origin else None
    if args.private_staging_origin:
        try:
            validate_staging_config(args.private_staging_origin, proxy_secret)
        except ValueError as exc:
            parser.error(str(exc))
    if args.init:
        if Path(args.db).exists():
            raise SystemExit('Database already exists; refusing to overwrite')
        password = getpass('Fictional demo passphrase (12+ characters): ')
        bootstrap(args.db, args.identity, password)
        print('Synthetic database initialized. Run again without --init.')
        return
    if not Path(args.db).is_file():
        raise SystemExit('Initialize a synthetic database first with --init')
    # Docker port forwarding needs a listener on the container network. Keep
    # localhost as the default and make the wider listener an explicit opt-in.
    # The Host/Origin checks still require the browser's 127.0.0.1 origin.
    bind_host = '0.0.0.0' if args.container_demo else '127.0.0.1'
    if args.container_demo:
        print('WARNING: container-network listener; restrict port publishing to localhost. Synthetic data only.', flush=True)
    app = App(args.db, staging_origin=args.private_staging_origin, proxy_secret=proxy_secret) if args.private_staging_origin else App(args.db)
    server = ThreadingHTTPServer((bind_host, args.port), make_handler(app))
    if args.private_staging_origin:
        print('WARNING: private HTTPS staging requires an authenticated same-host gateway; synthetic data only.', flush=True)
    print('Synthetic-only local app at http://127.0.0.1:%s' % server.server_port, flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
