'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

function fixture(useGraphics=true, reduceMotion=false) {
  let drawCalls=0, deleted=0;
  const offsets=[];
  const gl={
    VERTEX_SHADER:1, FRAGMENT_SHADER:2, COMPILE_STATUS:3, LINK_STATUS:4,
    ARRAY_BUFFER:5, STATIC_DRAW:6, FLOAT:7, DEPTH_TEST:8, TRIANGLES:9,
    COLOR_BUFFER_BIT:1, DEPTH_BUFFER_BIT:2,
    createShader:()=>({}), shaderSource(){}, compileShader(){}, getShaderParameter:()=>true,
    deleteShader(){}, createProgram:()=>({}), attachShader(){}, linkProgram(){},
    getProgramParameter:()=>true, deleteProgram(){deleted++;}, useProgram(){},
    createBuffer:()=>({}), bindBuffer(){}, bufferData(_target,data){assert(data.length>=216);assert.equal(data.length%6,0);},
    getAttribLocation:()=>0, enableVertexAttribArray(){}, vertexAttribPointer(){},
    getUniformLocation:(_p,n)=>n, enable(){}, clearColor(){},
    uniform3f(name,x,y,z){if(name==='offset')offsets.push([x,y,z]);},
    drawArrays(){drawCalls++;}, viewport(){}, clear(){offsets.length=0;},
    uniformMatrix4fv(_location,_transpose,matrix){assert.equal(matrix.length,16);assert([...matrix].every(Number.isFinite));},
    deleteBuffer(){deleted++;}
  };
  const listeners={};
  const canvas={width:0,height:0,getContext:()=>useGraphics?gl:null,
    getBoundingClientRect:()=>({width:800,height:450}),
    addEventListener:(type,fn)=>listeners[type]=fn,
    removeEventListener:(type)=>delete listeners[type]};
  const window={devicePixelRatio:1,addEventListener(){},removeEventListener(){},
    document:{documentElement:{getAttribute:()=>reduceMotion?'off':'on'}}};
  vm.runInNewContext(fs.readFileSync('prototype/web/world3d-engine.js','utf8'),{window,Float32Array,Math,Number,TypeError,Error,Object});
  return {canvas,window,listeners,offsets,get drawCalls(){return drawCalls;},get deleted(){return deleted;}};
}

const f=fixture();
const visited=[], nearby=[];
const world=f.window.LivingWorld3D.mount(f.canvas,{onVisit:id=>visited.push(id),onNearby:id=>nearby.push(id)});
assert.equal(world.available,true);
assert(f.drawCalls>20,'the world draws real WebGL geometry');
assert.equal(f.canvas.width,800);assert.equal(f.canvas.height,450);
const start=world.getState();
let prevented=false;
f.listeners.keydown({key:'ArrowUp',preventDefault(){prevented=true;}});
assert(prevented);assert(world.getState().z<start.z);
assert.notEqual(f.offsets.at(-7)[2],world.getState().z,'the companion steps while moving');
const after=world.getState().z;
f.listeners.keydown({key:'w',ctrlKey:true,preventDefault(){throw Error('browser shortcut blocked');}});
assert.equal(world.getState().z,after,'modified shortcuts do not move the companion');
world.pause();world.move(0,-1);assert.equal(world.getState().z,after);
world.resume();world.goTo('activities');assert.equal(visited[0],'activities');
assert.equal(world.getState().nearby,'activities');
world.interact();assert.equal(visited[1],'activities');
world.goTo('invalid');assert.equal(visited.length,2);
world.goTo('signin');assert.equal(world.getState().nearby,'signin');
world.goTo('voice');assert.equal(world.getState().nearby,'voice');
assert.deepEqual(visited.slice(-2),['signin','voice'],'both city landmarks remain separately reachable');
world.reset();assert.equal(world.getState().z,7);
world.move(NaN,0);assert.equal(world.getState().z,7);
world.destroy();assert.equal(f.deleted,3);assert(!f.listeners.keydown);
assert(!f.listeners.webglcontextlost, 'destroy removes the context-loss listener');

const lost=fixture();
let lossCount=0;
const lostWorld=lost.window.LivingWorld3D.mount(lost.canvas,{onUnavailable:()=>lossCount++,onVisit:id=>visited.push(id)});
assert.equal(lostWorld.available,true);
lost.listeners.webglcontextlost({});
assert.equal(lostWorld.available,false,'loss immediately marks the renderer unavailable');
assert.equal(lossCount,1,'the UI is told to show its fallback once');
lost.listeners.webglcontextlost({});
assert.equal(lossCount,1,'repeat loss does not re-trigger fallback');
lostWorld.goTo('voice');
assert.equal(visited.at(-1),'voice','non-3D navigation remains usable');
lostWorld.destroy();

const without=fixture(false);
const fallback=without.window.LivingWorld3D.mount(without.canvas,{onVisit:id=>visited.push(id)});
assert.equal(fallback.available,false);
fallback.goTo('voice');assert.equal(visited.at(-1),'voice');
fallback.destroy();

const reduced=fixture(true,true);
const quietWorld=reduced.window.LivingWorld3D.mount(reduced.canvas);
quietWorld.move(0,-1);
assert.equal(reduced.offsets.at(-7)[2],quietWorld.getState().z,'reduced motion suppresses the walking bob');
quietWorld.destroy();
console.log('3D world engine checks passed');
