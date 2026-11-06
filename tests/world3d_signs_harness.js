'use strict';
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.style = {}; this.attrs = {}; this.hidden = false; this.offsetWidth = 110; this.offsetHeight = 30; }
  append(child) { child.parent = this; this.children.push(child); }
  setAttribute(name, value) { this.attrs[name] = String(value); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(x => x !== this); }
  getBoundingClientRect() { return {width: 500, height: 300}; }
}
const document = {createElement: tag => new Element(tag)};
const window = {};
vm.runInNewContext(fs.readFileSync('prototype/web/world3d-signs.js', 'utf8'), {window, document, Object, Number, Math, TypeError, Map});
const stage = new Element('div');
const locations = [
  {id:'voice', x:1, y:4, z:1},
  {id:'activities', x:2, y:4, z:2},
  {id:'signin', x:3, y:4, z:3}
];
let projection = point => ({x:point/4, y:.5, visible:true});
const engine = {available:true, getLandmarks:()=>locations, project:(x,y,z)=>projection(x,y,z)};
const controller = window.LivingWorldSigns.mount(stage, engine);
assert.equal(stage.children.length, 1);
const layer = stage.children[0];
assert.equal(layer.attrs['aria-hidden'], 'true');
const signs = layer.children;
assert.deepEqual(signs.map(x => x.textContent), ['Post Office', 'City Archive', 'Bookshop']);
assert(signs.every(x => !x.hidden));
assert(signs.every(x => Number.isFinite(parseFloat(x.style.left)) && Number.isFinite(parseFloat(x.style.top))));

// Overlapping projections are stacked without masking one another.
projection = () => ({x:.5, y:.3, visible:true});
controller.update();
assert(signs.every(x => !x.hidden));
assert.equal(new Set(signs.map(x=>x.style.top)).size, 3);
// Behind-camera, offscreen and malformed positions cannot create bad CSS.
projection = x => x === 1 ? {x:.2,y:.2,visible:false} : x === 2 ? {x:1.1,y:.3,visible:true} : {x:NaN,y:.5,visible:true};
controller.update();
assert(signs.every(x => x.hidden));
engine.available = false;
projection = () => ({x:.5,y:.5,visible:true});
controller.update();
assert(signs.every(x => x.hidden));
engine.available = true;
controller.update();
assert(signs.every(x => !x.hidden));
controller.hide();
assert(signs.every(x => x.hidden));
controller.destroy(); controller.destroy(); controller.update();
assert.equal(stage.children.length, 0);
assert.throws(() => window.LivingWorldSigns.mount(null, engine), TypeError);
console.log('3D landmark labels passed');
