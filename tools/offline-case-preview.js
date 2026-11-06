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
  const freshCase = revision => ({step:'post_office',revision,decode:null,context:null,sequence:null,pendingHint:false,sessionId:null});
  let investigation = freshCase(0);
  const messages = {
    post_office:'A storybook is missing! Visit the Post Office to investigate the first clue.',
    decode:'A folded note arrived at the Post Office. Read it to find the first clue.',
    archive:'Clue found! Follow the map to the blue lantern at the archive.',
    context:'A note waits beside the blue lantern at the archive.',
    lesson:'Complete the fictional map activity before continuing to the bookshop.',
    lesson_active:'Complete the fictional map activity, then return to the investigation.',
    bookshop:'Follow the note to the bookshop and investigate the locked box.',
    sequence:'At the bookshop, use the clues to work out what happens next.',
    solved:'The storybook is found! Case complete. This fictional game does not establish mastery.'
  };
  const clueData = {
    decode:{id:'clue-decode',title:'The folded map',text:'The folded map shows a blue lantern outside the archive.'},
    context:{id:'clue-context',title:'The lantern note',text:'Beside the blue lantern, a note says: Take the key to the bookshop.'},
    sequence:{id:'clue-sequence',title:'The missing storybook',text:'Inside the box is the missing storybook.'}
  };
  const copy = value => JSON.parse(JSON.stringify(value));
  const reply = (status, value) => ({ok:status >= 200 && status < 300, status, json:async()=>copy(value)});
  const denied = () => reply(403, {error:'Offline preview action unavailable'});
  const findSession = id => sessions.get(id);
  const validRevision = (session, data) => Number.isSafeInteger(data.revision) && data.revision === session.revision;
  function caseSnapshot(feedback = '') {
    const step=investigation.step;
    const allowed={post_office:['voice'],decode:['voice'],archive:['activities'],context:['activities'],lesson:['activities'],lesson_active:['activities'],bookshop:['signin'],sequence:['signin'],solved:['signin','activities','voice']}[step];
    const phase={lesson:'activity_requested',lesson_active:'activity_started',bookshop:'returned',sequence:'returned',solved:'case_solved'}[step] || 'exploring';
    const visited=[];
    if (step !== 'post_office') visited.push('voice');
    if (['context','lesson','lesson_active','bookshop','sequence','solved'].includes(step)) visited.push('activities');
    if (['sequence','solved'].includes(step)) visited.push('signin');
    const clues=['decode','context','sequence'].filter(id=>investigation[id] !== null)
      .map(id=>({...clueData[id],usedHint:investigation[id]}));
    return {case_id:'synthetic-vanishing-storybook-v1',revision:investigation.revision,phase,step,
      caseTitle:'The Vanishing Storybook',message:step === 'lesson' && feedback ? feedback : messages[step],clues,visited,
      challengeId:['decode','context','sequence'].includes(step)?step:null,feedback,
      allowedDestinations:allowed,pendingHint:investigation.pendingHint,boundSessionId:investigation.sessionId};
  }
  function caseAction(data) {
    const fields = {
      visit:['action','revision','destination'],answer:['action','revision','challenge','choice','hint_used'],
      hint:['action','revision','challenge'],bind:['action','revision','session_id'],
      finish:['action','revision'],cancel:['action','revision'],reset:['action','revision']
    };
    if (typeof data.action !== 'string' || !Object.hasOwn(fields,data.action)
        || Object.keys(data).sort().join('|') !== fields[data.action].slice().sort().join('|')) return reply(400,{error:'Invalid preview case request'});
    if (!Number.isSafeInteger(data.revision) || data.revision < 0) return denied();
    if (data.revision !== investigation.revision) return reply(409,{error:'Conflicting preview case change'});
    const step=investigation.step;
    let feedback='';
    if (data.action === 'visit') {
      if (!['voice','activities','signin'].includes(data.destination)) return denied();
      const transitions={post_office:['voice','decode'],decode:['voice','decode'],archive:['activities','context'],context:['activities','context'],lesson:['activities','lesson'],lesson_active:['activities','lesson_active'],bookshop:['signin','sequence'],sequence:['signin','sequence']};
      if (step !== 'solved') {
        const pair=transitions[step];
        if (!pair || data.destination !== pair[0]) return denied();
        investigation.step=pair[1];
      }
    } else if (data.action === 'hint') {
      if (!['decode','context','sequence'].includes(data.challenge) || data.challenge !== step) return denied();
      investigation.pendingHint=true;
    } else if (data.action === 'answer') {
      const answers={decode:'a',context:'b',sequence:'c'};
      if (!Object.hasOwn(answers,data.challenge) || data.challenge !== step || !['a','b','c'].includes(data.choice) || typeof data.hint_used !== 'boolean') return denied();
      investigation.pendingHint = investigation.pendingHint || data.hint_used;
      if (answers[data.challenge] !== data.choice) feedback='Not quite. Read the clue and try again.';
      else {
        investigation[data.challenge]=investigation.pendingHint; investigation.pendingHint=false;
        investigation.step={decode:'archive',context:'lesson',sequence:'solved'}[data.challenge];
        feedback='Clue found.';
      }
    } else if (data.action === 'bind') {
      const session=findSession(data.session_id);
      if (step !== 'lesson' || !session || session.student_id !== student || session.lesson_id !== lesson.lesson_id
          || session.lesson_version !== lesson.version || !['created','active','paused'].includes(session.status)) return denied();
      investigation.step='lesson_active'; investigation.sessionId=session.session_id;
    } else if (data.action === 'finish') {
      const session=findSession(investigation.sessionId);
      if (step !== 'lesson_active' || !session || session.status !== 'completed' || session.stage_index !== 5) return denied();
      investigation.sessionId=null;
      if (!session.responses.some(item=>item.stage === 'practice' && typeof item.response === 'string' && item.response.trim().toLowerCase() === 'map')) {
        investigation.step='lesson';
        feedback='Reopen the map activity and answer its Practice step to continue.';
      } else investigation.step='bookshop';
    } else if (data.action === 'cancel') {
      if (step !== 'lesson_active') return denied();
      investigation.step='lesson'; investigation.sessionId=null;
    } else if (data.action === 'reset') investigation=freshCase(investigation.revision);
    investigation.revision++;
    return reply(200,{case:caseSnapshot(feedback)});
  }

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
    if (path === '/api/logout' && method === 'POST') { signedIn = false; return reply(200,{ok:true}); }
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
    if (path === '/api/profiles/' + student + '/investigation') {
      if (method === 'GET') return reply(200,{case:caseSnapshot()});
      if (method === 'POST') return caseAction(data);
      return denied();
    }
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
