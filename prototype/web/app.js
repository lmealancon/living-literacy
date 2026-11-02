'use strict';
// Synthetic-data prototype. All access and content checks are enforced by the server.
const $ = id => document.getElementById(id);
const state = { csrf: null, identity: null, profiles: [], lessons: [], profile: null, session: null, history: [], epoch: 0 };
const ongoing = session => ['created', 'active', 'paused'].includes(session.status);
const snapshot = () => ({epoch: state.epoch, identity: state.identity, profile: state.profile});
const current = stamp => stamp.epoch === state.epoch && stamp.identity === state.identity && stamp.profile === state.profile;
function clearLessonData() {
  state.session = null;
  for (const id of ['stage-pathway', 'response-area', 'lesson-actions']) $(id).replaceChildren();
  for (const id of ['stage-title', 'stage-instruction', 'stage-word', 'coach-note', 'lesson-counter', 'session-status']) $(id).textContent = '';
  $('progress-fill').style.width = '0%'; $('progress').setAttribute('aria-valuenow', '1');
}
function clearProfileData() {
  state.history = []; clearLessonData();
  for (const id of ['history', 'interests']) $(id).replaceChildren();
  for (const id of ['stat-inprogress', 'stat-completed']) $(id).textContent = '—';
}
function clearProtectedData() {
  clearProfileData();
  state.profiles = []; state.lessons = []; state.profile = null;
  for (const id of ['profiles', 'lesson-list']) $(id).replaceChildren();
  $('stat-profiles').textContent = '—';
  $('new-profile').value = ''; $('history-filter').value = 'all';
}


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
  const stamp = snapshot();
  clearProfileData();
  show('dashboard');
  const [profileData, lessonData] = await Promise.all([request('/api/profiles'), request('/api/lessons')]);
  if (!current(stamp)) return;
  state.profiles = profileData.profiles || [];
  state.lessons = lessonData.lessons || [];
  if (!state.profiles.some(p => p.id === state.profile)) state.profile = state.profiles[0]?.id || null;
  $('stat-profiles').textContent = String(state.profiles.length);
  renderProfiles();
  renderLessons();
  await Promise.all([loadHistory(), loadInterests()]);
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
      state.epoch++;
      clearProfileData();
      state.profile = profile.id;
      const stamp = snapshot();
      renderProfiles(); renderLessons();
      try { await Promise.all([loadHistory(), loadInterests()]); } catch (error) { if (current(stamp)) message(friendlyError(error), true); }
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
      const stamp = snapshot();
      try {
        message('');
        if (!pendingKey) pendingKey = crypto.randomUUID();
        const result = await request('/api/sessions', { student_id: stamp.profile, lesson_id: lesson.lesson_id, version: lesson.version, idempotency_key: pendingKey });
        if (!current(stamp)) return;
        pendingKey = null;
        state.session = result.session;
        await openSession();
      } catch (error) { if (current(stamp)) message(friendlyError(error), true); }
    }, true));
    area.append(row);
  });
}
async function loadInterests() {
  const area = $('interests');
  area.replaceChildren();
  if (!state.profile) { area.append(el('p', 'Select a fictional profile to see its choices.')); return; }
  const selected = state.profile; const stamp = snapshot();
  let data;
  try { data = await request('/api/profiles/' + encodeURIComponent(selected) + '/interests'); }
  catch (_) { if (current(stamp)) area.append(el('p', 'Interest choices are currently unavailable.')); return; }
  if (!current(stamp)) return;
  const options = Array.isArray(data.options) ? data.options : [];
  const chosen = Array.isArray(data.interests) ? data.interests : [];
  if (!options.length) { area.append(el('p', 'Interest choices are currently unavailable.')); return; }
  const form = el('form');
  const fieldset = el('fieldset', undefined, 'interest-fieldset');
  fieldset.append(el('legend', 'Choose any interests for this fictional learner'));
  const choices = el('div', undefined, 'interest-choices');
  options.forEach(option => {
    const label = el('label', undefined, 'interest-choice');
    const box = el('input'); box.type = 'checkbox'; box.value = option; box.checked = chosen.includes(option);
    label.append(box, document.createTextNode(option.charAt(0).toUpperCase() + option.slice(1)));
    choices.append(label);
  });
  fieldset.append(choices);
  const save = el('button', 'Save fictional interests'); save.type = 'submit';
  form.append(fieldset, save);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const values = Array.from(choices.querySelectorAll('input:checked')).map(input => input.value);
    try {
      await request('/api/profiles/' + encodeURIComponent(selected) + '/interests', {interests: values});
      if (current(stamp)) message('Fictional interests saved. Lessons are not personalized yet.');
    } catch (error) { if (current(stamp)) message(friendlyError(error), true); }
  });
  area.append(form);
}
async function loadHistory() {
  const area = $('history');
  area.replaceChildren();
  if (!state.profile) {
    state.history = [];
    $('stat-inprogress').textContent = '—'; $('stat-completed').textContent = '—';
    area.append(el('p', 'Choose a fictional profile to view activity.'));
    return;
  }
  const selected = state.profile; const stamp = snapshot();
  const data = await request('/api/history/' + encodeURIComponent(selected));
  // Selection may have changed while the request was in flight.
  if (!current(stamp)) return;
  state.history = data.sessions || [];
  $('stat-inprogress').textContent = String(state.history.filter(ongoing).length);
  $('stat-completed').textContent = String(state.history.filter(session => session.status === 'completed').length);
  renderHistory();
}
function renderHistory() {
  const area = $('history');
  area.replaceChildren();
  const filter = $('history-filter').value;
  const sessions = state.history.filter(session => filter === 'all' ||
    (filter === 'ongoing' ? ongoing(session) : session.status === 'completed'));
  if (!sessions.length) {
    area.append(el('p', state.history.length ? 'No activities match this filter.' : 'No practice activity yet.'));
    return;
  }
  sessions.forEach(session => {
    const row = el('div', undefined, 'item');
    const details = el('div');
    const lesson = state.lessons.find(item => item.lesson_id === session.lesson_id && item.version === session.lesson_version);
    details.append(el('strong', lesson?.title || 'Unavailable activity'), el('p', 'Status: ' + session.status.replaceAll('_', ' '), 'fine'));
    row.append(details, button('Open', async () => {
      const stamp = snapshot();
      try {
        const data = await request('/api/sessions/' + encodeURIComponent(session.session_id));
        if (!current(stamp)) return;
        state.session = data.session;
        await openSession();
      } catch (error) { if (current(stamp)) message(friendlyError(error), true); }
    }));
    area.append(row);
  });
}
$('history-filter').addEventListener('change', renderHistory);
async function openSession() {
  const session = state.session;
  const stamp = snapshot();
  // Re-check approval and integrity with the registry every time we show content.
  // The dashboard's list is only a snapshot, and may be stale after withdrawal.
  let lesson;
  try {
    const data = await request('/api/lessons/' + encodeURIComponent(session.lesson_id) + '/' + encodeURIComponent(session.lesson_version));
    lesson = data.lesson;
  } catch (_) {
    if (current(stamp) && state.session === session) {
      clearLessonData(); show('dashboard');
      message('This activity is unavailable or has been withdrawn. Its history remains available.', true);
    }
    return;
  }
  if (!current(stamp) || state.session !== session) return;
  if (!lesson || !lesson.stages?.[session.stage_index]) {
    clearLessonData(); show('dashboard');
    message('This activity is unavailable or has been withdrawn. Its history remains available.', true);
    return;
  }
  show('lesson-view');
  const step = lesson.stages[session.stage_index];
  const pathway = $('stage-pathway'); pathway.replaceChildren();
  lesson.stages.forEach((item, index) => {
    const node = el('li', `${index + 1}. ${item.title}`);
    if (index === session.stage_index) node.setAttribute('aria-current', 'step');
    else if (index < session.stage_index) node.className = 'past';
    pathway.append(node);
  });
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
  if (session.status === 'paused') { responses.append(el('p', 'Take a quiet moment. Resume when you are ready.', 'break-note')); actions.append(button('Resume activity', () => runAction('resume'), true)); }
  if (session.status === 'active') {
    const form = el('form');
    const prompt = el('label', step.response_prompt + ' (fictional practice only)');
    prompt.htmlFor = 'answer';
    const answer = el('textarea'); answer.id = 'answer'; answer.required = true; answer.maxLength = 500;
    const assistanceFieldset = el('fieldset', undefined, 'assistance-fieldset');
    assistanceFieldset.append(el('legend', 'Was audio or modeling assistance used?'));
    for (const [value, caption] of [['yes', 'Yes, assistance was used'], ['no', 'No assistance was used']]) {
      const label = el('label', undefined, 'assistance-option');
      const input = el('input'); input.type = 'radio'; input.name = 'assistance'; input.value = value; input.required = true;
      label.append(input, document.createTextNode(caption)); assistanceFieldset.append(label);
    }
    const submit = el('button', 'Save practice response'); submit.type = 'submit';
    form.append(prompt, answer, assistanceFieldset, submit);
    if (session.lesson_id === 'synthetic-lesson-word-study' && step.id === 'practice') {
      const builder = el('div', undefined, 'word-builder');
      builder.append(el('p', 'Build a word with these letters. Choose a letter, then choose another.'));
      const built = el('output', '', 'built-word'); built.setAttribute('aria-live', 'polite');
      built.setAttribute('aria-label', 'Letters selected');
      const letters = el('div', undefined, 'letter-choices');
      const tiles = [];
      ['p', 'm', 'a'].forEach(letter => {
        const tile = button(letter, () => {
          if (tile.disabled) return;
          tile.disabled = true; built.textContent += letter; answer.value = built.textContent;
        });
        tiles.push(tile); letters.append(tile);
      });
      letters.append(button('Clear letters', () => {
        built.textContent = ''; answer.value = ''; tiles.forEach(tile => { tile.disabled = false; });
      }));
      builder.append(letters, built);
      responses.append(builder);
    }
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const assistance = form.querySelector('input[name="assistance"]:checked');
      if (!assistance) { message('Choose whether assistance was used before saving.', true); return; }
      await runAction('respond', {response: answer.value, assisted: assistance.value === 'yes'});
    });
    responses.append(form);
    actions.append(button(session.stage_index === 5 ? 'Complete activity' : 'Next stage', () => runAction(session.stage_index === 5 ? 'complete' : 'next'), true));
    actions.append(button('Take a quiet break', () => runAction('pause')));
  }
  $('stage-title').focus?.();
}
async function runAction(action, extra = {}) {
  const stamp = snapshot(); const session = state.session;
  if (!session) return;
  try {
    message('');
    const data = await request('/api/sessions/' + encodeURIComponent(session.session_id) + '/action', {action, revision: session.revision, ...extra});
    if (!current(stamp) || state.session !== session) return;
    state.session = data.session;
    await openSession();
  } catch (error) { if (current(stamp) && state.session === session) { clearLessonData(); show('dashboard'); message(friendlyError(error), true); } }
}
$('login-form').addEventListener('submit', async event => {
  event.preventDefault();
  const identity = $('identity').value; const passphrase = $('passphrase').value;
  const submit = event.currentTarget.querySelector('button[type="submit"]');
  if (submit.disabled) return;
  submit.disabled = true;
  state.epoch++; state.identity = null; state.csrf = null; clearProtectedData();
  const stamp = snapshot();
  try {
    message('');
    await request('/api/login', {identity, passphrase});
    if (!current(stamp)) return;
    $('passphrase').value = '';
    const me = await request('/api/me');
    if (!current(stamp)) return;
    state.identity = me.identity; state.csrf = me.csrf;
    await loadDashboard();
  } catch (error) { if (state.epoch === stamp.epoch) { $('passphrase').value = ''; message(friendlyError(error), true); } }
  finally { submit.disabled = false; }
});
$('logout').addEventListener('click', async () => {
  // Build request while CSRF token is present; immediately hide and clear prior account data.
  const pending = request('/api/logout', {});
  state.epoch++; state.identity = null; state.csrf = null; clearProtectedData();
  $('identity').value = ''; $('passphrase').value = '';
  show('login-view'); message('Signing out…');
  const stamp = snapshot();
  try { await pending; if (current(stamp)) message('Signed out.'); }
  catch (_) { if (current(stamp)) message('Sign-out could not be confirmed. Please close this browser and sign in again.', true); }
});
$('profile-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!state.profile) { message('An authorized fictional profile is required to add another.', true); return; }
  const stamp = snapshot(); let activeEpoch = stamp.epoch;
  try {
    const data = await request('/api/profiles', {anchor_id: stamp.profile, student_id: $('new-profile').value});
    if (!current(stamp)) return;
    state.epoch++; activeEpoch = state.epoch; clearProfileData(); state.profile = data.profile.id;
    $('new-profile').value = '';
    message('Fictional profile added.');
    await loadDashboard();
  } catch (error) { if (state.epoch === activeEpoch) message(friendlyError(error), true); }
});
$('back').addEventListener('click', async () => {
  const stamp = snapshot();
  try { message(''); await loadDashboard(); } catch (error) { if (current(stamp)) message(friendlyError(error), true); }
});
(async function initialize() {
  const stamp = snapshot();
  try {
    const me = await request('/api/me');
    if (!current(stamp)) return;
    state.identity = me.identity; state.csrf = me.csrf;
    if (state.identity) await loadDashboard(); else show('login-view');
  } catch (_) { if (current(stamp)) show('login-view'); }
})();
