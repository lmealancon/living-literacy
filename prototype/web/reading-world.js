'use strict';

// A fictional, client-side exploration scene. It never opens a lesson itself,
// stores learner data, or makes an authorization decision.
(function (global) {
  const WIDTH = 960, HEIGHT = 540, STEP = 0.075, REACH = 0.17;
  const DESTINATIONS = Object.freeze([
    Object.freeze({id:'signin', name:'Bookshop', x:0.18, y:0.61, icon:'✦', color:'#f4aa55'}),
    Object.freeze({id:'activities', name:'Archive', x:0.48, y:0.36, icon:'▤', color:'#5e92df'}),
    Object.freeze({id:'voice', name:'Post Office', x:0.81, y:0.53, icon:'♥', color:'#ed8091'})
  ]);
  const clamp = value => Math.max(0.055, Math.min(0.945, value));
  const node = (tag, className, text) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  };

  function mount(root, options = {}) {
    if (!root || typeof root.replaceChildren !== 'function') throw new TypeError('A world container is required.');
    const navigate = typeof options.navigate === 'function' ? options.navigate : () => {};
    let x = 0.49, y = 0.78, active = true, destroyed = false, background = null;
    const buttons = [];
    const section = node('section', 'reading-world');
    section.setAttribute('aria-labelledby', 'reading-world-title');
    const intro = node('div', 'reading-world-intro');
    const eyebrow = node('p', 'reading-world-eyebrow', 'Your world to explore');
    const heading = node('h2', 'reading-world-heading', 'Explore Victorian London');
    heading.id = 'reading-world-title';
    const description = node('p', 'reading-world-description', 'Move through the fictional city to investigate. You can also choose a location directly below.');
    intro.append(eyebrow, heading, description);
    const frame = node('div', 'reading-world-frame');
    const canvas = node('canvas', 'reading-world-canvas');
    canvas.width = WIDTH; canvas.height = HEIGHT; canvas.tabIndex = 0;
    canvas.setAttribute('aria-label', 'Fictional London map. While focused, use arrow keys or W A S D to move. Press Enter near a destination to visit it.');
    const canvasFallback = node('p', '', 'The city map is unavailable. Use the destination buttons below.');
    canvas.append(canvasFallback);
    frame.append(canvas);
    const status = node('p', 'reading-world-status', 'Choose a direction to begin exploring.');
    status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    const controls = node('div', 'reading-world-controls');
    const directions = node('div', 'reading-world-directions');
    directions.setAttribute('aria-label', 'Move the companion');
    const directionsLabel = node('span', 'reading-world-control-label', 'Move');
    directions.append(directionsLabel);
    const moves = [['Up','↑',0,-1],['Left','←',-1,0],['Down','↓',0,1],['Right','→',1,0]];
    for (const [label, symbol, dx, dy] of moves) {
      const button = node('button', 'reading-world-direction', symbol);
      button.type = 'button'; button.setAttribute('aria-label', 'Move ' + label.toLowerCase());
      button.addEventListener('click', () => move(dx,dy));
      buttons.push(button); directions.append(button);
    }
    const explore = node('button', 'reading-world-explore', 'Explore nearby');
    explore.type = 'button'; explore.addEventListener('click', visitNearby);
    buttons.push(explore); controls.append(directions, explore);
    const destinationList = node('div', 'reading-world-destinations');
    destinationList.setAttribute('aria-label', 'Choose a destination');
    for (const destination of DESTINATIONS) {
      const button = node('button', 'reading-world-destination', destination.name);
      button.type = 'button';
      button.addEventListener('click', () => visit(destination));
      buttons.push(button); destinationList.append(button);
    }
    section.append(intro, frame, status, controls, destinationList);
    root.replaceChildren(section);
    let ctx = null;
    try { ctx = typeof canvas.getContext === 'function' ? canvas.getContext('2d') : null; } catch (_) { /* Text controls still work. */ }
    if (!ctx) {
      canvas.hidden = true;
      status.textContent = 'The visual map is unavailable. Choose a destination below.';
    }

    function nearest() {
      let result = null, distance = Infinity;
      for (const destination of DESTINATIONS) {
        const candidate = Math.hypot(x - destination.x, (y - destination.y) * HEIGHT / WIDTH);
        if (candidate < distance) { distance = candidate; result = destination; }
      }
      return distance <= REACH ? result : null;
    }
    function announce() {
      const nearby = nearest();
      status.textContent = nearby
        ? 'Near ' + nearby.name + '. Choose Explore nearby to visit.'
        : 'Keep exploring, or choose a destination below.';
    }
    function roundedRect(x0, y0, width, height, radius) {
      ctx.beginPath();
      ctx.moveTo(x0 + radius, y0);
      ctx.arcTo(x0 + width, y0, x0 + width, y0 + height, radius);
      ctx.arcTo(x0 + width, y0 + height, x0, y0 + height, radius);
      ctx.arcTo(x0, y0 + height, x0, y0, radius);
      ctx.arcTo(x0, y0, x0 + width, y0, radius);
      ctx.closePath();
    }
    function paint() {
      if (!ctx || destroyed) return;
      ctx.clearRect(0,0,WIDTH,HEIGHT);
      if (background) {
        const scale = Math.max(WIDTH / background.width, HEIGHT / background.height);
        const w = background.width * scale, h = background.height * scale;
        ctx.drawImage(background, (WIDTH-w)/2, (HEIGHT-h)/2, w, h);
      } else {
        const sky = ctx.createLinearGradient(0,0,0,HEIGHT);
        sky.addColorStop(0,'#c9eaff'); sky.addColorStop(.6,'#edf7d0'); sky.addColorStop(1,'#b5dfa4');
        ctx.fillStyle = sky; ctx.fillRect(0,0,WIDTH,HEIGHT);
      }
      // A gently curved trail links real application destinations; it does not
      // imply the existence of extra activities or lesson content.
      ctx.save(); ctx.strokeStyle = 'rgba(255,248,210,.72)'; ctx.lineWidth = 30;
      ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.setLineDash([7,18]);
      ctx.beginPath(); ctx.moveTo(DESTINATIONS[0].x*WIDTH, DESTINATIONS[0].y*HEIGHT);
      ctx.quadraticCurveTo(WIDTH*.32,HEIGHT*.27,WIDTH*.48,HEIGHT*.36);
      ctx.quadraticCurveTo(WIDTH*.67,HEIGHT*.26,WIDTH*.81,HEIGHT*.53); ctx.stroke(); ctx.restore();
      for (const destination of DESTINATIONS) {
        const px = destination.x*WIDTH, py = destination.y*HEIGHT;
        ctx.save(); ctx.shadowColor = 'rgba(28,49,70,.3)'; ctx.shadowBlur = 12; ctx.shadowOffsetY = 4;
        ctx.fillStyle = '#fffdf8'; roundedRect(px-74,py-31,148,62,18); ctx.fill(); ctx.restore();
        ctx.fillStyle = destination.color; ctx.beginPath(); ctx.arc(px-49,py,17,0,Math.PI*2); ctx.fill();
        ctx.fillStyle = '#fff'; ctx.font = 'bold 19px system-ui,sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(destination.icon,px-49,py+1);
        ctx.fillStyle = '#193858'; ctx.font = 'bold 15px system-ui,sans-serif'; ctx.textAlign = 'left'; ctx.fillText(destination.name,px-25,py,100);
      }
      const px = x*WIDTH, py = y*HEIGHT;
      ctx.save(); ctx.translate(px,py);
      ctx.fillStyle = 'rgba(25,60,50,.24)'; ctx.beginPath(); ctx.ellipse(0,34,33,9,0,0,Math.PI*2); ctx.fill();
      ctx.strokeStyle = '#176c61'; ctx.lineWidth = 9; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(-20,1); ctx.lineTo(-33,-8); ctx.moveTo(20,1); ctx.lineTo(33,-8); ctx.moveTo(-12,24); ctx.lineTo(-17,34); ctx.moveTo(12,24); ctx.lineTo(17,34); ctx.stroke();
      ctx.fillStyle = '#f7bf4c'; ctx.strokeStyle = '#a36020'; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.moveTo(0,-39); ctx.bezierCurveTo(32,-26,32,2,24,20); ctx.bezierCurveTo(16,39,-16,39,-24,20); ctx.bezierCurveTo(-32,2,-32,-26,0,-39); ctx.fill(); ctx.stroke();
      ctx.fillStyle = '#51a46f'; ctx.beginPath(); ctx.moveTo(0,-38); ctx.quadraticCurveTo(0,-56,17,-55); ctx.quadraticCurveTo(15,-42,0,-38); ctx.fill();
      ctx.fillStyle = '#243c37'; ctx.beginPath(); ctx.arc(-9,-5,3.5,0,Math.PI*2); ctx.arc(9,-5,3.5,0,Math.PI*2); ctx.fill();
      ctx.strokeStyle = '#704329'; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(0,2,7,0.2,Math.PI-.2); ctx.stroke();
      ctx.restore();
    }
    function move(dx, dy) {
      if (!active || destroyed) return;
      x = clamp(x + dx*STEP); y = Math.max(.12, Math.min(.91, y + dy*STEP));
      paint(); announce();
    }
    function visit(destination) {
      if (!active || destroyed) return;
      x = destination.x; y = destination.y; paint();
      const accepted = navigate(destination.id);
      status.textContent = accepted === false
        ? 'That location is locked. Follow the current clue or sign in.'
        : 'Visiting ' + destination.name + '.';
    }
    function visitNearby() {
      if (!active || destroyed) return;
      const destination = nearest();
      if (destination) visit(destination);
      else status.textContent = 'Move closer to a destination or choose one below.';
    }
    canvas.addEventListener('keydown', event => {
      if (!active || destroyed) return;
      const keys = {ArrowUp:[0,-1], ArrowDown:[0,1], ArrowLeft:[-1,0], ArrowRight:[1,0], w:[0,-1], s:[0,1], a:[-1,0], d:[1,0]};
      const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
      if (Object.hasOwn(keys, key)) { event.preventDefault(); move(...keys[key]); }
      else if (key === 'Enter' || key === ' ') { event.preventDefault(); visitNearby(); }
    });
    // Pointer users can choose a destination on the map. The destination
    // buttons provide the same operation without requiring precise pointing.
    canvas.addEventListener('click', event => {
      if (!active || destroyed) return;
      const box = canvas.getBoundingClientRect();
      if (!box.width || !box.height) return;
      const px = (event.clientX-box.left)/box.width, py = (event.clientY-box.top)/box.height;
      const selected = DESTINATIONS.find(d => Math.abs(px-d.x) <= 0.085 && Math.abs(py-d.y) <= 0.075);
      if (selected) visit(selected);
    });
    if (ctx && typeof global.Image === 'function') {
      const image = new global.Image();
      image.onload = () => { if (!destroyed && image.width && image.height) { background = image; paint(); } };
      image.src = '/hero-world.png';
    }
    paint();
    return {
      pause() { active = false; for (const button of buttons) button.disabled = true; },
      resume() { if (!destroyed) { active = true; for (const button of buttons) button.disabled = false; paint(); } },
      reset() { if (!destroyed) { x=.49; y=.78; paint(); status.textContent='Choose a direction to begin exploring.'; } },
      destroy() { active = false; destroyed = true; root.replaceChildren(); }
    };
  }
  global.LivingReadingWorld = Object.freeze({mount});
})(window);
