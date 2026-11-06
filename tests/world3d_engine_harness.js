'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

function fixture(useGraphics=true, reduceMotion=false) {
  let drawCalls=0, deleted=0, created=0, clearColor;
  let boundBuffer=null;
  const offsets=[], materials=[], uploaded=new Map();
  const gl={
    VERTEX_SHADER:1, FRAGMENT_SHADER:2, COMPILE_STATUS:3, LINK_STATUS:4,
    ARRAY_BUFFER:5, STATIC_DRAW:6, FLOAT:7, DEPTH_TEST:8, TRIANGLES:9,
    COLOR_BUFFER_BIT:1, DEPTH_BUFFER_BIT:2,
    createShader:()=>({}), shaderSource(){}, compileShader(){}, getShaderParameter:()=>true,
    deleteShader(){}, createProgram:()=>({}), attachShader(){}, linkProgram(){},
    getProgramParameter:()=>true, deleteProgram(){deleted++;}, useProgram(){},
    createBuffer:()=>{created++;return {};}, bindBuffer(_target,buffer){boundBuffer=buffer;}, bufferData(_target,data){assert(data.length>=216);assert.equal(data.length%6,0);uploaded.set(boundBuffer,data);},
    getAttribLocation:()=>0, enableVertexAttribArray(){}, vertexAttribPointer(){},
    getUniformLocation:(_p,n)=>n, enable(){}, clearColor(...values){clearColor=values;},
    uniform3f(name,x,y,z){if(name==='offset')offsets.push([x,y,z]);if(name==='color')materials.push({color:[x,y,z],buffer:boundBuffer});},
    drawArrays(){drawCalls++;}, viewport(){}, clear(){offsets.length=0;materials.length=0;},
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
  return {canvas,window,listeners,offsets,materials,uploaded,get drawCalls(){return drawCalls;},get deleted(){return deleted;},get created(){return created;},get clearColor(){return clearColor;}};
}

const f=fixture();
const visited=[], nearby=[]; let viewChanges=0;
const world=f.window.LivingWorld3D.mount(f.canvas,{onVisit:id=>visited.push(id),onNearby:id=>nearby.push(id),onViewChange:()=>viewChanges++});
assert.equal(world.available,true);
assert(f.drawCalls>20,'the world draws real WebGL geometry');
assert(f.drawCalls<100,'static city geometry is batched for bounded redraw cost');
assert.equal(f.clearColor[3],0,'the original city backdrop can show behind the scene');
// The case directs the player to a blue lantern at the archive, then mentions a
// key and a closed box. Check the drawn scenery includes those visual cues in
// the corresponding areas. They are scenery and do not grant or record clues.
function batch(color) {
  const material=f.materials.find(item=>item.color.every((v,i)=>v===color[i]));
  assert(material, 'expected clue scenery material');
  return f.uploaded.get(material.buffer);
}
function hasVertex(vertices,xmin,xmax,ymin,ymax,zmin,zmax) {
  for(let i=0;i<vertices.length;i+=6) {
    if(vertices[i]>=xmin&&vertices[i]<=xmax&&vertices[i+1]>=ymin&&vertices[i+1]<=ymax
        &&vertices[i+2]>=zmin&&vertices[i+2]<=zmax) return true;
  }
  return false;
}
assert(hasVertex(batch([.14,.67,.95]),3.6,4.4,3.0,3.7,-13.4,-12.6),
  'a blue lantern is visible beside the archive');
const gold=batch([1,.82,.26]);
assert(hasVertex(gold,2.5,3.4,.5,.8,-13,-12.5),'a gold key sits near the archive');
assert(hasVertex(gold,-8.3,-7.9,.3,.6,-3.3,-3.0),'a gold fitting marks the bookshop box');
assert.equal(f.canvas.width,800);assert.equal(f.canvas.height,450);
const landmarks=world.getLandmarks(); assert.equal(landmarks.length,3);
const archive=landmarks.find(p=>p.id==='activities');
const projected=world.project(archive.x,archive.y,archive.z);
assert(Number.isFinite(projected.x)&&Number.isFinite(projected.y));
assert.equal(projected.visible,true,'the archive can be projected to the viewport');
assert.equal(world.project(NaN,1,2).visible,false,'invalid coordinates are rejected');
const start=world.getState();
let prevented=false;
f.listeners.keydown({key:'ArrowUp',preventDefault(){prevented=true;}});
assert(prevented);assert(world.getState().z<start.z);
assert(viewChanges>0,'sign positions can update after movement');
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
world.destroy();assert.equal(f.deleted,f.created+1,'all mesh and static batch buffers and program are released');assert(!f.listeners.keydown);
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
