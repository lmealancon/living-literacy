'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup(available = true, {reading, onAnswer} = {}) {
  class Element {
    constructor(tag) { this.tagName=tag; this.children=[]; this.events={}; this.attributes={}; this.textContent=''; this.disabled=false; this.hidden=false; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children=children; }
    setAttribute(name,value) { this.attributes[name]=value; }
    addEventListener(name,callback) { this.events[name]=callback; }
    descendants() { return [this,...this.children.flatMap(child=>child.descendants())]; }
  }
  const root=new Element('div');
  const document={createElement: tag=>new Element(tag)};
  const visits=[], moves=[];
  const timers=new Map(); let nextTimer=0;
  let callbacks, engineAvailable=available, resets=0, pauses=0, resumes=0, destroys=0, interactions=0;
  const window={
    LivingInvestigationReading:reading,
    setTimeout(fn){const id=++nextTimer;timers.set(id,{fn,repeat:false});return id;},
    clearTimeout(id){timers.delete(id);},
    setInterval(fn){const id=++nextTimer;timers.set(id,{fn,repeat:true});return id;},
    clearInterval(id){timers.delete(id);},
    LivingWorld3D:{mount(canvas, handlers){
    callbacks=handlers;
    return {get available(){return engineAvailable;},
      move(dx,dz){moves.push([dx,dz]);},
      goTo(id){handlers.onNearby(id);handlers.onVisit(id);},
      interact(){interactions++;handlers.onVisit('activities');},
      reset(){resets++;}, pause(){pauses++;}, resume(){resumes++;}, destroy(){destroys++;}
    };
  }}};
  vm.runInNewContext(fs.readFileSync('prototype/web/world3d-ui.js','utf8'), {window,document,Object,TypeError});
  const controller=window.LivingWorld3DUI.mount(root,{navigate:id=>visits.push(id),onAnswer});
  const find=predicate=>root.descendants().find(predicate);
  const tick=()=>{for(const [id,timer] of [...timers]) { if(!timer.repeat)timers.delete(id); timer.fn(); }};
  const loseContext=()=>{engineAvailable=false;callbacks.onUnavailable();};
  return {root,controller,visits,moves,find,tick,timers,loseContext,getCallbacks:()=>callbacks,stats:()=>({resets,pauses,resumes,destroys,interactions})};
}
{
  const h=setup();
  const canvas=h.find(el=>el.tagName==='canvas');
  assert.equal(canvas.tabIndex,0);
  assert.match(canvas.attributes['aria-label'],/arrow keys/i);
  h.find(el=>el.attributes['aria-label']==='Move forward').events.click();
  assert.deepEqual(h.moves,[[0,-1]]);
  const right=h.find(el=>el.attributes['aria-label']==='Move right');
  right.events.pointerdown({button:2,isPrimary:true});
  assert.equal(h.timers.size,0,'secondary buttons do not start movement');
  right.events.pointerdown(); right.events.pointerup(); right.events.click({detail:1});
  assert.deepEqual(h.moves.at(-1),[1,0],'short taps move once');
  right.events.pointerdown(); h.tick(); h.tick();
  assert.deepEqual(h.moves.slice(-2),[[1,0],[1,0]],'held touch repeats movement');
  right.events.pointerup();
  const afterHeld=h.moves.length;
  right.events.click({detail:1});
  assert.equal(h.moves.length,afterHeld,'release click does not add a duplicate step');
  right.events.click({detail:0});
  assert.equal(h.moves.length,afterHeld+1,'keyboard activation remains available');
  right.events.pointerdown(); h.tick();
  h.controller.pause();
  assert.equal(h.timers.size,0,'pause stops pending movement');
  h.controller.resume();
  h.find(el=>el.textContent==='City Archive').events.click();
  assert.deepEqual(h.visits,['activities'],'direct destination navigates exactly once');
  assert.equal(h.stats().interactions,0,'direct destination must not interact twice');
  h.controller.reset();
  assert.equal(h.stats().resets,1);
  assert.deepEqual(h.visits,['activities'],'reset never navigates');
  h.getCallbacks().onNearby('voice');
  assert.match(h.find(el=>el.className==='world3d-status').textContent,/Post Office/);
  h.controller.updateQuest({phase:'activity_completed',message:'Activity completed; return to the garden.',visited:['activities']});
  assert.equal(h.find(el=>el.className==='world3d-quest-message').textContent,'Activity completed; return to the garden.');
  assert.match(h.find(el=>el.className==='world3d-visited').textContent,/City Archive/);
  h.controller.pause();
  h.find(el=>el.textContent==='Bookshop').events.click();
  assert.deepEqual(h.visits,['activities'],'paused UI cannot navigate');
  assert.equal(h.stats().pauses,2);
  h.controller.resume();
  h.find(el=>el.textContent==='Bookshop').events.click();
  assert.deepEqual(h.visits,['activities','signin']);
  assert.equal(h.stats().resumes,2);
  right.events.pointerdown(); h.tick(); right.events.pointercancel();
  assert.equal(h.timers.size,0,'pointer cancellation stops movement');
  right.events.pointerdown(); h.tick(); right.events.pointerleave();
  assert.equal(h.timers.size,0,'leaving the button stops movement');
  right.events.pointerdown(); h.tick();
  h.controller.destroy();
  assert.equal(h.timers.size,0,'destroy stops movement timers');
  assert.equal(h.stats().destroys,1);
  assert.equal(h.root.children.length,0);
}
{
  const h=setup(false);
  assert.equal(h.controller.available,false);
  assert(h.find(el=>el.className==='world3d-stage').hidden);
  assert.match(h.find(el=>el.className==='world3d-status').textContent,/unavailable/i);
  h.find(el=>el.textContent==='City Archive').events.click();
  assert.deepEqual(h.visits,['activities'],'destination navigation remains available without WebGL');
  h.controller.reset();
  assert.deepEqual(h.visits,['activities'],'fallback reset never navigates');
}
{
  const h=setup();
  const right=h.find(el=>el.attributes['aria-label']==='Move right');
  right.events.pointerdown(); h.tick();
  assert.equal(h.timers.size,1,'holding a movement button starts the repeat timer');
  h.loseContext();
  assert.equal(h.controller.available,false);
  assert.equal(h.timers.size,0,'losing graphics stops repeated movement');
  assert(h.find(el=>el.className==='world3d-stage').hidden,'the failed view is hidden');
  assert(right.disabled,'movement becomes unavailable');
  assert.match(h.find(el=>el.className==='world3d-status').textContent,/unavailable/i);
  h.getCallbacks().onNearby('voice');
  assert.match(h.find(el=>el.className==='world3d-status').textContent,/unavailable/i,'late proximity does not hide graphics failure');
  h.find(el=>el.textContent==='City Archive').events.click();
  assert.deepEqual(h.visits,['activities'],'the direct text destination remains available');
  h.getCallbacks().onVisit('voice');
  assert.deepEqual(h.visits,['activities'],'stale graphics callbacks do not navigate');
  h.controller.reset();
  assert.deepEqual(h.visits,['activities'],'reset does not navigate');
  h.controller.pause(); h.controller.resume();
  assert(right.disabled,'movement remains disabled after pause and resume');
  h.getCallbacks().onUnavailable();
  assert.deepEqual(h.visits,['activities'],'repeated loss notifications are harmless');
}
async function testCasebookAndChallenge() {
  const calls=[];
  const reading={get(id){
    if (id!=='decode') return null;
    return {id,title:'Fictional word puzzle',teaching:'Try reading the fictional note.',passage:'A short note.',prompt:'Choose a word.',hint:'Look again.',review_status:'unreviewed',audience:'synthetic_adult_demo',options:[{id:'a',label:'First'},{id:'b',label:'Second'}]};
  }};
  let h;
  h=setup(true,{reading,onAnswer(id,choice,hintUsed){
    calls.push({id,choice,hintUsed});
    if (choice==='b') {
      h.controller.updateQuest({caseTitle:'The Vanishing Storybook',allowedDestinations:['voice'],challengeId:'decode',feedback:'Try another answer.',clues:[]});
      return false;
    }
    h.controller.updateQuest({caseTitle:'The Vanishing Storybook',allowedDestinations:['activities'],challengeId:null,feedback:'',clues:[{id:'clue-decode',title:'Folded note',text:'<img src=x onerror=alert(1)>',usedHint:true}]});
    return true;
  }});
  h.controller.updateQuest({caseTitle:'The Vanishing Storybook',message:'Investigate the Post Office.',allowedDestinations:['voice'],challengeId:'decode',feedback:'',clues:[]});
  assert.equal(h.find(el=>el.className==='world3d-title').textContent,'The Vanishing Storybook');
  assert.equal(h.find(el=>el.textContent==='Post Office').disabled,false);
  assert.equal(h.find(el=>el.textContent==='City Archive').disabled,true,'locked destinations cannot be selected');
  assert.equal(h.find(el=>el.textContent==='Bookshop').disabled,true);
  h.find(el=>el.textContent==='City Archive').events.click();
  assert.deepEqual(h.visits,[],'synthetic direct clicks cannot bypass the location lock');
  const challenge=h.find(el=>el.className==='world3d-challenge');
  assert.equal(challenge.hidden,false);
  await h.find(el=>el.textContent==='Second').events.click();
  assert.equal(h.find(el=>el.className==='world3d-feedback').textContent,'Try another answer.','incorrect answer feedback is not overwritten');
  assert.equal(calls[0].hintUsed,false);
  h.find(el=>el.className==='world3d-hint').events.click();
  assert.equal(h.find(el=>el.className==='world3d-hint-text').hidden,false);
  await h.find(el=>el.textContent==='First').events.click();
  assert.equal(calls[1].hintUsed,true,'clicked hint is reported with the answer');
  assert.equal(challenge.hidden,true,'solved challenge closes when the journey advances');
  assert.equal(h.find(el=>el.textContent==='City Archive').disabled,false);
  const entry=h.find(el=>el.className==='world3d-clue');
  assert.equal(entry.children[1].textContent,'Hint used');
  assert.equal(entry.children[2].textContent,'<img src=x onerror=alert(1)>','clue text is rendered as text, not HTML');
}
testCasebookAndChallenge().then(()=>console.log('3D world accessible controls passed')).catch(error=>{console.error(error);process.exitCode=1;});
