'use strict';

// Presentation and accessible controls for the fictional 3D world. This UI
// never grants access, opens a session, or stores learner information.
(function (global) {
  const PLACES = Object.freeze([
    Object.freeze({id:'voice', label:'Post Office'}),
    Object.freeze({id:'activities', label:'City Archive'}),
    Object.freeze({id:'signin', label:'Bookshop'})
  ]);
  const byId = id => PLACES.find(place => place.id === id);
  const make = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };
  function mount(root, options = {}) {
    if (!root || typeof root.replaceChildren !== 'function') throw new TypeError('A world container is required.');
    const navigate = typeof options.navigate === 'function' ? options.navigate : () => {};
    const onExit = typeof options.onExit === 'function' ? options.onExit : () => {};
    const onAnswer = typeof options.onAnswer === 'function' ? options.onAnswer : () => null;
    const onHint = typeof options.onHint === 'function' ? options.onHint : () => false;
    const onRestart = typeof options.onRestart === 'function' ? options.onRestart : () => false;
    let active = true, destroyed = false, nearby = null, engine = null, signs = null, held = null, graphicsFailed = false;
    let allowedDestinations = null, challengeId = null, challengeGeneration = 0, hintUsed = false, hintPending = false, answerPending = false;
    let visitGeneration = 0, pendingChallengeFocus = null;
    let restartPending = false, restartGeneration = 0;
    let guidePhase = 'exploring', guideChallenge = null, guideDestination = null;
    const movementButtons = [], destinationButtons = [], mapButtons = [];
    const canRender = () => Boolean(engine?.available && !graphicsFailed);
    function stopHeldMovement() {
      if (!held) return;
      if (held.timeout !== null) global.clearTimeout(held.timeout);
      if (held.interval !== null) global.clearInterval(held.interval);
      held = null;
    }
    function beginHeldMovement(button, dx, dz) {
      if (!active || destroyed || !canRender()) return;
      stopHeldMovement();
      button.suppressPointerClick = false;
      const press = {button, timeout:null, interval:null};
      held = press;
      press.timeout = global.setTimeout(() => {
        if (held !== press || !active || destroyed || !canRender()) return;
        button.suppressPointerClick = true;
        engine.move(dx, dz);
        press.interval = global.setInterval(() => {
          if (held === press && active && !destroyed && canRender()) engine.move(dx, dz);
        }, 140);
      }, 250);
    }
    const section = make('section', 'world3d');
    section.setAttribute('aria-labelledby', 'world3d-title');
    const header = make('header', 'world3d-header');
    const headingGroup = make('div', 'world3d-heading-group');
    headingGroup.append(make('p', 'world3d-eyebrow', 'An original fictional investigation'));
    const title = make('h2', 'world3d-title', 'The London Case Files');
    title.id = 'world3d-title';
    headingGroup.append(title, make('p', 'world3d-subtitle', 'Sign in with a fictional profile, then explore an imagined Victorian London, uncover clues, and use reading to follow the trail. Adult fictional-data demonstration only. Progress resumes for the same sign-in and profile while the demo database exists; free Render restarts erase it.'));
    const exit = make('button', 'world3d-exit', 'Back to workspace');
    exit.type = 'button'; exit.addEventListener('click', () => { if (active && !destroyed) onExit(); });
    header.append(headingGroup, exit);
    const gameArea = make('div', 'world3d-stage');
    const canvas = make('canvas', 'world3d-canvas');
    canvas.tabIndex = 0;
    canvas.setAttribute('aria-label', 'Victorian London investigation world. Focus this area and use arrow keys or W A S D to move. Press Enter or Space near a destination to visit. You can also use the controls below.');
    canvas.append(make('p', '', 'The 3D world is unavailable. Use the destination buttons below.'));
    gameArea.append(canvas);
    const quest = make('aside', 'world3d-quest');
    quest.setAttribute('aria-labelledby', 'world3d-quest-title');
    const questTitle = make('h3', 'world3d-quest-title', 'Your casebook');
    questTitle.id = 'world3d-quest-title';
    questTitle.setAttribute('tabindex', '-1');
    const questMessage = make('p', 'world3d-quest-message', 'Explore the city to begin your investigation.');
    questMessage.setAttribute('aria-live', 'polite');
    const visited = make('p', 'world3d-visited', 'Places visited: none yet.');
    const cluesTitle = make('h4', 'world3d-clues-title', 'Clues collected');
    const clues = make('ol', 'world3d-clues');
    clues.setAttribute('aria-label', 'Clues collected');
    const emptyClues = make('li', 'world3d-clue-empty', 'No clues collected yet.');
    clues.append(emptyClues);
    const restart = make('button', 'world3d-restart', 'Start case again');
    restart.type = 'button'; restart.hidden = true;
    quest.append(questTitle, questMessage, visited, cluesTitle, clues, restart);
    const guide = make('aside', 'world3d-guide');
    guide.setAttribute('aria-labelledby', 'world3d-guide-title');
    const guideTitle = make('h3', 'world3d-guide-title', 'Your case companion');
    guideTitle.id = 'world3d-guide-title';
    const guideNote = make('p', 'world3d-guide-note', 'Scripted guide · fictional demonstration');
    const guideReply = make('p', 'world3d-guide-reply', 'I can help you find your way through the case.');
    guideReply.setAttribute('role', 'status'); guideReply.setAttribute('aria-live', 'polite');
    const guideActions = make('div', 'world3d-guide-actions');
    const guideNext = make('button', 'world3d-guide-next', 'Where do I go?'); guideNext.type = 'button';
    const guideControls = make('button', 'world3d-guide-controls', 'How do I explore?'); guideControls.type = 'button';
    guideNext.addEventListener('click', () => {
      if (!active || destroyed) return;
      if (guideChallenge) guideReply.textContent = 'A reading challenge is open below. Read the prompt and choose an answer.';
      else if (guidePhase === 'activity_requested') guideReply.textContent = 'Open the fictional map activity, then return to the case.';
      else if (guidePhase === 'activity_started') guideReply.textContent = 'Continue the fictional map activity, then return to the case.';
      else if (guidePhase === 'activity_completed') guideReply.textContent = 'Return to the case to follow the next clue.';
      else if (guidePhase === 'case_solved') guideReply.textContent = 'The fictional case is complete. You can explore the locations again.';
      else if (guideDestination) guideReply.textContent = 'Your next location is the ' + guideDestination + '. Choose its destination button or move there in the world.';
      else guideReply.textContent = 'Follow the casebook to find the next place to investigate.';
    });
    guideControls.addEventListener('click', () => {
      if (active && !destroyed) guideReply.textContent = 'Choose a destination button, or focus the world and use the arrow keys. Near a location, choose Explore nearby.';
    });
    guideActions.append(guideNext, guideControls);
    guide.append(guideTitle, guideNote, guideReply, guideActions);
    const challenge = make('section', 'world3d-challenge'); challenge.hidden = true;
    challenge.setAttribute('aria-labelledby', 'world3d-challenge-title');
    const challengeLabel = make('p', 'world3d-challenge-label', 'Reading investigation · unreviewed adult demonstration');
    const challengeTitle = make('h3', 'world3d-challenge-title', 'Reading challenge'); challengeTitle.id = 'world3d-challenge-title'; challengeTitle.setAttribute('tabindex', '-1');
    const teaching = make('p', 'world3d-challenge-teaching');
    const passage = make('blockquote', 'world3d-challenge-passage');
    const prompt = make('p', 'world3d-challenge-prompt');
    const answers = make('div', 'world3d-challenge-answers'); answers.setAttribute('aria-label', 'Choose an answer');
    const hint = make('button', 'world3d-hint', 'Show a hint'); hint.type = 'button';
    const hintText = make('p', 'world3d-hint-text'); hintText.hidden = true;
    hintText.setAttribute('role', 'status'); hintText.setAttribute('aria-live', 'polite');
    const feedback = make('p', 'world3d-feedback'); feedback.setAttribute('role', 'status'); feedback.setAttribute('aria-live', 'polite');
    challenge.append(challengeLabel, challengeTitle, teaching, passage, prompt, answers, hint, hintText, feedback);
    const status = make('p', 'world3d-status', 'Explore the city or choose a destination below.');
    status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    const wayfinding = make('p', 'world3d-wayfinding', 'Follow your casebook to find the next location.');
    wayfinding.setAttribute('aria-live', 'polite');
    const controls = make('div', 'world3d-controls');
    const moveGroup = make('div', 'world3d-movement');
    moveGroup.setAttribute('aria-label', 'Move through the city');
    moveGroup.append(make('span', 'world3d-control-label', 'Move'));
    for (const [label, symbol, dx, dz] of [['Forward','↑',0,-1],['Left','←',-1,0],['Back','↓',0,1],['Right','→',1,0]]) {
      const b = make('button', 'world3d-direction', symbol);
      b.type = 'button'; b.setAttribute('aria-label', 'Move ' + label.toLowerCase());
      b.addEventListener('pointerdown', event => {
        if (event && (event.isPrimary === false || (typeof event.button === 'number' && event.button !== 0))) return;
        beginHeldMovement(b, dx, dz);
      });
      for (const eventName of ['pointerup', 'pointercancel', 'pointerleave', 'blur']) b.addEventListener(eventName, stopHeldMovement);
      b.addEventListener('click', event => {
        // A long pointer press has already moved. Keyboard activation has
        // detail zero and must remain a single independent move.
        if (event?.detail !== 0 && b.suppressPointerClick) { b.suppressPointerClick = false; return; }
        if (active && !destroyed && canRender()) engine.move(dx,dz);
      });
      movementButtons.push(b); moveGroup.append(b);
    }
    const interact = make('button', 'world3d-interact', 'Explore nearby');
    interact.type = 'button';
    interact.addEventListener('click', () => {
      if (!active || destroyed || !canRender()) return;
      if (!nearby) { status.textContent = 'Move closer to a destination or choose one below.'; return; }
      engine.interact();
    });
    movementButtons.push(interact);
    controls.append(moveGroup, interact);
    function allowed(id) { return allowedDestinations === null || allowedDestinations.includes(id); }
    // Only a deliberate location visit may move keyboard focus into a newly
    // opened challenge. Restoration, account changes and background refreshes
    // must never unexpectedly move focus. Keep the intent until a returned
    // Promise settles so future server-backed visits behave the same way.
    function visitFromUI(id) {
      const generation = ++visitGeneration;
      pendingChallengeFocus = generation;
      const clearIntent = () => { if (pendingChallengeFocus === generation) pendingChallengeFocus = null; };
      try {
        const result = navigate(id);
        if (result && typeof result.then === 'function') result.then(clearIntent, clearIntent);
        else clearIntent();
      } catch (_) { clearIntent(); }
    }
    // The map and text alternatives must share the same locked-location and
    // authentication path; the map never grants access or starts a lesson.
    function visitDestination(place) {
      if (!active || destroyed || !allowed(place.id)) return;
      if (canRender()) engine.goTo(place.id);
      else visitFromUI(place.id);
    }
    const directLabel = make('p', 'world3d-control-label', 'Or choose a destination');
    const destinations = make('div', 'world3d-destinations');
    destinations.setAttribute('aria-label', 'Choose a destination');
    for (const place of PLACES) {
      const b = make('button', 'world3d-destination', place.label);
      b.type = 'button';
      b.destinationId = place.id;
      b.addEventListener('click', () => visitDestination(place));
      destinationButtons.push(b); destinations.append(b);
    }
    const map = make('section', 'world3d-map'); map.hidden = true;
    map.setAttribute('aria-labelledby', 'world3d-map-title');
    const mapTitle = make('h3', 'world3d-map-title', 'Case map'); mapTitle.id = 'world3d-map-title';
    const mapArea = make('div', 'world3d-map-area');
    mapArea.setAttribute('role', 'group'); mapArea.setAttribute('aria-label', 'Case map locations');
    const mapPlayer = make('span', 'world3d-map-player', 'You'); mapPlayer.setAttribute('aria-hidden', 'true');
    const symbols = {voice:'P', activities:'A', signin:'B'};
    for (const place of PLACES) {
      const marker = make('button', 'world3d-map-location', symbols[place.id]);
      marker.type = 'button'; marker.destinationId = place.id;
      marker.setAttribute('aria-label', 'Visit ' + place.label + ' on the case map');
      marker.setAttribute('data-place', place.id);
      marker.addEventListener('click', () => visitDestination(place));
      mapButtons.push(marker); mapArea.append(marker);
    }
    mapArea.append(mapPlayer);
    map.append(mapTitle, mapArea, make('p', 'world3d-map-legend', 'P: Post Office · A: City Archive · B: Bookshop'));
    function updateMap() {
      if (destroyed || !active || !canRender() || typeof engine?.getState !== 'function' || typeof engine?.getLandmarks !== 'function') {
        map.hidden = true; return;
      }
      let position, landmarks;
      try { position = engine.getState(); landmarks = engine.getLandmarks(); } catch (_) { map.hidden = true; return; }
      if (!Number.isFinite(position?.x) || !Number.isFinite(position?.z) || !Array.isArray(landmarks)) { map.hidden = true; return; }
      const byPlace = new Map(landmarks.filter(p => p && byId(p.id) && Number.isFinite(p.x) && Number.isFinite(p.z)).map(p => [p.id, p]));
      if (byPlace.size !== PLACES.length) { map.hidden = true; return; }
      // The procedural world bounds are -17 to 17 in both axes. Clamp
      // markers within the panel; their status is never a saved location.
      const percent = value => (100 * Math.max(.16, Math.min(.84, (value + 17) / 34))) + '%';
      for (const marker of mapButtons) {
        const point = byPlace.get(marker.destinationId);
        marker.style.left = percent(point.x); marker.style.top = percent(point.z);
      }
      mapPlayer.style.left = percent(position.x); mapPlayer.style.top = percent(position.z);
      map.hidden = false;
    }
    const instructions = make('p', 'world3d-instructions', 'Click the world and use arrow keys or W A S D to move. Press Enter near a destination. Touch or click the controls below, or choose a destination directly.');
    const legend = make('p', 'world3d-legend', 'Orange: Bookshop. Blue: City Archive. Pink: Post Office.');
    section.append(header, gameArea, map, quest, guide, challenge, status, wayfinding, instructions, legend, controls, directLabel, destinations);
    root.replaceChildren(section);
    function updateWayfinding() {
      if (destroyed) return;
      let text = 'Follow your casebook to find the next location.';
      const id = Array.isArray(allowedDestinations) && allowedDestinations.length === 1 ? allowedDestinations[0] : null;
      const place = byId(id);
      if (place) {
        text = 'Next location: ' + place.label + '. Choose its destination button below.';
        if (canRender() && typeof engine?.getLandmarks === 'function' && typeof engine?.getState === 'function') {
          const landmark = engine.getLandmarks().find(item => item.id === id);
          const position = engine.getState();
          if (landmark && Number.isFinite(position?.x) && Number.isFinite(position?.z)
              && Number.isFinite(landmark.x) && Number.isFinite(landmark.z)) {
            const dx = landmark.x - position.x, dz = landmark.z - position.z;
            if (Math.hypot(dx, dz) <= 2.7) text = 'You are near ' + place.label + '. Choose Explore nearby.';
            else {
              const direction = Math.abs(dx) > Math.abs(dz) ? (dx < 0 ? 'left' : 'right') : (dz < 0 ? 'forward' : 'back');
              text = 'Next location: ' + place.label + '. Move ' + direction + ', or choose its destination button below.';
            }
          }
        }
      }
      if (wayfinding.textContent !== text) wayfinding.textContent = text;
    }
    function setControls() {
      for (const b of movementButtons) b.disabled = !active || !canRender();
      for (const b of destinationButtons) b.disabled = !active || !allowed(b.destinationId);
      for (const b of mapButtons) b.disabled = !active || !canRender() || !allowed(b.destinationId);
      guideNext.disabled = !active; guideControls.disabled = !active;
      exit.disabled = !active;
      restart.disabled = !active || restart.hidden || restartPending;
      hint.disabled = !active || !challengeId || hintUsed || hintPending || answerPending;
      for (const button of answers.children) button.disabled = !active || hintPending || answerPending;
    }
    restart.addEventListener('click', async () => {
      if (!active || destroyed || restart.hidden || restartPending) return;
      const generation = ++restartGeneration;
      restartPending = true; setControls();
      status.textContent = 'Starting the case again…';
      try {
        const confirmed = await onRestart();
        if (destroyed || !active || generation !== restartGeneration) return;
        // The backend callback must have applied its confirmed snapshot. Do
        // not clear clues or change phase in anticipation of a server result.
        if (confirmed === true && restart.hidden) { status.textContent = 'Case restarted.'; questTitle.focus?.(); }
        else status.textContent = 'The case could not be restarted. Please try again.';
      } catch (_) {
        if (!destroyed && active && generation === restartGeneration)
          status.textContent = 'The case could not be restarted. Please try again.';
      } finally {
        if (!destroyed && generation === restartGeneration) { restartPending = false; setControls(); }
      }
    });
    hint.addEventListener('click', async () => {
      if (!active || destroyed || !challengeId || hintUsed || hintPending || answerPending) return;
      const id = challengeId, generation = challengeGeneration;
      hintPending = true; setControls();
      try {
        await onHint(id);
        // A successful callback is not enough: only an authoritative matching
        // snapshot may reveal the hint and mark assistance as used.
        if (!destroyed && active && generation === challengeGeneration && challengeId === id && !hintUsed)
          feedback.textContent = 'The hint is unavailable. Please try again.';
      } catch (_) {
        if (!destroyed && active && generation === challengeGeneration && challengeId === id)
          feedback.textContent = 'The hint is unavailable. Please try again.';
      } finally {
        if (generation === challengeGeneration) { hintPending = false; setControls(); }
      }
    });
    function renderChallenge(id) {
      if (id === challengeId) {
        if (id && pendingChallengeFocus && active && !challenge.hidden) {
          pendingChallengeFocus = null;
          challengeTitle.focus?.();
        }
        return;
      }
      challengeGeneration++;
      challengeId = null; hintUsed = false; hintPending = false; answerPending = false;
      answers.replaceChildren(); hintText.textContent = ''; hintText.hidden = true;
      hint.disabled = false; feedback.textContent = ''; challenge.hidden = true;
      if (typeof id !== 'string' || typeof global.LivingInvestigationReading?.get !== 'function') return;
      let data;
      try { data = global.LivingInvestigationReading.get(id); } catch (_) { return; }
      if (!data || data.id !== id || data.review_status !== 'unreviewed' || data.audience !== 'synthetic_adult_demo'
          || !Array.isArray(data.options) || data.options.length === 0
          || !['title', 'teaching', 'passage', 'prompt', 'hint'].every(key => typeof data[key] === 'string')) return;
      challengeId = id;
      challengeTitle.textContent = data.title;
      teaching.textContent = data.teaching;
      passage.textContent = data.passage;
      prompt.textContent = data.prompt;
      hintText.textContent = data.hint;
      for (const choice of data.options) {
        if (!choice || typeof choice.id !== 'string' || typeof choice.label !== 'string') continue;
        const button = make('button', 'world3d-answer', choice.label);
        button.type = 'button';
        button.addEventListener('click', async () => {
          if (!active || destroyed || answerPending || hintPending || challengeId !== id) return;
          const generation = challengeGeneration;
          answerPending = true; setControls();
          try {
            const result = await onAnswer(id, choice.id, hintUsed);
            if (destroyed || generation !== challengeGeneration) return;
            if (typeof result?.feedback === 'string') feedback.textContent = result.feedback;
          } catch (_) {
            if (!destroyed && generation === challengeGeneration) feedback.textContent = 'This challenge is unavailable. Please try again.';
          } finally {
            if (generation === challengeGeneration) { answerPending = false; setControls(); }
          }
        });
        answers.append(button);
      }
      if (answers.children.length) {
        challenge.hidden = false;
        if (pendingChallengeFocus && active) {
          pendingChallengeFocus = null;
          challengeTitle.focus?.();
        }
      }
    }
    function markUnavailable() {
      if (destroyed || graphicsFailed) return;
      graphicsFailed = true;
      signs?.hide();
      map.hidden = true;
      nearby = null;
      stopHeldMovement();
      canvas.hidden = true;
      gameArea.hidden = true;
      status.textContent = 'The 3D view is unavailable in this browser. You can still choose a destination below.';
      instructions.textContent = 'Choose a destination to continue.';
      setControls();
      updateWayfinding();
    }
    try {
      if (typeof global.LivingWorld3D?.mount === 'function') {
        engine = global.LivingWorld3D.mount(canvas, {
          onNearby(id) {
            if (destroyed || graphicsFailed) return;
            nearby = byId(id) || null;
            status.textContent = nearby ? 'Near ' + nearby.label + (allowed(nearby.id) ? '. Choose Explore nearby to visit.' : '. This location is not open yet.') : 'Explore the city or choose a destination below.';
          },
          onVisit(id) {
            if (!active || destroyed || graphicsFailed || !byId(id)) return;
            if (!allowed(id)) { status.textContent = byId(id).label + ' is not open yet. Follow the casebook to the next location.'; return; }
            visitFromUI(id);
          },
          onUnavailable: markUnavailable,
          onViewChange() {
            if (!destroyed && active) { signs?.update(); updateMap(); updateWayfinding(); }
          }
        });
      }
    } catch (_) { engine = null; }
    if (!canRender()) markUnavailable();
    else if (typeof global.LivingWorldSigns?.mount === 'function') {
      try { signs = global.LivingWorldSigns.mount(gameArea, engine); signs.update(); }
      catch (_) { signs = null; }
    }
    updateMap(); setControls();
    return Object.freeze({
      get available() { return canRender(); },
      updateQuest(snapshot) {
        if (destroyed || !snapshot || typeof snapshot !== 'object') return;
        const previousGuideKey = [guidePhase, guideChallenge, guideDestination].join('|');
        guidePhase = ['exploring', 'activity_requested', 'activity_started', 'activity_completed', 'returned', 'case_solved'].includes(snapshot.phase) ? snapshot.phase : 'exploring';
        restart.hidden = guidePhase !== 'case_solved';
        guideChallenge = ['decode', 'context', 'sequence'].includes(snapshot.challengeId) ? snapshot.challengeId : null;
        const nextPlace = Array.isArray(snapshot.allowedDestinations) && snapshot.allowedDestinations.length === 1 ? byId(snapshot.allowedDestinations[0]) : null;
        guideDestination = nextPlace ? nextPlace.label : null;
        if ([guidePhase, guideChallenge, guideDestination].join('|') !== previousGuideKey)
          guideReply.textContent = 'I can help you find your way through the case.';
        if (typeof snapshot.caseTitle === 'string' && snapshot.caseTitle.length <= 120) title.textContent = snapshot.caseTitle;
        if (typeof snapshot.message === 'string' && snapshot.message.length <= 300) questMessage.textContent = snapshot.message;
        if (Array.isArray(snapshot.visited)) {
          const names = PLACES.filter(p => snapshot.visited.includes(p.id)).map(p => p.label);
          visited.textContent = 'Places visited: ' + (names.length ? names.join(', ') : 'none yet') + '.';
        }
        if (Array.isArray(snapshot.allowedDestinations)) {
          allowedDestinations = snapshot.allowedDestinations.filter(id => typeof id === 'string' && byId(id));
        } else allowedDestinations = null;
        setControls();
        updateWayfinding();
        if (nearby && canRender()) status.textContent = 'Near ' + nearby.label + (allowed(nearby.id) ? '. Choose Explore nearby to visit.' : '. This location is not open yet.');
        if (Array.isArray(snapshot.clues)) {
          clues.replaceChildren();
          const valid = snapshot.clues.slice(0, 12).filter(clue => clue && typeof clue.title === 'string' && clue.title.length <= 120 && typeof clue.text === 'string' && clue.text.length <= 500);
          if (!valid.length) clues.append(make('li', 'world3d-clue-empty', 'No clues collected yet.'));
          for (const clue of valid) {
            const entry = make('li', 'world3d-clue');
            entry.append(make('strong', '', clue.title));
            if (clue.usedHint === true) entry.append(make('span', 'world3d-clue-hint', 'Hint used'));
            entry.append(make('p', '', clue.text));
            clues.append(entry);
          }
        }
        const finishedByAnswer = answerPending && challengeId && snapshot.challengeId === null
          && Array.isArray(snapshot.clues) && snapshot.clues.some(clue => clue?.id === 'clue-' + challengeId);
        renderChallenge(snapshot.challengeId);
        // Hint visibility and its assistance flag are restored only from the
        // persisted state for this exact active challenge.
        if (challengeId && snapshot.challengeId === challengeId) {
          hintUsed = snapshot.pendingHint === true;
          hintText.hidden = !hintUsed;
          setControls();
        }
        if (finishedByAnswer && active) questTitle.focus?.();
        if (typeof snapshot.feedback === 'string' && snapshot.feedback.length <= 500) feedback.textContent = snapshot.feedback;
      },
      pause() { if (destroyed) return; active = false; restartGeneration++; restartPending = false; visitGeneration++; pendingChallengeFocus = null; stopHeldMovement(); signs?.hide(); engine?.pause(); updateMap(); setControls(); },
      resume() { if (destroyed) return; active = true; engine?.resume(); signs?.update(); updateMap(); updateWayfinding(); setControls(); },
      reset() { if (destroyed) return; restartGeneration++; restartPending = false; visitGeneration++; pendingChallengeFocus = null; stopHeldMovement(); nearby = null; engine?.reset(); signs?.update(); updateMap(); updateWayfinding(); setControls(); status.textContent = canRender() ? 'Explore the city or choose a destination below.' : 'The 3D view is unavailable in this browser. You can still choose a destination below.'; },
      destroy() { if (destroyed) return; destroyed = true; active = false; restartGeneration++; restartPending = false; visitGeneration++; pendingChallengeFocus = null; stopHeldMovement(); signs?.destroy(); engine?.destroy(); root.replaceChildren(); }
    });
  }
  global.LivingWorld3DUI = Object.freeze({mount});
})(window);
