'use strict';
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('prototype/web/investigation-client.js','utf8');
const window = {};
vm.runInNewContext(source,{window});
const {create} = window.LivingInvestigationClient;
const deferred = () => { let resolve,reject; const promise=new Promise((a,b)=>{resolve=a;reject=b;}); return {promise,resolve,reject}; };
const tick = () => new Promise(resolve=>setImmediate(resolve));
const base = (step,revision,more={}) => ({case_id:'synthetic-vanishing-storybook-v1', revision,
  phase:step==='lesson'?'activity_requested':step==='lesson_active'?'activity_started':step==='bookshop'?'returned':step==='solved'?'case_solved':'exploring',
  step, caseTitle:'The Vanishing Storybook', message:'Fictional case', clues:[], visited:[],
  challengeId:['decode','context','sequence'].includes(step)?step:null, feedback:'',
  allowedDestinations:({post_office:['voice'],decode:['voice'],archive:['activities'],context:['activities'],
    lesson:['activities'],lesson_active:['activities'],bookshop:['signin'],sequence:['signin'],solved:['signin','activities','voice']})[step], pendingHint:false,
  boundSessionId:step==='lesson_active'?'session-1':null, ...more});

async function functionalFlow() {
  let state=base('post_office',0), held=null;
  const calls=[], changes=[], navigations=[], errors=[];
  const request=async(path,body)=>{
    calls.push({path,body});
    if (!body) return {case:state};
    assert.equal(body.revision,state.revision,'every request uses latest confirmed revision');
    if (body.action==='visit' && body.destination==='voice') {
      if (held) await held.promise;
      state=base('decode',state.revision+1);
    } else if (body.action==='hint') state=base('decode',state.revision+1,{pendingHint:true});
    else if (body.action==='answer' && body.challenge==='decode') state=body.choice==='a'
      ?base('archive',state.revision+1):base('decode',state.revision+1,{pendingHint:true,feedback:'Not quite.'});
    else if (body.action==='visit' && body.destination==='activities') state=base('context',state.revision+1);
    else if (body.action==='answer' && body.challenge==='context') state=base('lesson',state.revision+1);
    else if (body.action==='bind') state=base('lesson_active',state.revision+1);
    else if (body.action==='finish') state=base('bookshop',state.revision+1);
    else if (body.action==='reset') state=base('post_office',state.revision+1);
    else throw Error('Unexpected action');
    return {case:state};
  };
  const client=create({request,onChange:s=>changes.push(s.step),navigate:(...v)=>navigations.push(v),onError:e=>errors.push(e)});
  assert.equal(await client.load('synthetic-a'),true);
  assert.equal(client.snapshot().step,'post_office');
  assert(Object.isFrozen(client.snapshot()));
  const beforeLocked=calls.length;
  assert.equal(await client.visit('activities'),false);
  assert.equal(calls.length,beforeLocked,'a locked location never produces an unauthorized request');
  assert.equal(client.isLoaded(),true,'a locked location does not clear the case');
  const beforeOrdinaryLesson = calls.length;
  assert.equal(await client.bindSession({student_id:'synthetic-a',session_id:'ordinary'},'synthetic-a'),false);
  assert.equal(calls.length,beforeOrdinaryLesson,'ordinary activities do not trigger case binding');
  assert(client.isLoadedFor('synthetic-a'));
  assert(!client.isLoadedFor('synthetic-other'));
  held=deferred();
  const entering=client.visit('voice'); await tick();
  assert.equal(client.snapshot().step,'post_office','no optimistic case change');
  assert.deepEqual(navigations,[],'no navigation before the server confirms');
  held.resolve(); assert.equal(await entering,true); held=null;
  assert.equal(client.snapshot().challengeId,'decode');
  assert.equal(await client.hint('decode'),true);
  assert.equal(client.snapshot().pendingHint,true,'hint is visible only after server confirms');
  assert.equal(await client.attempt('decode','b',true),false,'a wrong answer does not grant a clue');
  assert.equal(client.snapshot().feedback,'Not quite.');
  assert.equal(await client.attempt('decode','a',true),true);
  assert.equal(await client.visit('activities'),true);
  assert.deepEqual(navigations,[]);
  assert.equal(await client.attempt('context','b',false),true);
  assert.deepEqual(navigations,[['activities']],'only a confirmed archive answer opens the lesson list');
  assert.equal(await client.bindSession({student_id:'synthetic-other',session_id:'session-1'},'synthetic-a'),false);
  assert.equal(await client.bindSession({student_id:'synthetic-a',session_id:'session-1'},'synthetic-a'),true);
  assert.deepEqual(Object.keys(calls.at(-1).body).sort(),['action','revision','session_id']);
  const afterBinding=calls.length;
  assert.equal(await client.bindSession({student_id:'synthetic-a',session_id:'session-1'},'synthetic-a'),false);
  assert.equal(calls.length,afterBinding,'an already-bound session is not rebound');
  assert.equal(await client.observeSession({student_id:'synthetic-a',session_id:'other',status:'completed'}),false);
  assert.equal(await client.observeSession({student_id:'synthetic-a',session_id:'session-1',status:'completed'}),true);
  assert.equal(client.snapshot().step,'bookshop');
  assert.equal(client.returnToWorld(),true);
  const count=calls.length;
  client.reset();
  assert.equal(calls.length,count,'clearing the profile does not erase stored progress');
  assert.equal(client.snapshot().message,'Select a fictional profile to investigate.');
  assert.equal(await client.load('synthetic-a'),true);
  assert.equal(client.snapshot().step,'bookshop','saved state loads after switching back');
  assert.equal(await client.restart(),true,'restart is explicit');
  assert.equal(client.snapshot().step,'post_office');
  assert.deepEqual(errors,[]);
}

