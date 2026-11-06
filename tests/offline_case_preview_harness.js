'use strict';
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const lesson = JSON.parse(fs.readFileSync('content/SYNTHETIC_WORD_STUDY.demo-1.json', 'utf8'));
const previewCode = fs.readFileSync('tools/offline-case-preview.js', 'utf8');
const readingCode = fs.readFileSync('prototype/web/investigation-reading.js', 'utf8');
const journeyCode = fs.readFileSync('prototype/web/world3d-journey.js', 'utf8');

function setup(protocol='file:', withLesson=true) {
  const originalFetch = () => { throw new Error('A preview must not contact a network'); };
  const window = {location:{protocol}, fetch:originalFetch};
  if (withLesson) window.__LIVING_PREVIEW_LESSON__ = lesson;
  const context = vm.createContext({window});
  vm.runInContext(previewCode,context);
  vm.runInContext(readingCode,context);
  vm.runInContext(journeyCode,context);
  return {window,originalFetch};
}
async function main() {
  const remote = setup('https:');
  assert.strictEqual(remote.window.fetch,remote.originalFetch, 'not installed in deployed environments');
  const missing = setup('file:',false);
  assert.equal((await missing.window.fetch('/api/me')).status,503);
  const {window} = setup();
  const get = async path => {const r=await window.fetch(path); return {status:r.status,body:await r.json()};};
  const post = async (path, body) => {const r=await window.fetch(path,{method:'POST',body:JSON.stringify(body)}); return {status:r.status,body:await r.json()};};
  assert.equal((await window.fetch('https://example.test/private')).status,403);
  assert.equal((await get('/api/me')).body.identity,'synthetic-parent-1');
  assert.equal((await get('/api/profiles')).body.profiles[0].id,'synthetic-student-1');
  assert.equal((await get('/api/lessons')).body.lessons[0].lesson_id,lesson.lesson_id);
  const journey = window.LivingJourney.create();
  assert.equal(journey.visit('activities'),false);
  assert.equal(journey.visit('voice'),true);
  assert.equal(journey.attempt('decode','b',false),false);
  assert.equal(journey.attempt('decode','a',false),true);
  assert.equal(journey.visit('activities'),true);
  assert.equal(journey.attempt('context','b',true),true);
  const data = {student_id:'synthetic-student-1',lesson_id:lesson.lesson_id,version:lesson.version,idempotency_key:'preview-test-key'};
  let result = await post('/api/sessions',data), session=result.body.session;
  assert.equal(result.status,201);
  assert.equal((await post('/api/sessions',data)).body.session.session_id,session.session_id);
  assert.equal(journey.bindSession(session,'synthetic-student-1'),true);
  const path='/api/sessions/'+session.session_id+'/action';
  const action = async (action,extra={}) => {
    const result=await post(path,{action,revision:session.revision,...extra});
    assert.equal(result.status,200); session=result.body.session; journey.observeSession(session);
  };
  await action('activate');
  await action('next'); await action('next'); await action('next');
  assert.equal(session.stage_index,3);
  assert.equal((await post(path,{action:'respond',revision:session.revision,response:'',assisted:false})).status,403);
  await action('respond',{response:'map',assisted:false});
  await action('next'); await action('next'); await action('complete');
  assert.equal(journey.snapshot().phase,'activity_completed');
  assert.equal(journey.returnToWorld(),true);
  assert.equal(journey.visit('signin'),true);
  assert.equal(journey.attempt('sequence','c',false),true);
  assert.equal(journey.snapshot().phase,'case_solved');
  assert.equal((await post('/api/logout',{})).status,200);
  assert.equal((await get('/api/me')).status,403);
  assert.equal((await post('/api/login',{identity:'synthetic-parent-1',passphrase:'preview'})).status,200);
  assert.deepEqual((await get('/api/history/synthetic-student-1')).body.sessions,[]);
  console.log('Offline fictional case preview checks passed');
}
main().catch(error=>{console.error(error); process.exitCode=1;});
