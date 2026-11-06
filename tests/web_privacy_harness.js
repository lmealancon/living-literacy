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
function harness(fetch, {reduceMotion = false, initialPreferences = {}, legacyMedia = false} = {}) {
  const nodes = new Map();
  const stored = new Map(Object.entries(initialPreferences));
  const document = {
    getElementById(id) { if (!nodes.has(id)) nodes.set(id, new Node()); return nodes.get(id); },
    createElement(tag) { return new Node(tag); },
    createTextNode(text) { const n = new Node('#text'); n.textContent = text; return n; },
    documentElement: new Node('html'), body: new Node('body')
  };
  const localStorage = { getItem(key) { return stored.get(key) || null; }, setItem(key, value) { stored.set(key, value); } };
  const listeners = [];
  const mediaQuery = {
    matches: reduceMotion,
    addEventListener(type, listener) { if (type === 'change') listeners.push(listener); },
    addListener(listener) { listeners.push(listener); },
    change(matches) { this.matches = matches; for (const listener of listeners) listener({matches}); }
  };
  if (legacyMedia) delete mediaQuery.addEventListener;
  const window = { matchMedia: () => mediaQuery };
  const context = vm.createContext({document, fetch, window, localStorage, crypto: {randomUUID: () => 'fictional-test-uuid-12345678'}, console});
  vm.runInContext(fs.readFileSync('prototype/web/app.js', 'utf8'), context);
  return {nodes, document, context, stored, mediaQuery, window};
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
async function testWordTilesAndSafeResponse() {
  const posts = [];
  const session = {session_id:'fictional-session', lesson_id:'synthetic-lesson-word-study', lesson_version:'v1', stage_index:3, status:'active', revision:2, responses:[]};
  const lesson = {stages: Array.from({length:6}, (_, i) => ({id:i===3?'practice':'other', title:'Fictional stage', instruction:'Practice', display_text:'map', coach_note:'Fictional note', response_prompt:'Fictional response'}))};
  const h = harness((url, options) => {
    if (url === '/api/me') return Promise.resolve(response({}, 403));
    if (url.startsWith('/api/lessons/')) return Promise.resolve(response({lesson}));
    if (url.endsWith('/action')) { posts.push({body:JSON.parse(options.body), csrf:options.headers['X-CSRF-Token']}); return Promise.resolve(response({session})); }
    throw new Error('Unexpected request: ' + url);
  });
  await tick();
  h.context.fixtureSession = session;
  vm.runInContext("state.identity='fictional-adult-a'; state.profile='synthetic-a'; state.csrf='csrf-a'; state.session=fixtureSession", h.context);
  await vm.runInContext('openSession()', h.context);
  assert.equal(h.document.getElementById('lesson-guide').attrs['data-mood'], 'idle');
  const area = h.document.getElementById('response-area');
  const builder = area.descendants().find(x => x.className === 'word-builder');
  assert(builder, 'existing fictional lesson has word-building controls');
  const all = builder.descendants();
  const tile = letter => all.find(x => x.tagName === 'button' && x.textContent === letter);
  const output = all.find(x => x.tagName === 'output');
  tile('m').events.click();
  assert.equal(h.document.getElementById('lesson-guide').attrs['data-mood'], 'react');
  assert.equal(output.textContent, 'm');
  assert.equal(tile('m').disabled, true, 'a selected tile is unavailable until undone');
  tile('m').events.click();
  assert.equal(output.textContent, 'm', 'an already-used tile cannot be added twice');
  output.events.drop({preventDefault(){}, dataTransfer:{getData:()=>'2'}});
  tile('p').events.click();
  assert.equal(output.textContent, 'map');
  all.find(x => x.tagName === 'button' && x.textContent === 'Undo last letter').events.click();
  assert.equal(output.textContent, 'ma');
  assert.equal(tile('p').disabled, false);
  tile('p').events.click();
  all.find(x => x.tagName === 'button' && x.textContent === 'Clear letters').events.click();
  assert.equal(output.textContent, '');
  for (const letter of ['m', 'a', 'p']) {
    assert.equal(tile(letter).disabled, false);
    tile(letter).events.click();
  }
  const form = area.descendants().find(x => x.tagName === 'form');
  assert.equal(form.descendants().find(x => x.tagName === 'textarea').value, 'map');
  form.descendants().find(x => x.name === 'assistance' && x.value === 'no').checked = true;
  await form.events.submit({preventDefault(){}});
  assert.equal(h.document.getElementById('lesson-guide').attrs['data-mood'], 'celebrate');
  assert.equal(posts.length, 1);
  assert.equal(posts[0].body.response, 'map');
  assert.equal(posts[0].body.assisted, false);
  assert.equal(posts[0].csrf, 'csrf-a');
}
async function testAccessibleVisualPreferences() {
  const denied = () => Promise.resolve(response({}, 403));
  const h = harness(denied);
  await tick();
  const motion = h.document.getElementById('motion-toggle');
  const visuals = h.document.getElementById('visuals-toggle');
  assert.equal(h.document.documentElement.attrs['data-motion'], 'on');
  motion.events.click();
  assert.equal(h.document.documentElement.attrs['data-motion'], 'off');
  assert.equal(motion.attrs['aria-pressed'], 'true');
  assert.equal(h.stored.get('living-literacy-reduce-motion'), 'true');
  visuals.events.click();
  assert.equal(h.document.documentElement.attrs['data-visuals'], 'simple');
  assert.equal(visuals.attrs['aria-pressed'], 'true');
  const reduced = harness(denied, {reduceMotion:true});
  await tick();
  const reducedButton = reduced.document.getElementById('motion-toggle');
  assert.equal(reduced.document.documentElement.attrs['data-motion'], 'off');
  assert.equal(reducedButton.disabled, true);
  reducedButton.events.click();
  assert.equal(reduced.document.documentElement.attrs['data-motion'], 'off', 'device preference must not be overridden');
}
async function testDynamicMotionPreference() {
  const denied = () => Promise.resolve(response({}, 403));
  const standard = harness(denied, {initialPreferences:{'living-literacy-reduce-motion':'false'}});
  await tick();
  const toggle = standard.document.getElementById('motion-toggle');
  assert.equal(standard.document.documentElement.attrs['data-motion'], 'on');
  standard.mediaQuery.change(true);
  assert.equal(standard.document.documentElement.attrs['data-motion'], 'off');
  assert.equal(toggle.disabled, true);
  assert.equal(toggle.attrs['aria-pressed'], 'true');
  assert.equal(standard.stored.get('living-literacy-reduce-motion'), 'false', 'device setting must not overwrite saved choice');
  standard.mediaQuery.change(false);
  assert.equal(standard.document.documentElement.attrs['data-motion'], 'on');
  assert.equal(toggle.disabled, false);
  assert.equal(toggle.attrs['aria-pressed'], 'false');

  const saved = harness(denied, {initialPreferences:{'living-literacy-reduce-motion':'true'}});
  await tick();
  const savedToggle = saved.document.getElementById('motion-toggle');
  assert.equal(saved.document.documentElement.attrs['data-motion'], 'off');
  saved.mediaQuery.change(true);
  assert.equal(savedToggle.disabled, true);
  saved.mediaQuery.change(false);
  assert.equal(saved.document.documentElement.attrs['data-motion'], 'off', 'saved reduced motion must survive device toggles');
  assert.equal(savedToggle.disabled, false);
  assert.equal(saved.stored.get('living-literacy-reduce-motion'), 'true');

  const startsReduced = harness(denied, {reduceMotion:true, initialPreferences:{'living-literacy-reduce-motion':'false'}});
  await tick();
  assert.equal(startsReduced.document.documentElement.attrs['data-motion'], 'off');
  startsReduced.mediaQuery.change(false);
  assert.equal(startsReduced.document.documentElement.attrs['data-motion'], 'on', 'saved choice should be restored when device setting clears');

  const legacy = harness(denied, {legacyMedia:true});
  await tick();
  legacy.mediaQuery.change(true);
  assert.equal(legacy.document.documentElement.attrs['data-motion'], 'off', 'legacy media listener must honor device changes');
  legacy.mediaQuery.change(false);
  assert.equal(legacy.document.documentElement.attrs['data-motion'], 'on');
}
async function testFixedVoiceDemo() {
  const requests = [];
  const h = harness((url, options) => {
    requests.push(url);
    if (url === '/api/me') return Promise.resolve(response({}, 403));
    if (url === '/api/logout') return Promise.resolve(response({ok:true}));
    throw new Error('Unexpected request: ' + url);
  });
  await tick();
  const played = [];
  let cancellations = 0;
  h.window.speechSynthesis = {speak: utterance => played.push(utterance), cancel: () => cancellations++};
  h.window.SpeechSynthesisUtterance = function(text) { this.text = text; };
  vm.runInContext("state.identity='synthetic-adult'; state.profile='synthetic-private-value'; state.csrf='csrf'; show('dashboard')", h.context);
  assert.equal(played.length, 0, 'speech must be initiated by a deliberate click');
  h.document.getElementById('voice-demo-hello').events.click();
  assert.equal(played[0].text, 'Hello! It is nice to meet you.');
  assert.equal(h.document.getElementById('voice-demo-text').textContent, played[0].text);
  h.document.getElementById('voice-demo-cheer').events.click();
  assert.equal(played[1].text, 'Hooray! Let us explore together.');
  assert(!played.some(utterance => utterance.text.includes('synthetic-private-value')));
  const generation = cancellations;
  h.document.getElementById('voice-demo-stop').events.click();
  assert(cancellations > generation, 'stop cancels platform speech');
  const oldError = played[1].onerror;
  oldError();
  assert.equal(h.document.getElementById('voice-demo-status').textContent, 'Audio stopped.', 'late error must not overwrite a later stop');
  h.document.getElementById('voice-demo-hello').events.click();
  const beforeLesson = cancellations;
  vm.runInContext("show('lesson-view')", h.context);
  assert(cancellations > beforeLesson, 'leaving the dashboard cancels the isolated demo');
  h.document.getElementById('voice-demo-cheer').events.click();
  const beforeLogout = cancellations;
  await h.document.getElementById('logout').events.click();
  assert(cancellations > beforeLogout, 'logout cancels platform speech');
  assert.deepEqual(requests, ['/api/me', '/api/logout'], 'voice demo makes no application network calls');

  const noVoice = harness(() => Promise.resolve(response({}, 403)));
  await tick();
  noVoice.document.getElementById('voice-demo-hello').events.click();
  assert.equal(noVoice.document.getElementById('voice-demo-text').textContent, 'Hello! It is nice to meet you.');
  assert(noVoice.document.getElementById('voice-demo-status').textContent.includes('unavailable'));
}
(async () => { await testAccountSwitchClearsAndIgnoresLateResults(); await testExplicitAssistanceIsRequiredAndRecorded(); await testWordTilesAndSafeResponse(); await testAccessibleVisualPreferences(); await testDynamicMotionPreference(); await testFixedVoiceDemo(); console.log('Web privacy and assistance checks passed'); })().catch(error => { console.error(error); process.exitCode = 1; });