async function staleAndConflict() {
  const delayed=deferred(), changes=[], navigation=[], errors=[];
  let posts=0, gets=0;
  const client=create({request:async(path,body)=>{
    if (!body) {gets++; return {case:base('post_office',gets===1?0:4)};}
    posts++; if (posts===1) return delayed.promise;
    throw Object.assign(new Error('sensitive backend text'),{status:409});
  },onChange:s=>changes.push(s.step),navigate:v=>navigation.push(v),onError:e=>errors.push(e)});
  assert.equal(await client.load('synthetic-a'),true);
  const pending=client.visit('voice'); await tick();
  client.reset();
  delayed.resolve({case:base('decode',1)});
  assert.equal(await pending,false);
  assert.equal(client.snapshot().step,'post_office');
  assert.equal(client.snapshot().challengeId,null,'late old-profile response cannot restore data');
  assert.deepEqual(navigation,[]);
  assert.equal(await client.load('synthetic-b'),true);
  const postBefore=posts;
  assert.equal(await client.visit('voice'),false);
  assert.equal(posts,postBefore+1,'conflicting mutations are not automatically replayed');
  assert.equal(client.snapshot().revision,4,'conflict reloads the latest state');
  assert(errors.some(text=>text.includes('changed elsewhere')));
  assert(!errors.some(text=>text.includes('sensitive backend text')));
}

async function serialAndResume() {
  const held=deferred(), actions=[], navigation=[];
  const client=create({request:async(path,body)=>{
    if (!body) return {case:base('post_office',0)};
    actions.push({...body});
    if (body.action==='visit' && body.destination==='voice') {await held.promise; return {case:base('decode',1)};}
    if (body.action==='answer') return {case:base('archive',2)};
    throw Error('Unexpected action');
  },navigate:(...args)=>navigation.push(args)});
  await client.load('synthetic-a');
  const first=client.visit('voice'); await tick();
  const second=client.attempt('decode','a',false); await tick();
  assert.equal(actions.length,1,'case mutations serialize');
  held.resolve();
  assert.equal(await first,true); assert.equal(await second,true);
  assert.equal(actions[1].revision,1,'queued action uses newly confirmed revision');
  const resume=create({request:async(path,body)=>({case:base('lesson_active',body?8:7)}),navigate:(...args)=>navigation.push(args)});
  await resume.load('synthetic-a');
  assert.equal(await resume.visit('activities'),true);
  assert.deepEqual(navigation.at(-1),['resume','session-1'],'bound lesson resumes after reload');
}

