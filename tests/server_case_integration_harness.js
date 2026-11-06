'use strict';
// Browserless integration of the real investigation client and app with the
// separate in-memory fictional HTTP fixture. The real server has its own tests.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

module.exports = async function runServerCaseIntegration({harness, response, deferred, tick}) {
  const lesson = JSON.parse(fs.readFileSync('content/SYNTHETIC_WORD_STUDY.demo-1.json', 'utf8'));
  const previewCode = fs.readFileSync('tools/offline-case-preview.js', 'utf8');
  function backend() {
    const window = {location:{protocol:'file:'}, __LIVING_PREVIEW_LESSON__:lesson};
    vm.runInNewContext(previewCode,{window});
    return window.fetch;
  }
  async function settle() { for (let i=0;i<8;i++) await tick(); }
  async function createGame(fetch) {
    let callbacks;
    const events=[], snapshots=[];
    const world3dMock = {mount(root, options) {
      callbacks=options;
      return {available:true,pause(){events.push('pause');},resume(){events.push('resume');},
        reset(){events.push('reset');},updateQuest(value){snapshots.push(value);}};
    }};
    const h=harness(fetch,{world3dMock});
    h.document.getElementById('history-filter').value='all';
    await settle();
    assert(callbacks, 'the 3D world must mount with the server-backed client');
    assert.equal(vm.runInContext("state.identity",h.context),'synthetic-parent-1');
    assert.equal(vm.runInContext("state.profile",h.context),'synthetic-student-1');
    assert.equal(vm.runInContext("journey.isLoadedFor('synthetic-student-1')",h.context),true);
    return {h,callbacks,events,snapshots};
  }
  async function reachLesson(game) {
    const {h,callbacks}=game;
    assert.equal(await callbacks.navigate('activities'),false, 'later locations stay locked');
    assert.equal(vm.runInContext('journey.snapshot().clues.length',h.context),0);
    assert.equal(await callbacks.navigate('voice'),true);
    assert.equal(vm.runInContext('journey.snapshot().challengeId',h.context),'decode');
    assert.equal(await callbacks.onHint('decode'),true, 'a hint is authorized before display');
    assert.equal(vm.runInContext('journey.snapshot().pendingHint',h.context),true);
    assert.equal(await callbacks.onAnswer('decode','b',true),false, 'wrong answers do not unlock clues');
    assert.equal(vm.runInContext('journey.snapshot().feedback',h.context),'Not quite. Read the clue and try again.');
    assert.equal(await callbacks.onAnswer('decode','a',true),true);
    assert.equal(vm.runInContext('journey.snapshot().clues[0].usedHint',h.context),true);
    assert.equal(await callbacks.navigate('activities'),true);
    assert.equal(await callbacks.onAnswer('context','b',false),true);
    assert.equal(vm.runInContext('journey.snapshot().step',h.context),'lesson');
    assert.equal(h.document.getElementById('lesson-list-title').focused,true,
      'the server-confirmed clue opens the real lesson selector');
  }
  async function startLesson(game) {
    const button=game.h.document.getElementById('lesson-list').descendants().find(x=>x.tagName==='button'&&x.textContent==='Start');
    assert(button, 'the existing sample lesson remains available');
    await button.events.click();
    assert.equal(vm.runInContext('journey.snapshot().step',game.h.context),'lesson_active');
    assert.equal(game.h.document.getElementById('world3d-root').hidden,true);
  }
  async function finishLesson(game) {
    const run=async(action,extra='')=>vm.runInContext(`runAction('${action}'${extra})`,game.h.context);
    await run('activate'); await run('next'); await run('next'); await run('next');
    await run('respond',", {response:'map',assisted:false}");
    await run('next'); await run('next'); await run('complete');
    assert.equal(vm.runInContext('journey.snapshot().step',game.h.context),'bookshop',
      'only a server-confirmed completed sample with its target practice unlocks the bookshop');
  }

  // A full case uses the real client, CSRF-bearing app request, and HTTP fixture.
  {
    const origin=backend(), calls=[];
    const game=await createGame((url,options)=>{calls.push({url,options});return origin(url,options);});
    await reachLesson(game);
    await startLesson(game);
    await finishLesson(game);
    await game.h.document.getElementById('back').events.click();
    assert.equal(game.h.document.getElementById('world3d-root').hidden,false);
    assert.equal(await game.callbacks.navigate('signin'),true);
    assert.equal(await game.callbacks.onAnswer('sequence','c',false),true);
    assert.equal(vm.runInContext('journey.snapshot().phase',game.h.context),'case_solved');
    assert.equal(vm.runInContext('journey.snapshot().clues.length',game.h.context),3);
    const writes=calls.filter(c=>c.url.endsWith('/investigation')&&c.options?.method==='POST');
    assert(writes.length>=8, 'case transitions must go to the server');
    assert(writes.every(c=>c.options.headers['X-CSRF-Token']==='fictional-preview-csrf'));
    assert(writes.some(c=>JSON.parse(c.options.body).action==='hint'));
    assert(writes.some(c=>JSON.parse(c.options.body).action==='bind'));
    assert(writes.some(c=>JSON.parse(c.options.body).action==='finish'));
    await game.h.document.getElementById('logout').events.click();
    assert.equal(vm.runInContext('journey.isLoaded()',game.h.context),false);
    assert.equal(vm.runInContext('journey.snapshot().clues.length',game.h.context),0);
    const count=calls.length;
    assert.equal(await game.callbacks.navigate('voice'),false);
    assert.equal(calls.length,count,'signed-out game visits must not issue case writes');
  }

  // A delayed old-account response must not repopulate data after sign-out.
  {
    const origin=backend(), held=deferred(); let delay=false, delayedResponse;
    const game=await createGame(async(url,options)=>{
      if (delay && url.endsWith('/investigation') && options?.method==='POST'
          && JSON.parse(options.body).action==='visit') {
        delayedResponse=await origin(url,options);
        return held.promise;
      }
      return origin(url,options);
    });
    delay=true;
    const pending=game.callbacks.navigate('voice');
    await settle();
    assert(delayedResponse, 'the mutation must have reached the fictional server before logout');
    await game.h.document.getElementById('logout').events.click();
    held.resolve(delayedResponse);
    assert.equal(await pending,false);
    assert.equal(vm.runInContext('journey.isLoaded()',game.h.context),false);
    assert.equal(vm.runInContext('journey.snapshot().challengeId',game.h.context),null);
    assert.equal(vm.runInContext('journey.snapshot().clues.length',game.h.context),0);
  }

  // If the current profile disappears, the app must load the replacement's
  // server case and discard late history belonging to the former profile.
  {
    const origin=backend(), held=deferred(); let replacing=false, delayHistory=false;
    const initial=await (await origin('/api/profiles/synthetic-student-1/investigation')).json();
    const game=await createGame((url,options)=>{
      if (delayHistory && url==='/api/history/synthetic-student-1') return held.promise;
      if (replacing && url==='/api/profiles') return Promise.resolve(response({profiles:[{id:'synthetic-b'}]}));
      if (replacing && url==='/api/profiles/synthetic-b/investigation') return Promise.resolve(response(initial));
      if (replacing && url==='/api/history/synthetic-b') return Promise.resolve(response({sessions:[]}));
      if (replacing && url==='/api/profiles/synthetic-b/interests') return Promise.resolve(response({interests:[],options:[]}));
      if (replacing && url==='/api/profiles/synthetic-b/activity') return Promise.resolve(response({responses_total:0,responses_assisted:0,assistance_unrecorded:0}));
      return origin(url,options);
    });
    assert.equal(await game.callbacks.navigate('voice'),true);
    assert.equal(await game.callbacks.onAnswer('decode','a',false),true);
    assert.equal(vm.runInContext('journey.snapshot().clues.length',game.h.context),1);
    delayHistory=true;
    const pending=vm.runInContext('loadHistory()',game.h.context);
    await settle();
    replacing=true;
    await vm.runInContext('loadDashboard()',game.h.context);
    assert.equal(vm.runInContext('state.profile',game.h.context),'synthetic-b');
    assert.equal(vm.runInContext("journey.isLoadedFor('synthetic-b')",game.h.context),true);
    assert.equal(vm.runInContext('journey.snapshot().clues.length',game.h.context),0,
      'prior profile clues cannot appear under the replacement');
    assert(game.events.includes('reset'), 'world position resets when profile changes');
    held.resolve(response({sessions:[{session_id:'old-private',status:'completed',lesson_id:'old',lesson_version:'1'}]}));
    await pending;
    assert.equal(vm.runInContext('state.history.length',game.h.context),0, 'late prior history must be ignored');
  }

  // A denied case mutation after consent revocation must clear prior clues and
  // prevent further case actions until a newly authorized load succeeds.
  {
    const origin=backend(); let deny=false, deniedWrites=0;
    const game=await createGame((url,options)=>{
      if (deny && url.endsWith('/investigation') && options?.method==='POST') {
        deniedWrites++; return Promise.resolve(response({},403));
      }
      return origin(url,options);
    });
    assert.equal(await game.callbacks.navigate('voice'),true);
    assert.equal(await game.callbacks.onAnswer('decode','a',false),true);
    assert.equal(vm.runInContext('journey.snapshot().clues.length',game.h.context),1);
    deny=true;
    assert.equal(await game.callbacks.navigate('activities'),false);
    assert.equal(vm.runInContext('journey.isLoaded()',game.h.context),false);
    assert.equal(vm.runInContext('journey.snapshot().clues.length',game.h.context),0,
      'authorization denial clears previously displayed case clues');
    assert.equal(game.snapshots.at(-1).clues.length,0, 'the case HUD is notified to clear its clues');
    assert.equal(await game.callbacks.navigate('activities'),false);
    assert.equal(deniedWrites,1,'the cleared client must not repeat unauthorized writes');
  }

  // Rapid repeated start clicks share an in-flight guard and cannot create a
  // second server session after the first response returns.
  {
    const origin=backend(), held=deferred(); let started=0, created;
    const game=await createGame(async(url,options)=>{
      if (url==='/api/sessions' && options?.method==='POST') {
        started++; created=await origin(url,options); return held.promise;
      }
      return origin(url,options);
    });
    await reachLesson(game);
    const button=game.h.document.getElementById('lesson-list').descendants().find(x=>x.tagName==='button'&&x.textContent==='Start');
    const first=button.events.click(); await settle();
    const second=button.events.click(); await settle();
    assert.equal(started,1,'only one start request may run at a time');
    held.resolve(created); await Promise.all([first,second]);
    assert.equal(vm.runInContext('journey.snapshot().step',game.h.context),'lesson_active');
  }

  // Reopening the already-bound lesson after an app reload must resume it,
  // rather than abandoning the stored case or creating another session.
  {
    const origin=backend(), calls=[];
    const fetch=(url,options)=>{calls.push({url,options});return origin(url,options);};
    const first=await createGame(fetch);
    await reachLesson(first); await startLesson(first);
    const sessionId=vm.runInContext('state.session.session_id',first.h.context);
    const count=calls.filter(c=>c.url==='/api/sessions'&&c.options?.method==='POST').length;
    const second=await createGame(fetch);
    assert.equal(vm.runInContext('journey.snapshot().step',second.h.context),'lesson_active');
    assert.equal(await second.callbacks.navigate('activities'),true);
    await settle();
    assert.equal(vm.runInContext('state.session.session_id',second.h.context),sessionId);
    assert.equal(second.h.document.getElementById('lesson-view').hidden,false);
    assert.equal(calls.filter(c=>c.url==='/api/sessions'&&c.options?.method==='POST').length,count,
      'resuming a bound session must not create a duplicate');
  }

  // A completed lesson with an incorrect practice word is retryable and must
  // never unlock the final location. A fresh valid attempt can complete it.
  {
    const origin=backend(), calls=[];
    const game=await createGame((url,options)=>{calls.push({url,options});return origin(url,options);});
    await reachLesson(game); await startLesson(game);
    const run=async(action,extra='')=>vm.runInContext(`runAction('${action}'${extra})`,game.h.context);
    await run('activate'); await run('next'); await run('next'); await run('next');
    await run('respond',", {response:'mop',assisted:false}"); await run('next'); await run('next'); await run('complete');
    assert.equal(vm.runInContext('journey.snapshot().step',game.h.context),'lesson',
      'an incorrect practice answer must return to the activity step');
    assert.equal(vm.runInContext('journey.snapshot().clues.length',game.h.context),2);
    assert.equal(vm.runInContext("journey.snapshot().allowedDestinations.includes('signin')",game.h.context),false);
    assert(vm.runInContext('journey.snapshot().feedback',game.h.context).includes('Practice'));
    const firstId=vm.runInContext('state.session.session_id',game.h.context);
    await game.h.document.getElementById('back').events.click();
    await startLesson(game);
    assert.notEqual(vm.runInContext('state.session.session_id',game.h.context),firstId,
      'retry must create a new lesson session');
    await finishLesson(game);
    assert.equal(calls.filter(c=>c.url==='/api/sessions'&&c.options?.method==='POST').length,2);
  }

  // Leaving an active lesson cancels the case binding, but the same valid
  // existing session can be rebound from History rather than started again.
  {
    const origin=backend(), calls=[];
    const game=await createGame((url,options)=>{calls.push({url,options});return origin(url,options);});
    await reachLesson(game); await startLesson(game);
    await vm.runInContext("runAction('activate')",game.h.context);
    const id=vm.runInContext('state.session.session_id',game.h.context);
    await game.h.document.getElementById('back').events.click();
    assert.equal(vm.runInContext('journey.snapshot().step',game.h.context),'lesson');
    assert.equal(vm.runInContext('journey.snapshot().clues.length',game.h.context),2);
    const open=game.h.document.getElementById('history').descendants().find(x=>x.tagName==='button'&&x.textContent==='Open');
    assert(open, 'the interrupted lesson is available in history');
    await open.events.click();
    assert.equal(vm.runInContext('state.session.session_id',game.h.context),id);
    assert.equal(vm.runInContext('journey.snapshot().step',game.h.context),'lesson_active',
      'opening an existing authorized session rebinds it to the case');
    assert.equal(calls.filter(c=>c.url==='/api/sessions'&&c.options?.method==='POST').length,1);
  }

  // Lesson content withdrawal after binding must cancel the case binding and
  // leave earlier server-confirmed clues intact for a retry.
  {
    const origin=backend(); let rejectLesson=false;
    const game=await createGame((url,options)=>{
      if (rejectLesson && url.startsWith('/api/lessons/') && url !== '/api/lessons') return Promise.resolve(response({},403));
      return origin(url,options);
    });
    await reachLesson(game); rejectLesson=true;
    const button=game.h.document.getElementById('lesson-list').descendants().find(x=>x.tagName==='button'&&x.textContent==='Start');
    await button.events.click();
    assert.equal(vm.runInContext('state.session',game.h.context),null);
    assert.equal(vm.runInContext('journey.snapshot().step',game.h.context),'lesson');
    assert.equal(vm.runInContext('journey.snapshot().clues.length',game.h.context),2);
    assert.equal(vm.runInContext("journey.snapshot().allowedDestinations.includes('signin')",game.h.context),false);
  }

  // A successful server completion followed by a failed content recheck must
  // not grant the next clue or strand the case in the active lesson step.
  {
    const origin=backend(); let completed=false, finishRequests=0;
    const game=await createGame(async(url,options)=>{
      if (completed && url.startsWith('/api/lessons/') && url !== '/api/lessons') return response({},403);
      if (url.endsWith('/investigation') && options?.method==='POST' && JSON.parse(options.body).action==='finish') finishRequests++;
      const result=await origin(url,options);
      if (url.endsWith('/action') && options?.method==='POST' && JSON.parse(options.body).action==='complete') completed=true;
      return result;
    });
    await reachLesson(game); await startLesson(game);
    const run=async(action,extra='')=>vm.runInContext(`runAction('${action}'${extra})`,game.h.context);
    await run('activate'); await run('next'); await run('next'); await run('next');
    await run('respond',", {response:'map',assisted:false}"); await run('next'); await run('next'); await run('complete');
    assert.equal(finishRequests,0,'a withdrawn lesson must be rechecked before case finish');
    assert.equal(vm.runInContext('state.session',game.h.context),null);
    assert.equal(vm.runInContext('journey.snapshot().step',game.h.context),'lesson');
    assert.equal(vm.runInContext('journey.snapshot().clues.length',game.h.context),2);
    assert.equal(vm.runInContext("journey.snapshot().allowedDestinations.includes('signin')",game.h.context),false);
  }
};
