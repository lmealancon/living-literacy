'use strict';
// Original, self-contained 3D fictional Victorian London experiment. No learner data,
// remote requests, learning scores, or authorization decisions are made here.
(function (global) {
  const LANDMARKS = Object.freeze([
    Object.freeze({id:'signin', x:-7, z:-5}),
    Object.freeze({id:'activities', x:0, z:-12}),
    Object.freeze({id:'voice', x:7, z:-5})
  ]);
  const LIMIT = 17, REACH = 2.7;
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const finite = v => typeof v === 'number' && Number.isFinite(v);
  function perspective(fovy, aspect, near, far) {
    const f = 1 / Math.tan(fovy / 2), q = 1 / (near - far);
    return new Float32Array([f/aspect,0,0,0, 0,f,0,0, 0,0,(far+near)*q,-1, 0,0,2*far*near*q,0]);
  }
  function lookAt(eye, center) {
    let zx=eye[0]-center[0], zy=eye[1]-center[1], zz=eye[2]-center[2];
    let l=Math.hypot(zx,zy,zz); zx/=l; zy/=l; zz/=l;
    let xx=zz, xy=0, xz=-zx; l=Math.hypot(xx,xy,xz); xx/=l; xz/=l;
    const yx=zy*xz-zz*xy, yy=zz*xx-zx*xz, yz=zx*xy-zy*xx;
    return new Float32Array([xx,yx,zx,0, xy,yy,zy,0, xz,yz,zz,0,
      -(xx*eye[0]+xy*eye[1]+xz*eye[2]),
      -(yx*eye[0]+yy*eye[1]+yz*eye[2]),
      -(zx*eye[0]+zy*eye[1]+zz*eye[2]),1]);
  }
  function multiply(a,b) {
    const result = new Float32Array(16);
    for (let col=0;col<4;col++) for (let row=0;row<4;row++) {
      let n=0; for (let k=0;k<4;k++) n += a[k*4+row]*b[col*4+k];
      result[col*4+row]=n;
    }
    return result;
  }
  // Each face has a normal for gentle directional shading; the scene uses
  // procedural geometry, so it has no imported game art or third-party code.
  function cube() {
    const faces = [
      [[1,0,0],[[.5,-.5,-.5],[.5,-.5,.5],[.5,.5,.5],[.5,.5,-.5]]],
      [[-1,0,0],[[-.5,-.5,.5],[-.5,-.5,-.5],[-.5,.5,-.5],[-.5,.5,.5]]],
      [[0,1,0],[[-.5,.5,-.5],[.5,.5,-.5],[.5,.5,.5],[-.5,.5,.5]]],
      [[0,-1,0],[[-.5,-.5,.5],[.5,-.5,.5],[.5,-.5,-.5],[-.5,-.5,-.5]]],
      [[0,0,1],[[.5,-.5,.5],[-.5,-.5,.5],[-.5,.5,.5],[.5,.5,.5]]],
      [[0,0,-1],[[-.5,-.5,-.5],[.5,-.5,-.5],[.5,.5,-.5],[-.5,.5,-.5]]]
    ];
    const vertices=[];
    for (const [normal, points] of faces) for (const i of [0,1,2,0,2,3]) vertices.push(...points[i],...normal);
    return new Float32Array(vertices);
  }
  function sphere() {
    // A compact low-poly sphere lets the original companion and foliage read
    // as sculpted forms without downloading any external 3D models.
    const vertices=[], bands=12, segments=20;
    const point=(i,j)=>{
      const latitude=Math.PI*i/bands, longitude=2*Math.PI*j/segments;
      const n=[Math.sin(latitude)*Math.cos(longitude),Math.cos(latitude),Math.sin(latitude)*Math.sin(longitude)];
      return [n[0]*.5,n[1]*.5,n[2]*.5,...n];
    };
    for(let i=0;i<bands;i++) for(let j=0;j<segments;j++) {
      const a=point(i,j),b=point(i+1,j),c=point(i+1,j+1),d=point(i,j+1);
      vertices.push(...a,...b,...c,...a,...c,...d);
    }
    return new Float32Array(vertices);
  }
  function shader(gl, type, source) {
    const s=gl.createShader(type); gl.shaderSource(s,source); gl.compileShader(s);
    if (!gl.getShaderParameter(s,gl.COMPILE_STATUS)) { gl.deleteShader(s); throw Error('Graphics unavailable'); }
    return s;
  }
  function renderer(canvas) {
    const gl=canvas.getContext('webgl', {alpha:false, antialias:true, powerPreference:'low-power'});
    if (!gl) throw Error('Graphics unavailable');
    const vertex=shader(gl,gl.VERTEX_SHADER,`attribute vec3 position; attribute vec3 normal; uniform mat4 viewProjection; uniform vec3 offset; uniform vec3 scale; varying float light; void main(){ vec3 p=position*scale+offset; gl_Position=viewProjection*vec4(p,1.0); light=0.70+0.30*max(dot(normalize(normal/scale),normalize(vec3(0.45,0.9,0.35))),0.0); }`);
    const fragment=shader(gl,gl.FRAGMENT_SHADER,`precision mediump float; uniform vec3 color; varying float light; void main(){ gl_FragColor=vec4(color*light,1.0); }`);
    const program=gl.createProgram(); gl.attachShader(program,vertex); gl.attachShader(program,fragment); gl.linkProgram(program);
    if (!gl.getProgramParameter(program,gl.LINK_STATUS)) throw Error('Graphics unavailable');
    gl.deleteShader(vertex); gl.deleteShader(fragment); gl.useProgram(program);
    const meshes={};
    for(const [name,data] of [['cube',cube()],['sphere',sphere()]]) {
      const buffer=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,buffer); gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);
      meshes[name]={buffer,count:data.length/6};
    }
    const position=gl.getAttribLocation(program,'position'), normal=gl.getAttribLocation(program,'normal');
    let bound=null;
    function bind(name) {
      if(bound===name)return;
      bound=name; gl.bindBuffer(gl.ARRAY_BUFFER,meshes[name].buffer);
      for (const [location, offset] of [[position,0],[normal,12]]) {
        gl.enableVertexAttribArray(location); gl.vertexAttribPointer(location,3,gl.FLOAT,false,24,offset);
      }
    }
    const vp=gl.getUniformLocation(program,'viewProjection'), pos=gl.getUniformLocation(program,'offset');
    const size=gl.getUniformLocation(program,'scale'), color=gl.getUniformLocation(program,'color');
    gl.enable(gl.DEPTH_TEST); gl.clearColor(.66,.79,.84,1);
    function box(x,y,z,sx,sy,sz,c) {
      bind('cube'); gl.uniform3f(pos,x,y,z); gl.uniform3f(size,sx,sy,sz); gl.uniform3f(color,c[0],c[1],c[2]); gl.drawArrays(gl.TRIANGLES,0,meshes.cube.count);
    }
    function oval(x,y,z,sx,sy,sz,c) {
      bind('sphere'); gl.uniform3f(pos,x,y,z); gl.uniform3f(size,sx,sy,sz); gl.uniform3f(color,c[0],c[1],c[2]); gl.drawArrays(gl.TRIANGLES,0,meshes.sphere.count);
    }
    function tree(x,z,scale=1) {
      box(x,1.1*scale,z,.48*scale,2.2*scale,.48*scale,[.37,.27,.21]);
      oval(x,2.9*scale,z,2.4*scale,2.2*scale,2.4*scale,[.27,.49,.37]);
      oval(x-.5*scale,3.5*scale,z+.2*scale,1.5*scale,1.5*scale,1.5*scale,[.33,.56,.42]);
      oval(x+.5*scale,3.6*scale,z-.2*scale,1.5*scale,1.5*scale,1.5*scale,[.38,.58,.44]);
    }
    // Fictional buildings inspired by the shape and materials of a nineteenth-
    // century London street. No historic building or commercial game is copied.
    function building(x,z,width,height,depth,brick,roof) {
      box(x,height/2,z,width,height,depth,brick);
      box(x,height+.17,z,width+.38,.34,depth+.35,roof);
      box(x,height+.6,z,width*.74,.55,depth*.75,roof);
      box(x+width*.25,height+1.1,z,.4,1,.45,[.35,.31,.30]);
      const front=z+depth/2+.04;
      box(x,1.05,front,.88,2.1,.14,[.17,.27,.31]);
      box(x,2.2,front,1.1,.18,.2,[.86,.76,.55]);
      const columns=Math.max(2,Math.floor(width/1.55));
      const rows=Math.max(1,Math.floor((height-2.4)/1.55));
      for(let row=0;row<rows;row++) for(let col=0;col<columns;col++) {
        const wx=x-width/2+(col+1)*width/(columns+1), wy=3+row*1.5;
        box(wx,wy,front,.72,.9,.10,[.24,.32,.34]);
        box(wx,wy,front+.06,.54,.72,.05,[.96,.77,.39]);
        box(wx,wy,front+.10,.05,.73,.05,[.42,.36,.29]);
        box(wx,wy,front+.10,.55,.05,.05,[.42,.36,.29]);
      }
    }
    function lamp(x,z) {
      box(x,.08,z,.8,.16,.8,[.38,.37,.34]);
      box(x,1.6,z,.15,3.1,.15,[.19,.25,.26]);
      box(x,3.35,z,.58,.55,.58,[.96,.77,.38]);
      box(x,3.68,z,.72,.12,.72,[.19,.25,.26]);
      oval(x,3.75,z,.28,.3,.28,[.19,.25,.26]);
    }
    function clockTower(x,z) {
      box(x,4,z,2.5,8,2.5,[.55,.50,.43]);
      box(x,8.15,z,2.8,.3,2.8,[.33,.35,.34]);
      box(x,9.2,z,2.1,1.9,2.1,[.47,.46,.42]);
      oval(x,9.2,z+1.08,1.25,1.25,.08,[.97,.89,.69]);
      box(x,9.35,z+1.14,.05,.48,.05,[.26,.27,.25]);
      box(x+.17,9.15,z+1.14,.33,.05,.05,[.26,.27,.25]);
      box(x,10.2,z,2.35,.22,2.35,[.30,.34,.33]);
      box(x,10.7,z,1.4,.8,1.4,[.33,.37,.36]);
    }
    function gate(x,z,c) {
      box(x-1.3,1.5,z,.45,3,.55,c); box(x+1.3,1.5,z,.45,3,.55,c);
      box(x,3.1,z,3,.45,.55,c); box(x,.12,z,2.8,.24,1.8,[.91,.83,.59]);
      oval(x,3.55,z,.75,.75,.75,[1,.82,.26]);
    }
    function draw(state) {
      const rect=canvas.getBoundingClientRect();
      const width=Math.max(1,Math.min(1600,Math.round(rect.width*(global.devicePixelRatio||1))));
      const height=Math.max(1,Math.min(1000,Math.round(rect.height*(global.devicePixelRatio||1))));
      if (canvas.width!==width) canvas.width=width; if (canvas.height!==height) canvas.height=height;
      gl.viewport(0,0,width,height); gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
      const camera=[state.x,10,state.z+16], center=[state.x,1,state.z-3];
      gl.uniformMatrix4fv(vp,false,multiply(perspective(Math.PI/3,width/height,.1,100),lookAt(camera,center)));
      // A cobbled square, riverside, and central street form a continuous map.
      box(0,-.35,0,38,.7,38,[.45,.47,.44]);
      box(0,.02,0,6,.08,38,[.52,.51,.47]);
      box(0,.03,-5,34,.08,5.5,[.52,.51,.47]);
      box(-5,.09,0,2.1,.18,38,[.70,.69,.62]);
      box(5,.09,0,2.1,.18,38,[.70,.69,.62]);
      // Small, evenly spaced pavers give depth without a texture download.
      for(let z=-18;z<=18;z+=2) for(let x=-2;x<=2;x+=2) {
        box(x+((z/2)%2)*.35,.075,z,1.7,.035,1.65,[.56,.55,.51]);
      }
      box(17.5,.04,-1,3,.08,36,[.28,.56,.63]);
      box(15.8,.25,-1,.35,.5,36,[.69,.67,.59]);
      for(let z=-16;z<=16;z+=4) box(15.8,.68,z,.45,.5,.45,[.48,.48,.44]);
      // Three distinct streetside landmarks sit behind the colored destinations.
      building(-9,-10,6.1,6.6,3.5,[.59,.34,.28],[.31,.31,.31]);
      building(9,-10,6.1,6.1,3.5,[.72,.52,.39],[.29,.34,.34]);
      building(0,-17,8,7.5,3,[.57,.46,.40],[.26,.31,.32]);
      building(-13,4,4.5,5.5,3.3,[.68,.42,.34],[.33,.31,.30]);
      building(12,4,4.2,5.8,3.3,[.63,.48,.38],[.29,.33,.33]);
      building(-15,-17,3.3,5.2,3.1,[.58,.41,.35],[.32,.31,.30]);
      building(13,-17,4,5.5,3.1,[.60,.43,.37],[.30,.31,.31]);
      clockTower(15,-19);
      for(const [lx,lz] of [[-4,7],[4,7],[-4,-2],[4,-2],[-11,-4],[11,-4],[-4,-13],[4,-13]]) lamp(lx,lz);
      for(const [tx,tz] of [[-16,10],[14,11],[-15,-5],[14,-4]]) tree(tx,tz,.75);
      gate(-7,-5,[.91,.51,.24]); gate(0,-12,[.27,.48,.83]); gate(7,-5,[.77,.35,.52]);
      // Original seed companion: a simple shaded 3D figure with limbs and leaf.
      const x=state.x,z=state.z;
      // Alternating steps and a small bob are driven only by deliberate player
      // movement; no timer or animation loop runs while the game is idle.
      const stride=state.reduceMotion ? 0 : Math.sin(state.walkFrame)*.24, bob=Math.abs(stride)*.25;
      oval(x-.29,.32,z+stride,.42,.45,.64,[.10,.53,.45]); oval(x+.29,.32,z-stride,.42,.45,.64,[.10,.53,.45]);
      oval(x,1.25+bob,z,1.5,1.9,1.2,[.98,.71,.22]);
      oval(x,2.25+bob,z,.35,.45,.4,[.25,.65,.31]); oval(x+.28,2.38+bob,z,.6,.23,.3,[.33,.73,.37]);
      oval(x-.81,1.25+bob,z-stride,.45,.65,.48,[.10,.53,.45]); oval(x+.81,1.25+bob,z+stride,.45,.65,.48,[.10,.53,.45]);
      // Camera faces the back of the companion; the companion stays in view.
    }
    function destroy(){ for(const mesh of Object.values(meshes))gl.deleteBuffer(mesh.buffer); gl.deleteProgram(program); }
    return {draw,destroy};
  }
  function mount(canvas, options={}) {
    if (!canvas || typeof canvas.getContext !== 'function') throw TypeError('A canvas is required');
    const onNearby=typeof options.onNearby==='function'?options.onNearby:()=>{};
    const onVisit=typeof options.onVisit==='function'?options.onVisit:()=>{};
    const onUnavailable=typeof options.onUnavailable==='function'?options.onUnavailable:()=>{};
    const state={x:0,z:7,nearby:null,walkFrame:0,reduceMotion:false};
    let active=true, destroyed=false, graphics=null, mounted=false;
    try { graphics=renderer(canvas); } catch (_) { /* Parent supplies accessible non-WebGL navigation. */ }
    function loseGraphics() {
      if (!graphics || destroyed) return;
      // A lost context cannot reliably delete its own GPU resources. Drop the
      // reference and keep the direct, non-3D navigation available instead.
      graphics=null;
      if (mounted) onUnavailable();
    }
    function paint() {
      if (!graphics || destroyed) return;
      try { graphics.draw(state); } catch (_) { loseGraphics(); }
    }
    function nearest() {
      let best=null,distance=Infinity;
      for(const p of LANDMARKS){ const d=Math.hypot(state.x-p.x,state.z-p.z); if(d<distance){distance=d;best=p;} }
      return distance<=REACH?best:null;
    }
    function update(){
      state.reduceMotion = global.document?.documentElement?.getAttribute('data-motion') === 'off'
        || Boolean(global.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches);
      const next=nearest()?.id||null;
      if(next!==state.nearby){state.nearby=next;onNearby(next);}
      paint();
    }
    function move(dx,dz){
      if(!active||destroyed||!finite(dx)||!finite(dz)) return;
      dx=clamp(dx,-1,1); dz=clamp(dz,-1,1);
      state.x=clamp(state.x+dx*.7,-LIMIT,LIMIT); state.z=clamp(state.z+dz*.7,-LIMIT,LIMIT);
      if (dx || dz) state.walkFrame+=1.4;
      update();
    }
    function interact(){if(!active||destroyed)return;const p=nearest();if(p)onVisit(p.id);}
    function goTo(id){
      if(!active||destroyed)return;
      const p=LANDMARKS.find(item=>item.id===id);if(!p)return;
      state.x=p.x;state.z=p.z+1.5;state.walkFrame=0;update();onVisit(p.id);
    }
    const onKey=event=>{
      if(!active||destroyed||event.ctrlKey||event.metaKey||event.altKey||event.isComposing)return;
      const key=event.key.length===1?event.key.toLowerCase():event.key;
      const keys={ArrowUp:[0,-1],ArrowDown:[0,1],ArrowLeft:[-1,0],ArrowRight:[1,0],w:[0,-1],s:[0,1],a:[-1,0],d:[1,0]};
      if(Object.prototype.hasOwnProperty.call(keys,key)){event.preventDefault();move(...keys[key]);}
      else if(key==='Enter'||key===' '){event.preventDefault();interact();}
    };
    const onResize=()=>{if(active&&!destroyed)paint();};
    canvas.addEventListener('keydown',onKey);
    canvas.addEventListener('webglcontextlost',loseGraphics);
    if(typeof global.addEventListener==='function')global.addEventListener('resize',onResize);
    update();
    mounted=true;
    return Object.freeze({
      get available(){return Boolean(graphics);}, move, interact, goTo,
      pause(){active=false;}, resume(){if(!destroyed){active=true;update();}},
      reset(){if(!destroyed){state.x=0;state.z=7;state.walkFrame=0;update();}},
      destroy(){if(destroyed)return;active=false;destroyed=true;canvas.removeEventListener('keydown',onKey);canvas.removeEventListener('webglcontextlost',loseGraphics);if(typeof global.removeEventListener==='function')global.removeEventListener('resize',onResize);if(graphics)graphics.destroy();},
      getState(){return {x:state.x,z:state.z,nearby:state.nearby};}
    });
  }
  global.LivingWorld3D=Object.freeze({mount});
})(window);
