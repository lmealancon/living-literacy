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
    let active = true, destroyed = false, nearby = null, engine = null, held = null, graphicsFailed = false;
    let allowedDestinations = null, challengeId = null, challengeGeneration = 0, hintUsed = false, answerPending = false;
    const movementButtons = [], destinationButtons = [];
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
    headingGroup.append(title, make('p', 'world3d-subtitle', 'Sign in with a fictional profile, then explore an imagined Victorian London, uncover clues, and use reading to follow the trail. Adult fictional-data demonstration only. Case progress resets on reload or sign-out.'));
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
    const questMessage = make('p', 'world3d-quest-message', 'Explore the city to begin your investigation.');
    questMessage.setAttribute('aria-live', 'polite');
    const visited = make('p', 'world3d-visited', 'Places visited: none yet.');
    const cluesTitle = make('h4', 'world3d-clues-title', 'Clues collected');
    const clues = make('ol', 'world3d-clues');
    clues.setAttribute('aria-label', 'Clues collected');
    const emptyClues = make('li', 'world3d-clue-empty', 'No clues collected yet.');
    clues.append(emptyClues);
    quest.append(questTitle, questMessage, visited, cluesTitle, clues);
    const challenge = make('section', 'world3d-challenge'); challenge.hidden = true;
    challenge.setAttribute('aria-labelledby', 'world3d-challenge-title');
    const challengeLabel = make('p', 'world3d-challenge-label', 'Reading investigation · unreviewed adult demonstration');
    const challengeTitle = make('h3', 'world3d-challenge-title', 'Reading challenge'); challengeTitle.id = 'world3d-challenge-title';
    const teaching = make('p', 'world3d-challenge-teaching');
    const passage = make('blockquote', 'world3d-challenge-passage');
    const prompt = make('p', 'world3d-challenge-prompt');
    const answers = make('div', 'world3d-challenge-answers'); answers.setAttribute('aria-label', 'Choose an answer');
    const hint = make('button', 'world3d-hint', 'Show a hint'); hint.type = 'button';
    const hintText = make('p', 'world3d-hint-text'); hintText.hidden = true;
    const feedback = make('p', 'world3d-feedback'); feedback.setAttribute('role', 'status'); feedback.setAttribute('aria-live', 'polite');
    challenge.append(challengeLabel, challengeTitle, teaching, passage, prompt, answers, hint, hintText, feedback);
    const status = make('p', 'world3d-status', 'Explore the city or choose a destination below.');
    status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
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
    const directLabel = make('p', 'world3d-control-label', 'Or choose a destination');
    const destinations = make('div', 'world3d-destinations');
    destinations.setAttribute('aria-label', 'Choose a destination');
    for (const place of PLACES) {
      const b = make('button', 'world3d-destination', place.label);
      b.type = 'button';
      b.destinationId = place.id;
      b.addEventListener('click', () => {
        if (!active || destroyed || !allowed(place.id)) return;
        // Destination buttons are also a complete, non-3D alternative. goTo
        // invokes onVisit itself, so do not trigger a second interaction.
        if (canRender()) {
          engine.goTo(place.id);
        } else {
          navigate(place.id);
        }
      });
      destinationButtons.push(b); destinations.append(b);
    }
    const instructions = make('p', 'world3d-instructions', 'Click the world and use arrow keys or W A S D to move. Press Enter near a destination. Touch or click the controls below, or choose a destination directly.');
    const legend = make('p', 'world3d-legend', 'Orange: Bookshop. Blue: City Archive. Pink: Post Office.');
    section.append(header, gameArea, quest, challenge, status, instructions, legend, controls, directLabel, destinations);
    root.replaceChildren(section);
    function setControls() {
      for (const b of movementButtons) b.disabled = !active || !canRender();
      for (const b of destinationButtons) b.disabled = !active || !allowed(b.destinationId);
      exit.disabled = !active;
    }
    hint.addEventListener('click', () => {
      if (!active || destroyed || !challengeId) return;
      hintUsed = true;
      hintText.hidden = false;
      hint.disabled = true;
    });
    function renderChallenge(id) {
      if (id === challengeId) return;
      challengeGeneration++;
      challengeId = null; hintUsed = false; answerPending = false;
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
          if (!active || destroyed || answerPending || challengeId !== id) return;
          const generation = challengeGeneration;
          answerPending = true;
          try {
            const result = await onAnswer(id, choice.id, hintUsed);
            if (destroyed || generation !== challengeGeneration) return;
            if (typeof result?.feedback === 'string') feedback.textContent = result.feedback;
          } catch (_) {
            if (!destroyed && generation === challengeGeneration) feedback.textContent = 'This challenge is unavailable. Please try again.';
          } finally {
            if (generation === challengeGeneration) answerPending = false;
          }
        });
        answers.append(button);
      }
      if (answers.children.length) challenge.hidden = false;
    }
    function markUnavailable() {
      if (destroyed || graphicsFailed) return;
      graphicsFailed = true;
      nearby = null;
      stopHeldMovement();
      canvas.hidden = true;
      gameArea.hidden = true;
      status.textContent = 'The 3D view is unavailable in this browser. You can still choose a destination below.';
      instructions.textContent = 'Choose a destination to continue.';
      setControls();
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
            navigate(id);
          },
          onUnavailable: markUnavailable
        });
      }
    } catch (_) { engine = null; }
    if (!canRender()) markUnavailable();
    setControls();
    return Object.freeze({
      get available() { return canRender(); },
      updateQuest(snapshot) {
        if (destroyed || !snapshot || typeof snapshot !== 'object') return;
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
        renderChallenge(snapshot.challengeId);
        if (typeof snapshot.feedback === 'string' && snapshot.feedback.length <= 500) feedback.textContent = snapshot.feedback;
      },
      pause() { if (destroyed) return; active = false; stopHeldMovement(); engine?.pause(); setControls(); },
      resume() { if (destroyed) return; active = true; engine?.resume(); setControls(); },
      reset() { if (destroyed) return; stopHeldMovement(); nearby = null; engine?.reset(); status.textContent = canRender() ? 'Explore the city or choose a destination below.' : 'The 3D view is unavailable in this browser. You can still choose a destination below.'; },
      destroy() { if (destroyed) return; destroyed = true; active = false; stopHeldMovement(); engine?.destroy(); root.replaceChildren(); }
    });
  }
  global.LivingWorld3DUI = Object.freeze({mount});
})(window);
