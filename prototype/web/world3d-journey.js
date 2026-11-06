'use strict';

// Original, fictional, adult-demo game state. This in-memory sequence is not
// authorization, assessment, educational validation, or proof of mastery.
(function (global) {
  const DESTINATIONS = new Set(['signin', 'activities', 'voice']);
  const ACTIVE = new Set(['created', 'active', 'paused']);
  const FINISHED_EARLY = new Set(['abandoned', 'invalidated', 'closed']);
  const DEMO_LESSON = 'synthetic-lesson-word-study';
  const CASE_TITLE = 'The Vanishing Storybook';
  const CLUES = Object.freeze({
    decode: Object.freeze({id:'clue-decode', title:'The folded map',
      text:'The folded map shows a blue lantern outside the archive.'}),
    context: Object.freeze({id:'clue-context', title:'The lantern note',
      text:'Beside the blue lantern, a note says: Take the key to the bookshop.'}),
    sequence: Object.freeze({id:'clue-sequence', title:'The missing storybook',
      text:'Inside the box is the missing storybook.'})
  });
  function validId(value) {
    return typeof value === 'string' && value.length > 0 && value.length <= 128;
  }
  function validSession(session) {
    return !!session && typeof session === 'object' && !Array.isArray(session)
      && ['session_id', 'workspace_id', 'student_id', 'lesson_id', 'lesson_version']
        .every(key => validId(session[key]))
      && typeof session.status === 'string'
      && Number.isSafeInteger(session.stage_index) && session.stage_index >= 0 && session.stage_index <= 5
      && Number.isSafeInteger(session.revision) && session.revision >= 0;
  }
  function hasPracticeResponse(session) {
    return Array.isArray(session.responses) && session.responses.some(item =>
      item && typeof item === 'object' && item.stage === 'practice'
        && typeof item.response === 'string' && item.response.trim().toLowerCase() === 'map');
  }

  function create(options = {}) {
    const navigate = typeof options.navigate === 'function' ? options.navigate : () => {};
    const onChange = typeof options.onChange === 'function' ? options.onChange : () => {};
    let phase = 'exploring', step = 'post_office', challengeId = null;
    let message = 'A storybook is missing! Visit the Post Office to investigate the first clue.';
    let feedback = '', clues = [], visited = new Set(), bound = null, lastRevision = -1;

    function destinations() {
      if (step === 'post_office') return ['voice'];
      if (step === 'archive' || step === 'lesson') return ['activities'];
      if (step === 'bookshop') return ['signin'];
      if (step === 'solved') return ['signin', 'activities', 'voice'];
      return [];
    }
    function snapshot() {
      return Object.freeze({phase, message, visited:Object.freeze([...visited]), caseTitle:CASE_TITLE,
        clues:Object.freeze(clues.slice()), challengeId, feedback,
        allowedDestinations:Object.freeze(destinations())});
    }
    function notify() { onChange(snapshot()); }
    function sameSession(session) {
      return bound && ['session_id', 'workspace_id', 'student_id', 'lesson_id', 'lesson_version']
        .every(key => bound[key] === session[key]);
    }
    function clearBound() { bound = null; lastRevision = -1; }
    return Object.freeze({
      snapshot,
      visit(destination) {
        if (!DESTINATIONS.has(destination)) return false;
        if (!destinations().includes(destination)) {
          feedback = 'That stop is not available yet. Follow the current clue.';
          notify();
          return false;
        }
        visited.add(destination); feedback = '';
        if (step === 'solved') { notify(); navigate(destination); return true; }
        if (step === 'lesson') {
          phase = 'activity_requested';
          message = 'Open the fictional map activity to continue the case.';
          notify(); navigate('activities'); return true;
        }
        challengeId = step === 'post_office' ? 'decode' : step === 'archive' ? 'context' : 'sequence';
        message = step === 'post_office' ? 'A folded note arrived at the Post Office. Read it to find the first clue.'
          : step === 'archive' ? 'A note waits beside the blue lantern at the archive.'
          : 'At the bookshop, use the clues to work out what happens next.';
        notify();
        return true;
      },
      // The local, fixed synthetic evaluator determines the answer. A supplied
      // solved flag or clue ID is never accepted from the caller. The client is
      // not a security boundary, and no outcome represents reading mastery.
      attempt(id, choiceId, hintUsed) {
        if (!challengeId || id !== challengeId || typeof choiceId !== 'string' || typeof hintUsed !== 'boolean') return false;
        const reading = global.LivingInvestigationReading;
        if (!reading || typeof reading.evaluate !== 'function') {
          feedback = 'This fictional reading activity is unavailable.'; notify(); return false;
        }
        let result;
        try { result = reading.evaluate(id, choiceId, hintUsed); }
        catch (_) { feedback = 'Choose one of the available answers.'; notify(); return false; }
        if (!result || result.solved !== true || result.clue_id !== CLUES[id].id || result.hint_used !== hintUsed) {
          feedback = typeof result?.feedback === 'string' ? result.feedback : 'Try another answer.';
          notify(); return false;
        }
        clues = [...clues, Object.freeze({...CLUES[id], usedHint: hintUsed})]; challengeId = null; feedback = '';
        if (id === 'decode') {
          step = 'archive'; message = 'Clue found! Follow the map to the blue lantern at the archive.';
        } else if (id === 'context') {
          step = 'lesson'; phase = 'activity_requested';
          message = 'Clue found! Complete the fictional map activity before continuing to the bookshop.';
        } else {
          step = 'solved'; phase = 'case_solved';
          message = 'The storybook is found! Case complete. This fictional game does not establish mastery.';
        }
        notify();
        if (id === 'context') navigate('activities');
        return true;
      },
      // Only the actual authenticated start response for the existing fictional
      // map lesson can bind the case to a lesson. This call grants no access.
      bindSession(session, selectedProfileId) {
        if (step !== 'lesson' || phase !== 'activity_requested' || !validId(selectedProfileId)
            || !validSession(session) || session.student_id !== selectedProfileId
            || session.lesson_id !== DEMO_LESSON || !ACTIVE.has(session.status)) return false;
        bound = {};
        for (const key of ['session_id', 'workspace_id', 'student_id', 'lesson_id', 'lesson_version']) bound[key] = session[key];
        lastRevision = session.revision; phase = 'activity_started'; step = 'in_lesson';
        message = 'Complete the fictional map activity, then return to the investigation.';
        notify(); return true;
      },
      // Completion is a separate prerequisite, not evidence of an applied
      // reading answer. Each case clue still requires its own correct choice.
      observeSession(session) {
        if (phase !== 'activity_started' || !validSession(session) || !sameSession(session)
            || session.revision <= lastRevision) return false;
        if (session.status === 'completed') {
          if (session.stage_index !== 5) return false;
          if (!hasPracticeResponse(session)) {
            clearBound(); phase = 'activity_requested'; step = 'lesson';
            message = 'The map practice response was not completed as requested. Reopen the fictional activity and try again.';
            notify(); return true;
          }
          lastRevision = session.revision; phase = 'activity_completed';
          message = 'Activity complete. Return to the investigation to follow the next clue.';
          notify(); return true;
        }
        if (FINISHED_EARLY.has(session.status)) {
          clearBound(); phase = 'activity_requested'; step = 'lesson';
          message = 'That activity is unavailable. Reopen the fictional map activity to continue.';
          notify(); return true;
        }
        if (!ACTIVE.has(session.status)) return false;
        lastRevision = session.revision; return true;
      },
      // Leaving or failing to reopen an in-progress lesson must not strand the
      // case. This only clears local UI state; it does not mutate the session.
      cancelBoundSession() {
        if (phase !== 'activity_started') return false;
        clearBound(); phase = 'activity_requested'; step = 'lesson';
        message = 'The activity was left or became unavailable. Reopen the fictional map activity to continue.';
        notify(); return true;
      },
      returnToWorld() {
        if (phase !== 'activity_completed') return false;
        phase = 'returned'; step = 'bookshop'; clearBound();
        message = 'Follow the note to the bookshop and investigate the locked box.';
        notify(); return true;
      },
      reset() {
        phase = 'exploring'; step = 'post_office'; challengeId = null;
        message = 'A storybook is missing! Visit the Post Office to investigate the first clue.';
        feedback = ''; clues = []; visited = new Set(); clearBound(); notify();
      }
    });
  }
  global.LivingJourney = Object.freeze({create});
})(window);
