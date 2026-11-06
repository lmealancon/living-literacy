'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup(available = true, {reading, onAnswer, onHint, onNavigate, onRestart, withSigns = false} = {}) {
  class Element {
    constructor(tag) { this.tagName=tag; this.children=[]; this.events={}; this.attributes={}; this.style={}; this.textContent=''; this.disabled=false; this.hidden=false; this.focusCount=0; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children=children; }
    setAttribute(name,value) { this.attributes[name]=value; }
    addEventListener(name,callback) { this.events[name]=callback; }
    focus() { this.focusCount++; }
    descendants() { return [this,...this.children.flatMap(child=>child.descendants())]; }
  }
  const root=new Element('div');
  const document={createElement: tag=>new Element(tag)};
  const visits=[], moves=[];
  const timers=new Map(); let nextTimer=0;
  let callbacks, engineAvailable=available, resets=0, pauses=0, resumes=0, destroys=0, interactions=0;
  const signEvents=[]; const position={x:0,z:7};
  const window={
    LivingInvestigationReading:reading,
    setTimeout(fn){const id=++nextTimer;timers.set(id,{fn,repeat:false});return id;},
    clearTimeout(id){timers.delete(id);},
    setInterval(fn){const id=++nextTimer;timers.set(id,{fn,repeat:true});return id;},
    clearInterval(id){timers.delete(id);},
    LivingWorld3D:{mount(canvas, handlers){
    callbacks=handlers;
    return {get available(){return engineAvailable;},
      move(dx,dz){moves.push([dx,dz]);position.x+=dx;position.z+=dz;handlers.onViewChange?.();},
      goTo(id){handlers.onNearby(id);handlers.onVisit(id);},
      interact(){interactions++;handlers.onVisit('activities');},
      getState(){return {...position};},
      getLandmarks(){return [{id:'voice',x:7,y:5,z:-5},{id:'activities',x:0,y:5,z:-12},{id:'signin',x:-7,y:5,z:-5}];},
      reset(){resets++;position.x=0;position.z=7;handlers.onViewChange?.();}, pause(){pauses++;}, resume(){resumes++;}, destroy(){destroys++;}
    };
  }}};
  if (withSigns) window.LivingWorldSigns={mount(){signEvents.push('mount');return {update(){signEvents.push('update');},hide(){signEvents.push('hide');},destroy(){signEvents.push('destroy');}};}};
  vm.runInNewContext(fs.readFileSync('prototype/web/world3d-ui.js','utf8'), {window,document,Object,TypeError});
  const controller=window.LivingWorld3DUI.mount(root,{navigate:id=>{visits.push(id); return onNavigate?.(id);},onAnswer,onHint,onRestart});
  const find=predicate=>root.descendants().find(predicate);
  const tick=()=>{for(const [id,timer] of [...timers]) { if(!timer.repeat)timers.delete(id); timer.fn(); }};
  const loseContext=()=>{engineAvailable=false;callbacks.onUnavailable();};
  return {root,controller,visits,moves,find,tick,timers,loseContext,signEvents,getCallbacks:()=>callbacks,stats:()=>({resets,pauses,resumes,destroys,interactions})};
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
  const h=setup(true,{withSigns:true});
  assert.deepEqual(h.signEvents.slice(0,2),['mount','update'],'building labels mount and draw once the world is ready');
  h.controller.updateQuest({allowedDestinations:['voice'],message:'Visit the Post Office.'});
  assert.match(h.find(el=>el.className==='world3d-wayfinding').textContent,/Post Office.*forward/);
  const before=h.signEvents.length;
  h.find(el=>el.attributes['aria-label']==='Move right').events.click({detail:0});
  assert(h.signEvents.length>before && h.signEvents.at(-1)==='update','movement updates projected labels');
  h.controller.pause();
  assert.equal(h.signEvents.at(-1),'hide','pause hides the labels');
  h.controller.resume();
  assert.equal(h.signEvents.at(-1),'update','resume redraws labels');
  h.loseContext();
  assert.equal(h.signEvents.at(-1),'hide','graphics loss hides labels');
  assert.match(h.find(el=>el.className==='world3d-wayfinding').textContent,/Post Office.*destination button/);
  h.controller.destroy();
  assert.equal(h.signEvents.at(-1),'destroy');
}
{
  const h=setup(false);
  assert.equal(h.controller.available,false);
  assert(h.find(el=>el.className==='world3d-stage').hidden);
  assert(h.find(el=>el.className==='world3d-map').hidden,'the map is hidden when 3D positioning is unavailable');
  assert.match(h.find(el=>el.className==='world3d-status').textContent,/unavailable/i);
  h.find(el=>el.textContent==='City Archive').events.click();
  assert.deepEqual(h.visits,['activities'],'destination navigation remains available without WebGL');
  h.controller.reset();
  assert.deepEqual(h.visits,['activities'],'fallback reset never navigates');
}
{
  const h=setup();
  const map=h.find(el=>el.className==='world3d-map');
  const player=h.find(el=>el.className==='world3d-map-player');
  const post=h.find(el=>el.attributes['aria-label']==='Visit Post Office on the case map');
  const archive=h.find(el=>el.attributes['aria-label']==='Visit City Archive on the case map');
  assert.equal(map.hidden,false,'the map appears when 3D coordinates are available');
  assert.equal(player.attributes['aria-hidden'],'true','text destinations remain the accessible alternative');
  assert.equal(typeof player.style.left,'string');
  h.controller.updateQuest({allowedDestinations:['voice'],message:'Go to the Post Office.'});
  assert.equal(post.disabled,false);
  assert.equal(archive.disabled,true,'the map uses the same locked-location state');
  archive.events.click();
  assert.deepEqual(h.visits,[],'a locked map marker cannot bypass the case');
  post.events.click();
  assert.deepEqual(h.visits,['voice'],'the map uses the existing navigation callback once');
  const before=player.style.left;
  h.find(el=>el.attributes['aria-label']==='Move right').events.click({detail:0});
  assert.notEqual(player.style.left,before,'player marker follows movement');
  h.getCallbacks().onViewChange();
  assert.equal(map.hidden,false,'view and resize callbacks keep the map available');
  h.controller.pause();
  assert.equal(map.hidden,true,'the map is hidden while the world is paused');
  h.controller.resume();
  assert.equal(map.hidden,false,'the map returns when the world resumes');
  h.loseContext();
  assert.equal(map.hidden,true,'the map is hidden after graphics context loss');
  assert.equal(h.find(el=>el.textContent==='Post Office').disabled,false,'text destinations remain available after graphics loss');
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
  h=setup(true,{reading,onHint(id){
    assert.equal(id,'decode');
    h.controller.updateQuest({caseTitle:'The Vanishing Storybook',allowedDestinations:['voice'],challengeId:'decode',pendingHint:true,feedback:'',clues:[]});
    return true;
  },onAnswer(id,choice,hintUsed){
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
  await h.find(el=>el.className==='world3d-hint').events.click();
  assert.equal(h.find(el=>el.className==='world3d-hint-text').hidden,false);
  await h.find(el=>el.textContent==='First').events.click();
  assert.equal(calls[1].hintUsed,true,'clicked hint is reported with the answer');
  assert.equal(challenge.hidden,true,'solved challenge closes when the journey advances');
  assert.equal(h.find(el=>el.className==='world3d-quest-title').focusCount,1,'after solving, focus moves to the updated casebook');
  assert.equal(h.find(el=>el.textContent==='City Archive').disabled,false);
  const entry=h.find(el=>el.className==='world3d-clue');
  assert.equal(entry.children[1].textContent,'Hint used');
  assert.equal(entry.children[2].textContent,'<img src=x onerror=alert(1)>','clue text is rendered as text, not HTML');
}
async function testHintRequiresConfirmedMatchingSnapshot() {
  const reading={get(id){ return id==='decode' ? {id,title:'Fictional word puzzle',teaching:'Read.',passage:'A note.',prompt:'Choose.',hint:'A fictional hint.',review_status:'unreviewed',audience:'synthetic_adult_demo',options:[{id:'a',label:'Answer'}]} : null; }};
  const base={allowedDestinations:['voice'],challengeId:'decode',pendingHint:false,feedback:'',clues:[]};
  let finish, called=0;
  const pending=new Promise(resolve=>{finish=resolve;});
  const h=setup(true,{reading,onHint(id){called++;assert.equal(id,'decode');return pending;}});
  h.controller.updateQuest(base);
  const hint=h.find(el=>el.className==='world3d-hint');
  const hintText=h.find(el=>el.className==='world3d-hint-text');
  assert.equal(hintText.attributes['aria-live'],'polite','a newly available hint is announced accessibly');
  const answer=h.find(el=>el.textContent==='Answer');
  const inFlight=hint.events.click();
  assert.equal(called,1);
  assert.equal(hintText.hidden,true,'hint must remain hidden until the persisted snapshot confirms it');
  assert.equal(answer.disabled,true,'answers are disabled while a hint request is in flight');
  h.controller.updateQuest({...base,pendingHint:true});
  assert.equal(hintText.hidden,false,'confirmed snapshot reveals the hint');
  finish(true); await inFlight;
  assert.equal(hint.disabled,true,'a confirmed hint cannot be requested again');
  assert.equal(answer.disabled,false);

  const restored=setup(true,{reading});
  restored.controller.updateQuest({...base,pendingHint:true});
  assert.equal(restored.find(el=>el.className==='world3d-hint-text').hidden,false,'a reload restores a previously recorded hint');
  assert.equal(restored.find(el=>el.className==='world3d-hint').disabled,true);

  const failed=setup(true,{reading,onHint(){return Promise.reject(new Error('offline'));}});
  failed.controller.updateQuest(base);
  await failed.find(el=>el.className==='world3d-hint').events.click();
  assert.equal(failed.find(el=>el.className==='world3d-hint-text').hidden,true,'failed persistence must not reveal a hint');
  assert.match(failed.find(el=>el.className==='world3d-feedback').textContent,/unavailable/i);
  assert.equal(failed.find(el=>el.className==='world3d-hint').disabled,false);

  const unconfirmed=setup(true,{reading,onHint(){return true;}});
  unconfirmed.controller.updateQuest(base);
  await unconfirmed.find(el=>el.className==='world3d-hint').events.click();
  assert.equal(unconfirmed.find(el=>el.className==='world3d-hint-text').hidden,true,'a callback result alone is not a persisted state');

  let resolveStale;
  const stale=setup(true,{reading,onHint(){return new Promise(resolve=>{resolveStale=resolve;});}});
  stale.controller.updateQuest(base);
  const staleRequest=stale.find(el=>el.className==='world3d-hint').events.click();
  stale.controller.updateQuest({allowedDestinations:['voice'],challengeId:null,pendingHint:false,clues:[]});
  resolveStale(true); await staleRequest;
  assert.equal(stale.find(el=>el.className==='world3d-hint-text').hidden,true,'a late response cannot reveal a stale challenge hint');
}
async function testChallengeFocusFollowsOnlyDeliberateVisits() {
  const reading={get(id){ return id==='decode' ? {id,title:'Fictional word puzzle',teaching:'Read.',passage:'A note.',prompt:'Choose.',hint:'Try.',review_status:'unreviewed',audience:'synthetic_adult_demo',options:[{id:'a',label:'Answer'}]} : null; }};
  const snapshot={allowedDestinations:['voice'],challengeId:'decode',feedback:'',clues:[]};
  let h;
  h=setup(true,{reading,onNavigate(){ h.controller.updateQuest(snapshot); }});
  h.controller.updateQuest({allowedDestinations:['voice'],challengeId:null,clues:[]});
  const title=h.find(el=>el.className==='world3d-challenge-title');
  assert.equal(title.attributes.tabindex,'-1');
  h.find(el=>el.textContent==='Post Office').events.click();
  assert.equal(title.focusCount,1,'visiting a location focuses the new challenge heading');
  h.controller.updateQuest(snapshot);
  assert.equal(title.focusCount,1,'background refresh must not move focus');

  let finish;
  const future = new Promise(resolve=>{finish=resolve;});
  const asyncWorld=setup(false,{reading,onNavigate(){return future;}});
  asyncWorld.controller.updateQuest({allowedDestinations:['voice'],challengeId:null,clues:[]});
  asyncWorld.find(el=>el.textContent==='Post Office').events.click();
  asyncWorld.controller.updateQuest(snapshot);
  assert.equal(asyncWorld.find(el=>el.className==='world3d-challenge-title').focusCount,1,'async visits focus their challenge when state arrives');
  finish(); await future;

  let finishStale;
  const stale = new Promise(resolve=>{finishStale=resolve;});
  const staleWorld=setup(false,{reading,onNavigate(){return stale;}});
  staleWorld.controller.updateQuest({allowedDestinations:['voice'],challengeId:null,clues:[]});
  staleWorld.find(el=>el.textContent==='Post Office').events.click();
  staleWorld.controller.reset();
  staleWorld.controller.updateQuest(snapshot);
  assert.equal(staleWorld.find(el=>el.className==='world3d-challenge-title').focusCount,0,'a profile reset cancels pending focus');
  finishStale(); await stale;
}
async function testRestartRequiresConfirmedCompletedCase() {
  let finish, calls=0;
  const pending=new Promise(resolve=>{finish=resolve;});
  const h=setup(true,{onRestart(){calls++;return pending;}});
  const restart=h.find(el=>el.className==='world3d-restart');
  const title=h.find(el=>el.className==='world3d-quest-title');
  const message=h.find(el=>el.className==='world3d-quest-message');
  const status=h.find(el=>el.className==='world3d-status');
  assert.equal(restart.hidden,true,'restart is hidden while the case is in progress');
  await restart.events.click();
  assert.equal(calls,0,'a hidden restart action cannot run');
  h.controller.updateQuest({phase:'case_solved',message:'Case complete.',clues:[{id:'clue-sequence',title:'Book',text:'Found'}]});
  assert.equal(restart.hidden,false,'restart is visible only after case completion');
  const request=restart.events.click();
  assert.equal(calls,1);
  assert.equal(restart.disabled,true,'restart is disabled while the request is pending');
  await restart.events.click();
  assert.equal(calls,1,'repeated clicks cannot start a second request');
  assert.equal(message.textContent,'Case complete.','the case is not optimistically reset');
  h.controller.updateQuest({phase:'exploring',message:'Start the investigation.',clues:[]});
  assert.equal(restart.hidden,true,'only the confirmed snapshot hides the completed-state action');
  finish(true); await request;
  assert.equal(title.focusCount,1,'a confirmed restart returns focus to the casebook');
  assert.equal(status.textContent,'Case restarted.');

  const failed=setup(true,{onRestart:()=>Promise.resolve(false)});
  failed.controller.updateQuest({phase:'case_solved',message:'Case complete.'});
  const failedButton=failed.find(el=>el.className==='world3d-restart');
  await failedButton.events.click();
  assert.equal(failedButton.hidden,false,'failed restart preserves the solved case');
  assert.equal(failedButton.disabled,false,'failed restart can be retried');
  assert.match(failed.find(el=>el.className==='world3d-status').textContent,/could not be restarted/i);

  const unconfirmed=setup(true,{onRestart:()=>true});
  unconfirmed.controller.updateQuest({phase:'case_solved',message:'Case complete.'});
  await unconfirmed.find(el=>el.className==='world3d-restart').events.click();
  assert.equal(unconfirmed.find(el=>el.className==='world3d-restart').hidden,false,'a return value alone cannot reset the case');

  let resolveStale;
  const stale=setup(true,{onRestart:()=>new Promise(resolve=>{resolveStale=resolve;})});
  stale.controller.updateQuest({phase:'case_solved',message:'Case complete.'});
  const staleRequest=stale.find(el=>el.className==='world3d-restart').events.click();
  stale.controller.reset();
  stale.controller.updateQuest({phase:'exploring',message:'Another profile.',clues:[]});
  resolveStale(true); await staleRequest;
  assert.equal(stale.find(el=>el.className==='world3d-quest-title').focusCount,0,'a late restart cannot move focus after reset');
  assert.equal(stale.find(el=>el.className==='world3d-quest-message').textContent,'Another profile.');
}
function testScriptedCaseCompanion() {
  const h=setup();
  const reply=h.find(el=>el.className==='world3d-guide-reply');
  const next=h.find(el=>el.className==='world3d-guide-next');
  const controls=h.find(el=>el.className==='world3d-guide-controls');
  assert.equal(reply.attributes['aria-live'],'polite');
  h.controller.updateQuest({phase:'exploring',challengeId:null,allowedDestinations:['voice'],message:'PRIVATE-NOT-REPEATED'});
  next.events.click();
  assert.match(reply.textContent,/Post Office/);
  assert(!reply.textContent.includes('PRIVATE-NOT-REPEATED'),'guide uses fixed guidance, not arbitrary data');
  h.controller.updateQuest({phase:'exploring',challengeId:'decode',allowedDestinations:['voice']});
  assert.match(reply.textContent,/help you find your way/,'case changes clear outdated guidance');
  next.events.click();
  assert.match(reply.textContent,/reading challenge/i);
  controls.events.click();
  assert.match(reply.textContent,/arrow keys/i);
  h.controller.updateQuest({phase:'case_solved',challengeId:null,allowedDestinations:['voice','activities','signin']});
  next.events.click();
  assert.match(reply.textContent,/fictional case is complete/i);
  h.controller.pause();
  const before=reply.textContent;
  next.events.click();
  assert.equal(reply.textContent,before,'paused guide ignores clicks');
  h.controller.destroy();
}
testScriptedCaseCompanion();
Promise.all([testCasebookAndChallenge(),testChallengeFocusFollowsOnlyDeliberateVisits(),testHintRequiresConfirmedMatchingSnapshot(),testRestartRequiresConfirmedCompletedCase()]).then(()=>console.log('3D world accessible controls passed')).catch(error=>{console.error(error);process.exitCode=1;});
