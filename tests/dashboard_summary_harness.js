'use strict';
// Simulated DOM/network contract checks; not real-browser or accessibility QA.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
class Node {
  constructor(tag='div') { this.tagName=tag; this.children=[]; this.events={}; this.attrs={}; this._text=''; this.value=''; this.style={}; this.hidden=false; this.disabled=false; }
  set textContent(v) { this._text=String(v); this.children=[]; }
  get textContent() { return this._text+this.children.map(x=>x.textContent).join(''); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this._text=''; this.children=items; }
  setAttribute(k,v) { this.attrs[k]=String(v); }
  addEventListener(k,fn) { this.events[k]=fn; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  focus() {}
}
function response(body,status=200) { return {ok:status>=200&&status<300,status,json:async()=>body}; }
function deferred() { let resolve; const promise=new Promise(r=>resolve=r); return {promise,resolve}; }
function harness(fetch) {
  const nodes=new Map();
  const document={getElementById(id) {if(!nodes.has(id))nodes.set(id,new Node());return nodes.get(id);},
    createElement(tag){return new Node(tag);},createTextNode(text){let n=new Node('#text');n.textContent=text;return n;},
    documentElement:new Node('html'),body:new Node('body')};
  const context=vm.createContext({document,fetch,window:{matchMedia:()=>({matches:false,addEventListener(){}})},
    localStorage:{getItem(){return null;},setItem(){}},crypto:{randomUUID:()=> 'synthetic-idempotency-123'},console});
  vm.runInContext(fs.readFileSync('prototype/web/app.js','utf8'),context);
  return {context,document};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function run() {
  let activity=response({responses_total:4,responses_assisted:2,assistance_unrecorded:1});
  let domains=response({status:'candidate_counts_only',canonical_skill_definitions_present:false,
    domains:[{name:'Phonics',strand:'word_recognition'},{name:'Oral language',strand:'language_comprehension'}]});
  const calls=[];
  const h=harness((url,options)=>{
    calls.push({url,options});
    if(url==='/api/me')return Promise.resolve(response({},403));
    if(url==='/api/curriculum/domains')return Promise.resolve(domains);
    if(url.startsWith('/api/profiles/')&&url.endsWith('/activity'))return Promise.resolve(activity);
    if(url==='/api/logout')return Promise.resolve(response({ok:true}));
    throw Error('Unexpected request '+url);
  });
  await tick();
  vm.runInContext("state.identity='fictional-adult'; state.profile='synthetic-student-a'; state.csrf='csrf'",h.context);
  await vm.runInContext('loadActivitySummary()',h.context);
  const summary=h.document.getElementById('activity-summary');
  assert(summary.textContent.includes('Practice responses recorded4'));
  assert(summary.textContent.includes('Responses with reported audio or modeling support2'));
  assert(summary.textContent.includes('Responses with support not recorded1'));
  assert(!/mastery|proficiency|score/i.test(summary.textContent));
  assert(calls.some(x=>x.url==='/api/profiles/synthetic-student-a/activity'));

  // Incomplete or impossible counts must fail closed, never render a misleading zero.
  activity=response({responses_total:1,responses_assisted:2,assistance_unrecorded:0});
  await vm.runInContext('loadActivitySummary()',h.context);
  assert.equal(summary.textContent,'Activity summary is unavailable.');
  activity=response({},403);
  await vm.runInContext('loadActivitySummary()',h.context);
  assert.equal(summary.textContent,'Activity summary is unavailable.');

  await vm.runInContext('loadCurriculumDomains()',h.context);
  const areas=h.document.getElementById('curriculum-domains');
  for(const text of ['Word recognition','Phonics','Language comprehension','Oral language'])assert(areas.textContent.includes(text));
  domains=response({status:'approved',canonical_skill_definitions_present:true,domains:[{name:'Claim',strand:'word_recognition'}]});
  await vm.runInContext('loadCurriculumDomains()',h.context);
  assert.equal(areas.textContent,'Curriculum areas are unavailable.');

  // A late response from a previous profile must not appear after switching.
  const pending=deferred(); activity=pending.promise;
  const old=vm.runInContext('loadActivitySummary()',h.context);
  vm.runInContext("state.epoch++; state.profile='synthetic-student-b'; clearProfileData()",h.context);
  pending.resolve(response({responses_total:99,responses_assisted:90,assistance_unrecorded:1}));
  await old;
  assert.equal(summary.textContent,'');

  // Signing out clears already rendered profile-related activity immediately.
  summary.textContent='previous profile record'; areas.textContent='old curriculum';
  const logout=h.document.getElementById('logout').events.click();
  assert.equal(summary.textContent,''); assert.equal(areas.textContent,'');
  await logout;
  console.log('Dashboard summary checks passed');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
