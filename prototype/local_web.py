"""Local-only synthetic family UI. Never expose on public network or enter real student data."""
import html
import json
import secrets
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from prototype.lesson_engine import STAGES, PolicyError, ConflictError
from prototype.persistent_store import SyntheticSQLiteStore
from prototype.instructional_content import CONTENT_PATH, stage_content
import json

LESSON = ('synthetic-lesson-word-study', 'demo-1')

def make_demo():
    tmp = tempfile.TemporaryDirectory(prefix='living-literacy-demo-')
    store = SyntheticSQLiteStore(tmp.name + '/demo.sqlite')
    token = store.provision_synthetic_family('synthetic-family-1', 'synthetic-adult-1', 'synthetic-student-1')
    registry=store.content_registry()
    registry.create_draft(json.loads(CONTENT_PATH.read_text(encoding="utf-8")),"synthetic-author")
    registry.transition(*LESSON,"submit","synthetic-author","submitted for demo review")
    registry.transition(*LESSON,"approve_prototype","synthetic-reviewer","reviewed for synthetic demo only")
    return tmp, store, token

def render(session=None, error='', lesson=None):
    esc=html.escape
    stage = STAGES[session.stage_index] if session else None
    progress = (session.stage_index+1)*100//len(STAGES) if session else 0
    alert = '<p role="alert" class="error">'+esc(error)+'</p>' if error else ''
    if lesson is None:
        raise PolicyError("CONTENT_NOT_APPROVED")
    if session is None:
        controls = '<form method="post" action="/action"><input type="hidden" name="action" value="start"><button>Start demo lesson</button></form>'
        detail = '<p>Begin a sample lesson using fictional student data. This demonstration does not assess a child.</p><p><strong>Sample:</strong> '+esc(lesson['title'])+'</p>'
    else:
        hidden = '<input type="hidden" name="revision" value="'+str(session.revision)+'">'
        instructional = stage_content(lesson, session.stage_index)
        actions=[]
        if session.status=='created': actions=[('activate','Begin lesson')]
        elif session.status=='active':
            if session.stage_index < len(STAGES)-1: actions.append(('next','Next stage'))
            else: actions.append(('complete','Complete activity'))
            actions.append(('pause','Pause'))
        elif session.status=='paused': actions=[('resume','Resume')]
        elif session.status in ('completed','abandoned'): actions=[('restart','Start another demo lesson')]
        controls=''.join('<form method="post" action="/action">'+hidden+'<button name="action" value="'+a+'">'+label+'</button></form>' for a,label in actions)
        if session.status=='active':
            controls += '<form method="post" action="/action">'+hidden+'<label for="response">'+esc(instructional['response_prompt'])+' — Practice response (fictional text only)</label><textarea id="response" name="response" maxlength="500" required></textarea><label><input type="checkbox" name="assisted" value="yes"> Audio or modeling assistance used</label><button name="action" value="respond">Save practice response</button></form>'
        detail='<article aria-label="Instructional content"><h3>'+esc(instructional['title'])+'</h3><p>'+esc(instructional['instruction'])+'</p><p class="word-card">'+esc(instructional['display_text'])+'</p><details><summary>Adult demonstration note</summary><p>'+esc(instructional['coach_note'])+'</p></details></article><p><strong>Status:</strong> '+esc(session.status)+' · <strong>Stage:</strong> '+esc(stage.replace('_',' ').title())+'</p><div class="track"><div style="width:'+str(progress)+'%"></div></div><p>Stage '+str(session.stage_index+1)+' of 6 · '+str(len(session.responses))+' practice response(s)</p><p><strong>Mastery:</strong> not assessed. Completion does not establish mastery.</p>'
    return ("""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Living Literacy | Local Prototype</title><style>
:root{font-family:system-ui,sans-serif;color:#f9f5e8;background:#121212}body{margin:0}header{padding:24px 5vw;border-bottom:1px solid #63512d}main{max-width:760px;margin:45px auto;padding:0 20px}h1{color:#e8bd55}section{border:1px solid #66512e;border-radius:16px;padding:24px;background:#202020}button{background:#e8bd55;color:#171717;border:0;border-radius:9px;padding:12px 18px;font-weight:700;cursor:pointer;margin:8px 0}button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid white}form{margin-top:18px}label{display:block;margin:10px 0}textarea{display:block;box-sizing:border-box;width:100%;min-height:90px;padding:12px;background:#fafafa;color:#111}p{line-height:1.6}.track{height:12px;border-radius:10px;background:#484848;overflow:hidden}.track div{background:#e8bd55;height:100%}.error{color:#ffb0a0}.notice{color:#e8bd55;font-weight:700}.word-card{font-size:1.7rem;letter-spacing:.04em;background:#2e2a21;padding:18px;border-radius:10px}details{margin:16px 0}summary{cursor:pointer}footer{margin-top:25px;color:#b9b9b9;font-size:.9rem}
</style></head><body><header><strong>Living Literacy</strong> · Local engineering demo</header><main><h1>Learn to read. Grow with confidence.</h1><p class="notice">SYNTHETIC DATA ONLY · NOT FOR CHILDREN OR PUBLIC DEPLOYMENT</p><section><h2>Sample family lesson</h2>""" + alert + detail + controls + """</section><footer>This prototype is not a validated assessment, tutor, or secure family account service. Do not enter real personal information.</footer></main></body></html>""").encode('utf-8')

