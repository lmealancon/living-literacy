'use strict';
// Synthetic-data prototype. All access and content checks are enforced by the server.
const $ = id => document.getElementById(id);
const state = { csrf: null, identity: null, profiles: [], lessons: [], profile: null, session: null };

function message(text, error = false) {
  const box = $('message');
  box.textContent = text;
  box.hidden = !text;
  box.setAttribute('role', error ? 'alert' : 'status');
}
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function button(text, callback, primary = false) {
  const node = el('button', text, primary ? 'primary' : '');
  node.type = 'button';
  node.addEventListener('click', callback);
  return node;
}
function show(view) {
  for (const id of ['login-view', 'dashboard', 'lesson-view']) $(id).hidden = id !== view;
  $('logout').hidden = !state.identity;
}
function friendlyError(error) {
  if (error.status === 401 || error.status === 403) return 'Your session may have expired, or this action is unavailable. Please sign in again or contact the prototype administrator.';
  if (error.status === 409) return 'This activity changed in another tab. Reopen it to see the latest state.';
  return error.message || 'Something went wrong. Please try again.';
}
async function request(path, data) {
  const options = { credentials: 'same-origin', headers: { 'Accept': 'application/json' } };
  if (data !== undefined) {
    options.method = 'POST';
    options.headers['Content-Type'] = 'application/json';
    if (state.csrf) options.headers['X-CSRF-Token'] = state.csrf;
    options.body = JSON.stringify(data);
  }
  const response = await fetch(path, options);
  let result = {};
  try { result = await response.json(); } catch (_) { /* Return a safe generic message. */ }
  if (!response.ok) {
    const error = new Error(typeof result.message === 'string' ? result.message : 'Unable to complete the request.');
    error.status = response.status;
    throw error;
  }
  return result;
}
async function loadDashboard() {
  show('dashboard');
  const [profileData, lessonData] = await Promise.all([request('/api/profiles'), request('/api/lessons')]);
  state.profiles = profileData.profiles || [];
  state.lessons = lessonData.lessons || [];
  if (!state.profiles.some(p => p.id === state.profile)) state.profile = state.profiles[0]?.id || null;
  renderProfiles();
  renderLessons();
  await loadHistory();
}
function renderProfiles() {
  const area = $('profiles');
  area.replaceChildren();
  if (!state.profiles.length) area.append(el('p', 'No fictional profiles are available. Ask the prototype administrator to provision one.'));
  state.profiles.forEach(profile => {
    const row = el('div', undefined, 'item');
    const description = el('div');
    description.append(el('strong', profile.id), el('p', profile.id === state.profile ? 'Selected' : 'Fictional learner', 'fine'));
    row.append(description, button(profile.id === state.profile ? 'Selected' : 'Select', async () => {
      state.profile = profile.id;
      renderProfiles(); renderLessons();
      try { await loadHistory(); } catch (error) { message(friendlyError(error), true); }
    }));
    area.append(row);
  });
}
function renderLessons() {
  const area = $('lesson-list');
  area.replaceChildren();
  if (!state.profile) { area.append(el('p', 'Choose a fictional profile first.')); return; }
  if (!state.lessons.length) { area.append(el('p', 'No approved prototype activities are available.')); return; }
  state.lessons.forEach(lesson => {
    let pendingKey = null;
    const row = el('div', undefined, 'item');
    const details = el('div');
    details.append(el('strong', lesson.title), el('p', 'Six stages · Prototype only', 'fine'));
    row.append(details, button('Start', async () => {
      try {
        message('');
        if (!pendingKey) pendingKey = crypto.randomUUID();
        const result = await request('/api/sessions', { student_id: state.profile, lesson_id: lesson.lesson_id, version: lesson.version, idempotency_key: pendingKey });
        pendingKey = null;
        state.session = result.session;
        await openSession();
      } catch (error) { message(friendlyError(error), true); }
    }, true));
    area.append(row);
  });
}
async function loadHistory() {
  const area = $('history');
  area.replaceChildren();
  if (!state.profile) { area.append(el('p', 'Choose a fictional profile to view activity.')); return; }
  const data = await request('/api/history/' + encodeURIComponent(state.profile));
  const sessions = data.sessions || [];
  if (!sessions.length) { area.append(el('p', 'No practice activity yet.')); return; }
  sessions.forEach(session => {
    const row = el('div', undefined, 'item');
    const text = el('div');
    const lesson = state.lessons.find(item => item.lesson_id === session.lesson_id && item.version === session.lesson_version);
    text.append(el('strong', lesson?.title || 'Sample activity'), el('p', 'Status: ' + session.status.replaceAll('_', ' '), 'fine'));
    row.append(text, button('Open', async () => {
      try {
        const data = await request('/api/sessions/' + encodeURIComponent(session.session_id));
        state.session = data.session;
        await openSession();
      } catch (error) { message(friendlyError(error), true); }
    }));
    area.append(row);
  });
}
async function openSession() {
  const session = state.session;
  // Re-check approval and integrity with the registry every time we show content.
  // The dashboard's list is only a snapshot, and may be stale after withdrawal.
  let lesson;
  try {
    const data = await request('/api/lessons/' + encodeURIComponent(session.lesson_id) + '/' + encodeURIComponent(session.lesson_version));
    lesson = data.lesson;
  } catch (_) {
    show('dashboard');
    message('This activity is unavailable or has been withdrawn. Its history remains available.', true);
    return;
  }
  if (!lesson || !lesson.stages?.[session.stage_index]) {
    show('dashboard');
    message('This activity is unavailable or has been withdrawn. Its history remains available.', true);
    return;
  }
  show('lesson-view');
  const step = lesson.stages[session.stage_index];
  $('stage-title').textContent = step.title;
  $('stage-instruction').textContent = step.instruction;
  $('stage-word').textContent = step.display_text;
  $('coach-note').textContent = step.coach_note;
  $('lesson-counter').textContent = `Stage ${session.stage_index + 1} of 6 · ${session.responses.length} fictional practice response(s)`;
  $('session-status').textContent = `Activity status: ${session.status.replaceAll('_', ' ')}. Mastery is not assessed.`;
  $('progress').setAttribute('aria-valuenow', String(session.stage_index + 1));
  $('progress-fill').style.width = ((session.stage_index + 1) / 6 * 100) + '%';
  const actions = $('lesson-actions');
  const responses = $('response-area');
  actions.replaceChildren(); responses.replaceChildren();
  if (session.status === 'created') actions.append(button('Begin lesson', () => runAction('activate'), true));
  if (session.status === 'paused') actions.append(button('Resume', () => runAction('resume'), true));
  if (session.status === 'active') {
    const form = el('form');
    const prompt = el('label', step.response_prompt + ' (fictional practice only)');
    prompt.htmlFor = 'answer';
    const answer = el('textarea'); answer.id = 'answer'; answer.required = true; answer.maxLength = 500;
    const assistanceLabel = el('label');
    const assistance = el('input'); assistance.type = 'checkbox'; assistance.id = 'assistance';
    assistanceLabel.append(assistance, document.createTextNode('Audio or modeling assistance used'));
    const submit = el('button', 'Save practice response'); submit.type = 'submit';
    form.append(prompt, answer, assistanceLabel, submit);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      await runAction('respond', {response: answer.value, assisted: assistance.checked});
    });
    responses.append(form);
    actions.append(button(session.stage_index === 5 ? 'Complete activity' : 'Next stage', () => runAction(session.stage_index === 5 ? 'complete' : 'next'), true));
    actions.append(button('Pause', () => runAction('pause')));
  }
  $('stage-title').focus?.();
}
async function runAction(action, extra = {}) {
  try {
    message('');
    const data = await request('/api/sessions/' + encodeURIComponent(state.session.session_id) + '/action', {action, revision: state.session.revision, ...extra});
    state.session = data.session;
    await openSession();
  } catch (error) { show('dashboard'); message(friendlyError(error), true); }
}
$('login-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    message('');
    await request('/api/login', {identity: $('identity').value, passphrase: $('passphrase').value});
    $('passphrase').value = '';
    const me = await request('/api/me');
    state.identity = me.identity; state.csrf = me.csrf;
    await loadDashboard();
  } catch (error) { $('passphrase').value = ''; message(friendlyError(error), true); }
});
$('logout').addEventListener('click', async () => {
  try { await request('/api/logout', {}); } catch (error) { message(friendlyError(error), true); return; }
  state.identity = state.csrf = state.profile = state.session = null;
  state.profiles = []; state.lessons = [];
  show('login-view'); message('Signed out.');
});
$('profile-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!state.profile) { message('An authorized fictional profile is required to add another.', true); return; }
  try {
    const data = await request('/api/profiles', {anchor_id: state.profile, student_id: $('new-profile').value});
    state.profile = data.profile.id;
    $('new-profile').value = '';
    message('Fictional profile added.');
    await loadDashboard();
  } catch (error) { message(friendlyError(error), true); }
});
$('back').addEventListener('click', async () => {
  try { message(''); await loadDashboard(); } catch (error) { message(friendlyError(error), true); }
});
(async function initialize() {
  try {
    const me = await request('/api/me');
    state.identity = me.identity; state.csrf = me.csrf;
    if (state.identity) await loadDashboard(); else show('login-view');
  } catch (_) { show('login-view'); }
})();
