'use strict';

// Synthetic-demo client. The server, not this module, checks identity,
// relationship, purpose, consent, the lesson pin and each case transition.
(function (global) {
  const DESTINATIONS = new Set(['voice', 'activities', 'signin']);
  const CHALLENGES = new Set(['decode', 'context', 'sequence']);
  const STEPS = new Set(['post_office','decode','archive','context','lesson','lesson_active','bookshop','sequence','solved']);
  const PHASES = new Set(['exploring','activity_requested','activity_started','returned','case_solved']);
  const PROFILE = /^synthetic-[A-Za-z0-9_-]{1,80}$/;
  const CLUE_IDS = new Set(['clue-decode','clue-context','clue-sequence']);
  const isText = (value, max) => typeof value === 'string' && value.length <= max;
  function empty() {
    return Object.freeze({case_id:'synthetic-vanishing-storybook-v1', revision:0,
      phase:'exploring', step:'post_office', caseTitle:'The Vanishing Storybook',
      message:'Select a fictional profile to investigate.', clues:Object.freeze([]),
      visited:Object.freeze([]), challengeId:null, feedback:'',
      allowedDestinations:Object.freeze([]), pendingHint:false, boundSessionId:null});
  }
  function checkedCase(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)
        || value.case_id !== 'synthetic-vanishing-storybook-v1'
        || !Number.isSafeInteger(value.revision) || value.revision < 0
        || !STEPS.has(value.step) || !PHASES.has(value.phase)
        || !isText(value.caseTitle,120) || !isText(value.message,300) || !isText(value.feedback,500)
        || !Array.isArray(value.clues) || value.clues.length > 3
        || !Array.isArray(value.visited) || value.visited.length > 3
        || !Array.isArray(value.allowedDestinations) || value.allowedDestinations.length > 3
        || value.visited.some(id => !DESTINATIONS.has(id))
        || value.allowedDestinations.some(id => !DESTINATIONS.has(id))
        || new Set(value.visited).size !== value.visited.length
        || new Set(value.allowedDestinations).size !== value.allowedDestinations.length
        || !(value.challengeId === null || CHALLENGES.has(value.challengeId))
        || typeof value.pendingHint !== 'boolean'
        || !(value.boundSessionId === null || (isText(value.boundSessionId,128) && value.boundSessionId.length > 0))) {
      throw new TypeError('Invalid case state');
    }
    const clues = value.clues.map(clue => {
      if (!clue || typeof clue !== 'object' || Array.isArray(clue)
          || !CLUE_IDS.has(clue.id) || !isText(clue.title,120) || !isText(clue.text,500)
          || typeof clue.usedHint !== 'boolean') throw new TypeError('Invalid case clue');
      return Object.freeze({id:clue.id,title:clue.title,text:clue.text,usedHint:clue.usedHint});
    });
    if (new Set(clues.map(clue => clue.id)).size !== clues.length) throw new TypeError('Duplicate case clue');
    return Object.freeze({case_id:value.case_id,revision:value.revision,phase:value.phase,step:value.step,
      caseTitle:value.caseTitle,message:value.message,clues:Object.freeze(clues),
      visited:Object.freeze([...value.visited]),challengeId:value.challengeId,feedback:value.feedback,
      allowedDestinations:Object.freeze([...value.allowedDestinations]),pendingHint:value.pendingHint,
      boundSessionId:value.boundSessionId});
  }

  function create(options = {}) {
    if (typeof options.request !== 'function') throw new TypeError('A request function is required.');
    const request = options.request;
    const navigate = typeof options.navigate === 'function' ? options.navigate : () => {};
    const onChange = typeof options.onChange === 'function' ? options.onChange : () => {};
    const onError = typeof options.onError === 'function' ? options.onError : () => {};
    let profile = null, epoch = 0, value = empty(), loaded = false, tail = Promise.resolve();
    const path = id => '/api/profiles/' + encodeURIComponent(id) + '/investigation';
    const current = (id, version) => profile === id && epoch === version;
    function notify() { onChange(value); }
    function clear() {
      epoch++; profile = null; value = empty(); loaded = false; tail = Promise.resolve(); notify();
    }
    async function load(id) {
      clear();
      if (typeof id !== 'string' || !PROFILE.test(id)) { onError('Select a fictional profile to investigate.'); return false; }
      profile = id;
      const version = epoch;
      try {
        const result = await request(path(id));
        if (!current(id,version)) return false;
        value = checkedCase(result?.case); loaded = true; notify(); return current(id,version) && loaded;
      } catch (_) {
        if (current(id,version)) { loaded = false; value = empty(); notify(); onError('The investigation is unavailable.'); }
        return false;
      }
    }
    async function refreshAfterConflict(id,version) {
      try {
        const result = await request(path(id));
        if (!current(id,version)) return;
        value = checkedCase(result?.case); loaded = true; notify();
        onError('The case changed elsewhere. Please review it and try again.');
      } catch (_) {
        if (current(id,version)) { loaded = false; value = empty(); notify(); onError('The investigation is unavailable.'); }
      }
    }
    function perform(action, fields = {}, after = null) {
      const id = profile, version = epoch;
      if (!id || !loaded) return Promise.resolve(false);
      const work = async () => {
        if (!current(id,version) || !loaded) return false;
        const before = value;
        // An earlier queued action may have advanced the case. Drop obsolete
        // input locally instead of treating the server's expected denial as a
        // revoked-authorization response and clearing an otherwise valid case.
        if (action === 'visit' && !before.allowedDestinations.includes(fields.destination)) return false;
        if ((action === 'answer' || action === 'hint') && before.challengeId !== fields.challenge) return false;
        if (action === 'bind' && before.step !== 'lesson') return false;
        if ((action === 'finish' || action === 'cancel') && before.step !== 'lesson_active') return false;
        try {
          const result = await request(path(id), {action, revision:before.revision, ...fields});
          if (!current(id,version)) return false;
          const next = checkedCase(result?.case);
          if (next.revision <= before.revision) throw new TypeError('Case revision did not advance');
          value = next; notify();
          if (!current(id,version)) return false;
          if (after) after(before,next);
          return true;
        } catch (error) {
          if (current(id,version)) {
            if (error?.status === 409) await refreshAfterConflict(id,version);
            else if (error?.status === 401 || error?.status === 403) {
              // Revoked consent, a changed relationship, or an expired session
              // must immediately remove the prior profile's case from the UI.
              clear();
              onError('The investigation is unavailable. Please sign in again or contact the prototype administrator.');
            }
            else onError('The investigation action is unavailable. Please try again.');
          }
          return false;
        }
      };
      const result = tail.then(work, work);
      tail = result.then(() => undefined, () => undefined);
      return result;
    }
    return Object.freeze({
      snapshot: () => value,
      load,
      // Clearing an identity/profile must never delete its stored case.
      reset: clear,
      restart: () => perform('reset'),
      visit(destination) {
        // Locked destinations are normal game state, not an authorization
        // failure. Avoid sending a request that the server will rightly deny.
        if (!loaded || !DESTINATIONS.has(destination) || !value.allowedDestinations.includes(destination)) return Promise.resolve(false);
        return perform('visit',{destination},(before,next) => {
          if (before.step === 'lesson_active' && destination === 'activities'
              && next.step === 'lesson_active' && next.boundSessionId) navigate('resume',next.boundSessionId);
          else if ((before.step === 'lesson' && destination === 'activities' && next.step === 'lesson')
              || (before.step === 'solved' && next.step === 'solved')) navigate(destination);
        });
      },
      hint(challenge) {
        if (!CHALLENGES.has(challenge) || value.challengeId !== challenge) return Promise.resolve(false);
        return perform('hint',{challenge});
      },
      attempt(challenge, choice, hintUsed) {
        if (!CHALLENGES.has(challenge) || !['a','b','c'].includes(choice) || typeof hintUsed !== 'boolean') return Promise.resolve(false);
        let solved = false;
        return perform('answer',{challenge,choice,hint_used:hintUsed},(before,next) => {
          solved = before.step === challenge && next.step !== challenge;
          if (solved && before.step === 'context' && next.step === 'lesson') navigate('activities');
        }).then(ok => ok && solved);
      },
      bindSession(session, selectedProfile) {
        if (value.step !== 'lesson' || !profile || selectedProfile !== profile || !session || session.student_id !== profile
            || !isText(session.session_id,128) || !session.session_id) return Promise.resolve(false);
        return perform('bind',{session_id:session.session_id});
      },
      observeSession(session) {
        if (!session || !profile || session.student_id !== profile || session.session_id !== value.boundSessionId) return Promise.resolve(false);
        if (session.status === 'completed') return perform('finish');
        if (['abandoned','invalidated','closed'].includes(session.status)) return perform('cancel');
        return Promise.resolve(false);
      },
      cancelBoundSession() {
        if (value.step !== 'lesson_active') return Promise.resolve(false);
        return perform('cancel');
      },
      // The server moves directly to bookshop after verifying the stored lesson.
      returnToWorld: () => value.step === 'bookshop',
      isLoaded: () => loaded,
      isLoadedFor: id => loaded && profile === id
    });
  }
  global.LivingInvestigationClient = Object.freeze({create});
})(window);
