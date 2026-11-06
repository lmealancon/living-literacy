'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup(withCanvas = true) {
  const gradient = {addColorStop(){}};
  const context = new Proxy({createLinearGradient:() => gradient}, {
    get(target, key) { return key in target ? target[key] : () => {}; },
    set(target, key, value) { target[key] = value; return true; }
  });
  class Element {
    constructor(tag) { this.tagName=tag; this.children=[]; this.events={}; this.attributes={}; this.textContent=''; this.disabled=false; this.hidden=false; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children=children; }
    setAttribute(name,value) { this.attributes[name]=value; }
    addEventListener(name,callback) { this.events[name]=callback; }
    getContext() { return withCanvas ? context : null; }
    getBoundingClientRect() { return {left:0,top:0,width:960,height:540}; }
    descendants() { return [this,...this.children.flatMap(child=>child.descendants())]; }
  }
  const root=new Element('div');
  const document={createElement: tag=>new Element(tag)};
  const window={};
  vm.runInNewContext(fs.readFileSync('prototype/web/reading-world.js','utf8'), {window,document,Math,Object,TypeError});
  const visits=[];
  const controller=window.LivingReadingWorld.mount(root,{navigate:id=>visits.push(id)});
  const find=predicate=>root.descendants().find(predicate);
  return {root,controller,visits,find};
}

{
  const h=setup();
  const canvas=h.find(el=>el.tagName==='canvas');
  assert.equal(canvas.tabIndex,0);
  assert.match(canvas.attributes['aria-label'],/arrow keys/i);
  const key=key=>{let prevented=false; canvas.events.keydown({key,preventDefault(){prevented=true;}}); return prevented;};
  assert.equal(key('x'),false,'unrelated keys remain available');
  for(let i=0;i<4;i++) assert.equal(key('ArrowUp'),true);
  assert.equal(key('Enter'),true);
  assert.deepEqual(h.visits,['activities'],'walking near the grove and Enter visits the actual activity destination');
  h.find(el=>el.textContent==='Bookshop').events.click();
  h.find(el=>el.textContent==='Post Office').events.click();
  assert.deepEqual(h.visits,['activities','signin','voice']);
  h.controller.pause();
  h.find(el=>el.textContent==='Bookshop').events.click();
  assert.equal(h.visits.length,3,'paused scene does not navigate');
  h.controller.resume();
  h.controller.reset();
  h.find(el=>el.textContent==='Bookshop').events.click();
  assert.equal(h.visits.at(-1),'signin');
  h.controller.destroy();
  assert.equal(h.root.children.length,0);
}
{
  const h=setup(false);
  assert(h.find(el=>el.tagName==='canvas').hidden,'failed canvas hides the map');
  assert.match(h.find(el=>el.attributes.role==='status').textContent,/unavailable/i);
  h.find(el=>el.textContent==='Archive').events.click();
  assert.deepEqual(h.visits,['activities'],'text navigation remains available without a canvas');
}
console.log('Reading Garden interactions passed');
