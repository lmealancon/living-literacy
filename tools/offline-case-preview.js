'use strict';
// Preview-only in-memory simulator. Never include this in a deployed website.
// The packaged preview must define __LIVING_PREVIEW_LESSON__ before this file.
(function (global) {
  if (!global.location || global.location.protocol !== 'file:') return;
  const lesson = global.__LIVING_PREVIEW_LESSON__;
  if (!lesson || lesson.lesson_id !== 'synthetic-lesson-word-study'
      || lesson.version !== 'demo-1' || !Array.isArray(lesson.stages)
      || lesson.stages.length !== 6) {
    global.fetch = async () => ({ok:false, status:503, json:async()=>({error:'Offline preview lesson unavailable'})});
    return;
  }
  const identity = 'synthetic-parent-1', student = 'synthetic-student-1';
  let signedIn = true, serial = 0;
  const sessions = new Map(), requests = new Map();
  const copy = value => JSON.parse(JSON.stringify(value));
  const reply = (status, value) => ({ok:status >= 200 && status < 300, status, json:async()=>copy(value)});
  const denied = () => reply(403, {error:'Offline preview action unavailable'});
  const findSession = id => sessions.get(id);
  const validRevision = (session, data) => Number.isSafeInteger(data.revision) && data.revision === session.revision;

  global.fetch = async (path, options = {}) => {
    // No forwarding: unknown URLs always fail locally and never reach a network.
    if (typeof path !== 'string' || !path.startsWith('/api/') || path.includes('?') || path.includes('#')) return denied();
    const method = options.method || 'GET';
    let data = {};
    if (method === 'POST') {
      try { data = JSON.parse(options.body || '{}'); } catch (_) { return reply(400, {error:'Invalid preview request'}); }
      if (!data || typeof data !== 'object' || Array.isArray(data)) return reply(400, {error:'Invalid preview request'});
    } else if (method !== 'GET') return denied();
    if (path === '/api/login' && method === 'POST') {
      if (data.identity !== identity || data.passphrase !== 'preview') return denied();
      signedIn = true; return reply(200,{identity,csrf:'fictional-preview-csrf'});
    }
    if (!signedIn) return denied();
    if (path === '/api/me' && method === 'GET') return reply(200,{identity,csrf:'fictional-preview-csrf'});
    if (path === '/api/logout' && method === 'POST') { signedIn = false; sessions.clear(); requests.clear(); return reply(200,{ok:true}); }
    if (path === '/api/profiles' && method === 'GET') return reply(200,{profiles:[{id:student,workspace_id:'synthetic-preview',synthetic:true}]});
    if (path === '/api/lessons' && method === 'GET') return reply(200,{lessons:[{lesson_id:lesson.lesson_id,version:lesson.version,title:lesson.title}]});
    if (path === '/api/lessons/' + lesson.lesson_id + '/' + lesson.version && method === 'GET') return reply(200,{lesson});
    if (path === '/api/history/' + student && method === 'GET') return reply(200,{sessions:[...sessions.values()]});
    if (path === '/api/profiles/' + student + '/interests' && method === 'GET') return reply(200,{interests:[],options:[]});
    if (path === '/api/profiles/' + student + '/activity' && method === 'GET') {
      const responses = [...sessions.values()].flatMap(s => s.responses);
      return reply(200,{responses_total:responses.length,responses_assisted:responses.filter(r=>r.assistance.audio_or_modeling).length,assistance_unrecorded:0});
    }
    if (path === '/api/curriculum/domains' && method === 'GET') return reply(200,{status:'candidate_counts_only',canonical_skill_definitions_present:false,domains:[{name:'Word recognition',strand:'word_recognition'},{name:'Language comprehension',strand:'language_comprehension'}]});
    if (path === '/api/companion/status' && method === 'GET') return reply(200,{enabled:false});
    if (path === '/api/sessions' && method === 'POST') {
      if (data.student_id !== student || data.lesson_id !== lesson.lesson_id || data.version !== lesson.version || typeof data.idempotency_key !== 'string') return denied();
      let id = requests.get(data.idempotency_key);
      if (!id) {
        id = 'synthetic-preview-session-' + (++serial); requests.set(data.idempotency_key,id);
        sessions.set(id,{session_id:id,workspace_id:'synthetic-preview',student_id:student,lesson_id:lesson.lesson_id,lesson_version:lesson.version,status:'created',stage_index:0,revision:0,responses:[],mastery_status:'not_assessed'});
      }
      return reply(201,{session:findSession(id)});
    }
    const match = /^\/api\/sessions\/(synthetic-preview-session-\d+)(?:\/(action))?$/.exec(path);
    if (match) {
      const session = findSession(match[1]);
      if (!session) return denied();
      if (!match[2] && method === 'GET') return reply(200,{session});
      if (match[2] !== 'action' || method !== 'POST') return denied();
      if (!validRevision(session,data)) return reply(409,{error:'Conflicting preview change'});
      if (data.action === 'activate' && session.status === 'created') session.status = 'active';
      else if (data.action === 'pause' && session.status === 'active') session.status = 'paused';
      else if (data.action === 'resume' && session.status === 'paused') session.status = 'active';
      else if (data.action === 'next' && session.status === 'active' && session.stage_index < 5) session.stage_index++;
      else if (data.action === 'complete' && session.status === 'active' && session.stage_index === 5) session.status = 'completed';
      else if (data.action === 'respond' && session.status === 'active' && typeof data.response === 'string' && data.response.trim() && data.response.length <= 500 && typeof data.assisted === 'boolean') {
        session.responses.push({stage:lesson.stages[session.stage_index].id,response:data.response,assistance:{audio_or_modeling:data.assisted},independent_evidence_eligible:false});
      } else return denied();
      session.revision++;
      return reply(200,{session});
    }
    return reply(404,{error:'Not available in offline preview'});
  };
})(window);
