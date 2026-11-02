'use strict';
// Browserless behavioral checks for the synthetic UI. This is not browser or accessibility QA.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

class Node {
  constructor(tag = 'div') {
    this.tagName = tag.toLowerCase(); this.children = []; this.events = {}; this.attrs = {};
    this._text = ''; this.value = ''; this.style = {}; this.checked = false; this.disabled = false; this.hidden = false;
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  setAttribute(key, value) { this.attrs[key] = String(value); }
  addEventListener(kind, fn) { this.events[kind] = fn; }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.append(child); return child; }
  replaceChildren(...children) { this._text = ''; this.children = children; }
  focus() {}
  descendants() { return this.children.flatMap(child => [child, ...child.descendants()]); }
  querySelector(selector) {
    const nodes = this.descendants();
    if (selector === 'input[name="assistance"]:checked') return nodes.find(x => x.tagName === 'input' && x.name === 'assistance' && x.checked) || null;
    if (selector === 'button[type="submit"]') return nodes.find(x => x.tagName === 'button' && x.type === 'submit') || null;
    return null;
  }
  querySelectorAll(selector) {
    if (selector === 'input:checked') return this.descendants().filter(x => x.tagName === 'input' && x.checked);
    return [];
  }
}
function deferred() { let resolve; const promise = new Promise(r => { resolve = r; }); return {promise, resolve}; }
function response(data, status = 200) { return {ok: status >= 200 && status < 300, status, json: async () => data}; }
function harness(fetch) {
  const nodes = new Map();
  const document = {
    getElementById(id) { if (!nodes.has(id)) nodes.set(id, new Node()); return nodes.get(id); },
    createElement(tag) { return new Node(tag); },
    createTextNode(text) { const n = new Node('#text'); n.textContent = text; return n; }
  };
  const context = vm.createContext({document, fetch, crypto: {randomUUID: () => 'fictional-test-uuid-12345678'}, console});
  vm.runInContext(fs.readFileSync('prototype/web/app.js', 'utf8'), context);
  return {nodes, document, context};
}
const tick = () => new Promise(resolve => setImmediate(resolve));

async function testAccountSwitchClearsAndIgnoresLateResults() {
  const history = deferred(), logout = deferred();
  const calls = [];
  const h = harness((url, options) => {
    calls.push({url, options});
    if (url === '/api/me') return Promise.resolve(response({}, 403));
    if (url.startsWith('/api/history/')) return history.promise;
    if (url === '/api/logout') return logout.promise;
    throw new Error('Unexpected request: ' + url);
  });
  await tick();
  vm.runInContext("state.identity='fictional-adult-a'; state.csrf='csrf-a'; state.profile='synthetic-a';", h.context);
  for (const id of ['profiles','history','interests','stage-title','stage-word']) h.document.getElementById(id).textContent = 'prior-account-private';
  h.document.getElementById('stat-inprogress').textContent = '17';
  const pendingHistory = vm.runInContext('loadHistory()', h.context);
  const pendingLogout = h.document.getElementById('logout').events.click();
  assert.equal(h.document.getElementById('login-view').hidden, false);
  assert.equal(h.document.getElementById('dashboard').hidden, true);
  for (const id of ['profiles','history','interests','stage-title','stage-word']) assert(!h.document.getElementById(id).textContent.includes('prior-account-private'), id);
  assert.equal(h.document.getElementById('stat-inprogress').textContent, '—');
  history.resolve(response({sessions: [{status:'completed', lesson_id:'old', lesson_version:'1'}]}));
  await pendingHistory;
  assert(!h.document.getElementById('history').textContent.includes('old'));
  assert.equal(h.document.getElementById('stat-completed').textContent, '—');
  logout.resolve(response({ok:true}));
  await pendingLogout;
  assert.equal(calls.find(x => x.url === '/api/logout').options.headers['X-CSRF-Token'], 'csrf-a');
}

async function testExplicitAssistanceIsRequiredAndRecorded() {
  const posts = [];
  const session = {session_id:'fictional-session', lesson_id:'synthetic-lesson-word-study', lesson_version:'v1', stage_index:4, status:'active', revision:1, responses:[]};
  const lesson = {stages: Array.from({length:6}, (_, i) => ({id:i===4?'apply_independently':'other', title:'Fictional stage', instruction:'Practice', display_text:'map', coach_note:'Fictional note', response_prompt:'Fictional response'}))};
  const h = harness((url, options) => {
    if (url === '/api/me') return Promise.resolve(response({}, 403));
    if (url.startsWith('/api/lessons/')) return Promise.resolve(response({lesson}));
    if (url.endsWith('/action')) { posts.push(JSON.parse(options.body)); return Promise.resolve(response({session})); }
    throw new Error('Unexpected request: ' + url);
  });
  await tick();
  h.context.fixtureSession = session;
  vm.runInContext("state.identity='fictional-adult-a'; state.profile='synthetic-a'; state.csrf='csrf-a'; state.session=fixtureSession", h.context);
  await vm.runInContext('openSession()', h.context);
  let form = h.document.getElementById('response-area').children.find(x => x.tagName === 'form');
  const answer = form.descendants().find(x => x.tagName === 'textarea'); answer.value = 'fictional';
  await form.events.submit({preventDefault(){}});
  assert.equal(posts.length, 0, 'missing assistance selection must not submit');
  assert(h.document.getElementById('message').textContent.includes('assistance'));
  form.descendants().find(x => x.name === 'assistance' && x.value === 'yes').checked = true;
  await form.events.submit({preventDefault(){}});
  assert.equal(posts.length, 1);
  assert.equal(posts[0].assisted, true);
  form = h.document.getElementById('response-area').children.find(x => x.tagName === 'form');
  form.descendants().find(x => x.tagName === 'textarea').value = 'fictional';
  form.descendants().find(x => x.name === 'assistance' && x.value === 'no').checked = true;
  await form.events.submit({preventDefault(){}});
  assert.equal(posts.length, 2);
  assert.equal(posts[1].assisted, false);
}
(async () => { await testAccountSwitchClearsAndIgnoresLateResults(); await testExplicitAssistanceIsRequiredAndRecorded(); console.log('Web privacy and assistance checks passed'); })().catch(error => { console.error(error); process.exitCode = 1; });