def make_handler(store, token):
    current={'session_id':None}
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, content_type='text/html; charset=utf-8', extra=None):
            self.send_response(code); self.send_header('Content-Type',content_type); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            if extra:
                for k,v in extra.items(): self.send_header(k,v)
            self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            if urlsplit(self.path).path!='/': return self._send(404,b'Not found','text/plain')
            sid=current['session_id']; session=store.get_session(token,sid) if sid else None
            try:
                lesson=store.content_for_demo(*LESSON)
                self._send(200,render(session,lesson=lesson))
            except PolicyError:
                self._send(503,b"Demo content unavailable or withdrawn", "text/plain")
        def do_POST(self):
            if self.path!='/action': return self._send(404,b'Not found','text/plain')
            length=int(self.headers.get('Content-Length','0'))
            if length<=0 or length>4096: return self._send(413,b'Invalid request','text/plain')
            if self.headers.get('Content-Type','').split(';')[0].strip()!='application/x-www-form-urlencoded': return self._send(415,b'Invalid type','text/plain')
            # Local-only UI, not a production CSRF/auth model.
            origin=self.headers.get('Origin')
            if origin and origin!=f'http://127.0.0.1:{self.server.server_port}': return self._send(403,b'Forbidden','text/plain')
            fields=parse_qs(self.rfile.read(length).decode('utf-8'),keep_blank_values=True)
            val=lambda k:fields.get(k,[''])[0]
            try:
                if val('action')=='restart':
                    sid=current['session_id']
                    if not sid: raise PolicyError('NO_ACTIVE_SESSION')
                    previous=store.get_session(token,sid)
                    if previous.status not in ('completed','abandoned'): raise PolicyError('SESSION_NOT_FINISHED')
                    if int(val('revision')) != previous.revision: raise ConflictError('REVISION_CONFLICT')
                    session=store.start(token,'synthetic-student-1',*LESSON,secrets.token_urlsafe(16))
                    current['session_id']=session.session_id
                elif val('action')=='start':
                    if current['session_id'] is None:
                        session=store.start(token,'synthetic-student-1',*LESSON,secrets.token_urlsafe(16)); current['session_id']=session.session_id
                else:
                    sid=current['session_id']
                    if not sid: raise PolicyError('NO_ACTIVE_SESSION')
                    revision=int(val('revision'))
                    action=val('action')
                    if action=='activate': store.transition(token,sid,'active',revision)
                    elif action=='next': store.advance_stage(token,sid,revision)
                    elif action=='pause': store.transition(token,sid,'paused',revision)
                    elif action=='resume': store.transition(token,sid,'active',revision)
                    elif action=='complete': store.transition(token,sid,'completed',revision)
                    elif action=='respond': store.record_response(token,sid,revision,val('response'),{'audio_or_modeling':val('assisted')=='yes'},independent_task=(store.get_session(token,sid).stage_index == 4))
                    else: raise PolicyError('INVALID_ACTION')
                self.send_response(303); self.send_header('Location','/'); self.send_header('Cache-Control','no-store'); self.end_headers()
            except (PolicyError,ConflictError,ValueError) as exc:
                sid=current['session_id']; session=store.get_session(token,sid) if sid else None
                try:
                    lesson=store.content_for_demo(*LESSON)
                    self._send(400,render(session,str(exc),lesson))
                except PolicyError:
                    self._send(503,b"Demo content unavailable or withdrawn", "text/plain")
    return Handler

def serve():
    temp,store,token=make_demo()
    try:
        server=ThreadingHTTPServer(('127.0.0.1',8765),make_handler(store,token))
        print('Synthetic-only demo at http://127.0.0.1:8765 (Ctrl+C to stop)',flush=True)
        server.serve_forever()
    finally: temp.cleanup()

if __name__=='__main__': serve()
