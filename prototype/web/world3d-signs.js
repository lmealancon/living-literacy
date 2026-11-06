'use strict';

// Labels are visual wayfinding only. Existing destination buttons and the
// casebook provide the same names without relying on WebGL or a visual overlay.
(function (global) {
  const NAMES = Object.freeze({voice: 'Post Office', activities: 'City Archive', signin: 'Bookshop'});
  const ORDER = Object.freeze(['voice', 'activities', 'signin']);
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  function mount(stage, engine) {
    if (!stage || typeof stage.append !== 'function') throw new TypeError('A game stage is required.');
    const layer = document.createElement('div');
    layer.className = 'world3d-sign-layer';
    layer.setAttribute('aria-hidden', 'true');
    const labels = new Map();
    for (const id of ORDER) {
      const label = document.createElement('span');
      label.className = 'world3d-sign';
      label.textContent = NAMES[id];
      label.hidden = true;
      label.setAttribute('data-landmark', id);
      layer.append(label);
      labels.set(id, label);
    }
    stage.append(layer);
    let destroyed = false;

    function hide() {
      for (const label of labels.values()) label.hidden = true;
    }

    function update() {
      if (destroyed) return;
      hide();
      if (!engine || !engine.available || typeof engine.project !== 'function'
          || typeof engine.getLandmarks !== 'function') return;
      const rect = stage.getBoundingClientRect();
      const width = rect.width, height = rect.height;
      if (!(width > 0 && height > 0)) return;
      let points;
      try { points = engine.getLandmarks(); } catch (_) { return; }
      if (!Array.isArray(points)) return;
      const byId = new Map(points.filter(p => p && Object.hasOwn(NAMES, p.id)).map(p => [p.id, p]));
      const candidates = [];
      for (const id of ORDER) {
        const point = byId.get(id), label = labels.get(id);
        if (!point || ![point.x, point.y, point.z].every(Number.isFinite)) continue;
        let screen;
        try { screen = engine.project(point.x, point.y, point.z); } catch (_) { continue; }
        if (!screen || screen.visible !== true || !Number.isFinite(screen.x) || !Number.isFinite(screen.y)
            || screen.x < 0 || screen.x > 1 || screen.y < 0 || screen.y > 1) continue;
        label.hidden = false;
        candidates.push({id, label, screen});
      }
      // Batch the measurements before the positioning writes, so a movement
      // redraw does not force a fresh layout for every individual label.
      const measured = candidates.map(({id, label, screen}) => ({label, screen,
        w: Math.min(width, label.offsetWidth || (NAMES[id].length * 8 + 24)),
        h: Math.min(height, label.offsetHeight || 30)}));
      const placed = [], positions = [];
      for (const {label, screen, w:badgeWidth, h:badgeHeight} of measured) {
        // Stagger overlaps. If the viewport is too small, leave the later
        // badge hidden; its accessible destination button remains available.
        const centerX = clamp(screen.x * width, badgeWidth / 2, width - badgeWidth / 2);
        let bottom = clamp(screen.y * height, badgeHeight, height);
        const overlaps = candidate => placed.some(p =>
          Math.abs(centerX - p.x) < (badgeWidth + p.w) / 2 + 5
          && candidate > p.bottom - p.h - 5 && candidate - badgeHeight < p.bottom + 5);
        while (bottom <= height && overlaps(bottom)) bottom += badgeHeight + 6;
        if (bottom > height) { positions.push({label, hidden:true}); continue; }
        positions.push({label, hidden:false, left:(100 * centerX / width) + '%', top:(100 * bottom / height) + '%'});
        placed.push({x:centerX, bottom, w:badgeWidth, h:badgeHeight});
      }
      for (const position of positions) {
        if (position.hidden) position.label.hidden = true;
        else { position.label.style.left = position.left; position.label.style.top = position.top; }
      }
    }
    function destroy() {
      if (destroyed) return;
      destroyed = true; hide(); layer.remove();
    }
    update();
    return Object.freeze({update, hide, destroy});
  }
  global.LivingWorldSigns = Object.freeze({mount});
})(window);
