'use strict';
// Exercise the real projection and label modules together with mocked WebGL.
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

class Element {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.attrs = {}; this.style = {};
    this.hidden = false; this.offsetWidth = 90; this.offsetHeight = 28;
  }
  append(child) { child.parent = this; this.children.push(child); }
  setAttribute(name, value) { this.attrs[name] = String(value); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(item => item !== this); }
}

let width = 800, height = 450;
const document = {createElement: tag => new Element(tag),
  documentElement: {getAttribute: () => 'on'}};
const gl = {
  VERTEX_SHADER:1, FRAGMENT_SHADER:2, COMPILE_STATUS:3, LINK_STATUS:4,
  ARRAY_BUFFER:5, STATIC_DRAW:6, FLOAT:7, DEPTH_TEST:8, TRIANGLES:9,
  COLOR_BUFFER_BIT:1, DEPTH_BUFFER_BIT:2,
  createShader:()=>({}), shaderSource(){}, compileShader(){}, getShaderParameter:()=>true,
  deleteShader(){}, createProgram:()=>({}), attachShader(){}, linkProgram(){},
  getProgramParameter:()=>true, deleteProgram(){}, useProgram(){},
  createBuffer:()=>({}), bindBuffer(){}, bufferData(){}, getAttribLocation:()=>0,
  enableVertexAttribArray(){}, vertexAttribPointer(){}, getUniformLocation:(_p,n)=>n,
  enable(){}, clearColor(){}, uniform3f(){}, drawArrays(){}, viewport(){}, clear(){},
  uniformMatrix4fv(){}, deleteBuffer(){}
};
const canvasEvents = {}, windowEvents = {};
const canvas = {width:0, height:0, getContext:()=>gl,
  getBoundingClientRect:()=>({width,height}),
  addEventListener:(name,fn)=>{canvasEvents[name]=fn;},
  removeEventListener:(name)=>{delete canvasEvents[name];}};
const stage = new Element('div');
stage.getBoundingClientRect = () => ({width,height});
const window = {document, devicePixelRatio:1,
  addEventListener:(name,fn)=>{windowEvents[name]=fn;},
  removeEventListener:(name)=>{delete windowEvents[name];}};
const context = vm.createContext({window, document, Float32Array, Math, Number, TypeError, Error, Object, Map});
for (const file of ['prototype/web/world3d-engine.js', 'prototype/web/world3d-signs.js'])
  vm.runInContext(fs.readFileSync(file, 'utf8'), context);

let signs = null;
const engine = window.LivingWorld3D.mount(canvas, {
  onViewChange() { signs?.update(); },
  onUnavailable() { signs?.hide(); }
});
assert.equal(engine.available, true);
signs = window.LivingWorldSigns.mount(stage, engine);
const layer = stage.children[0], labels = layer.children;
assert.deepEqual(labels.map(label => label.textContent), ['Post Office', 'City Archive', 'Bookshop']);
assert(labels.every(label => !label.hidden), 'all three landmarks project into the initial scene');
const beforeMove = labels.map(label => label.style.left);
engine.move(1, 0);
assert.notDeepEqual(labels.map(label => label.style.left), beforeMove,
  'camera-following labels update when the player moves');
const beforeResize = labels.map(label => label.style.left);
width = 600;
windowEvents.resize();
assert.equal(canvas.width, 600);
assert.notDeepEqual(labels.map(label => label.style.left), beforeResize,
  'labels reproject using the resized camera aspect ratio');
canvasEvents.webglcontextlost({});
assert.equal(engine.available, false);
assert(labels.every(label => label.hidden), 'labels hide after graphics context loss');
signs.destroy(); engine.destroy();
assert.equal(stage.children.length, 0);
console.log('3D engine and sign integration passed');