async function badServerData() {
  const errors=[];
  const client=create({request:async()=>({case:{...base('post_office',0),clues:[{id:'unknown',title:'x',text:'x',usedHint:false}]}}),onError:e=>errors.push(e)});
  assert.equal(await client.load('synthetic-a'),false);
  assert.equal(client.isLoaded(),false);
  assert.equal(await client.load('real-name'),false);
  assert(errors.length>=2);
}

async function lateProfileLoad() {
  const first=deferred(), changes=[];
  const client=create({request:async(path)=>path.includes('synthetic-a')?first.promise:{case:base('archive',3)},
    onChange:s=>changes.push(s.step)});
  const waiting=client.load('synthetic-a'); await tick();
  assert.equal(await client.load('synthetic-b'),true);
  first.resolve({case:base('sequence',9)});
  assert.equal(await waiting,false);
  assert.equal(client.snapshot().step,'archive','late profile load cannot expose previous account state');
  assert(client.isLoadedFor('synthetic-b'));
  assert(!changes.includes('sequence'));
}

async function clearingFromChangeCallback() {
  let client, navigations=0;
  client=create({request:async(path,body)=>({case:base(body?'decode':'post_office',body?1:0)}),
    onChange:s=>{if(s.step==='decode') client.reset();},navigate:()=>navigations++});
  assert.equal(await client.load('synthetic-a'),true);
  assert.equal(await client.visit('voice'),false,'clearing during update invalidates that result');
  assert.equal(client.isLoaded(),false);
  assert.equal(navigations,0);
}

async function authorizationDenialClearsVisibleCase() {
  for (const status of [401,403]) {
    let writes=0; const errors=[];
    const clue={id:'clue-decode',title:'The folded map',text:'Fictional clue',usedHint:false};
    const client=create({request:async(path,body)=>{
      if (!body) return {case:base('archive',3,{clues:[clue]})};
      writes++;
      throw Object.assign(new Error('private denial detail'),{status});
    },onError:e=>errors.push(e)});
    assert.equal(await client.load('synthetic-a'),true);
    assert.equal(client.snapshot().clues.length,1);
    assert.equal(await client.visit('activities'),false);
    assert.equal(client.isLoaded(),false);
    assert.equal(client.snapshot().clues.length,0,'authorization denial removes previously shown clues');
    assert.equal(await client.visit('activities'),false);
    assert.equal(writes,1,'denied client must not repeat writes without reloading');
    assert(errors.length===1 && !errors[0].includes('private denial detail'));
  }
}

async function obsoleteQueuedAnswerIsDropped() {
  const held=deferred(); let writes=0;
  const client=create({request:async(path,body)=>{
    if (!body) return {case:base('decode',1)};
    writes++;
    await held.promise;
    return {case:base('archive',2)};
  }});
  assert.equal(await client.load('synthetic-a'),true);
  const first=client.attempt('decode','a',false);
  const second=client.attempt('decode','a',false);
  await tick(); assert.equal(writes,1);
  held.resolve();
  assert.equal(await first,true);
  assert.equal(await second,false);
  assert.equal(writes,1,'the obsolete answer is not sent after the case advances');
  assert(client.isLoaded(),'an obsolete queued answer does not clear an authorized case');
}

(async()=>{await functionalFlow(); await staleAndConflict(); await serialAndResume(); await badServerData(); await lateProfileLoad(); await clearingFromChangeCallback(); await authorizationDenialClearsVisibleCase(); await obsoleteQueuedAnswerIsDropped(); console.log('Synthetic investigation client checks passed');})().catch(error=>{console.error(error);process.exitCode=1;});
