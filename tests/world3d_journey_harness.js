'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({window:{}});
for (const file of ['prototype/web/investigation-reading.js','prototype/web/world3d-journey.js']) {
  vm.runInContext(fs.readFileSync(file, 'utf8'), context);
}
const {create} = context.window.LivingJourney;
const navigation = [], changes = [];
const journey = create({navigate: id => navigation.push(id), onChange: state => changes.push(state)});
const base = {session_id:'fictional-session', workspace_id:'synthetic-family', student_id:'synthetic-student',
  lesson_id:'synthetic-lesson-word-study', lesson_version:'demo-1', status:'created', stage_index:0, revision:0, responses:[]};
const completed = {...base,status:'completed',stage_index:5,revision:6,
  responses:[{stage:'practice',response:'map',assistance:{audio_or_modeling:true}}]};

assert.equal(journey.snapshot().phase, 'exploring');
assert.equal(journey.snapshot().caseTitle, 'The Vanishing Storybook');
assert.deepEqual(Array.from(journey.snapshot().allowedDestinations), ['voice']);
assert.equal(journey.visit('unknown'), false);
assert.equal(journey.visit('activities'), false, 'archive is locked before the first clue');
assert.equal(journey.visit('signin'), false, 'final destination is locked');
assert.equal(journey.attempt('decode','a',false), false, 'challenge must first be opened');
assert.equal(journey.bindSession(base, base.student_id), false, 'case puzzles must precede the lesson');
assert.equal(journey.observeSession(completed), false, 'completion cannot bind a journey');
assert.deepEqual(navigation, []);

assert.equal(journey.visit('voice'), true);
assert.equal(journey.snapshot().challengeId, 'decode');
assert.equal(journey.attempt('context','b',false), false, 'a different challenge cannot award a clue');
assert.equal(journey.attempt('decode','b',false), false, 'wrong choices do not unlock the archive');
assert.equal(journey.snapshot().clues.length, 0);
assert.equal(journey.visit('activities'), false);
assert.equal(journey.attempt('decode','a',true), true);
assert.deepEqual(Array.from(journey.snapshot().allowedDestinations), ['activities']);
assert.equal(journey.snapshot().clues[0].id, 'clue-decode');
assert.equal(journey.snapshot().clues[0].usedHint, true, 'hint use stays separate in the fictional case');
assert.equal(journey.attempt('decode','a',true), false, 'a solved clue cannot be duplicated');

assert.equal(journey.visit('activities'), true);
assert.equal(journey.snapshot().challengeId, 'context');
assert.equal(journey.attempt('context','a',false), false);
assert.equal(journey.snapshot().clues.length, 1);
assert.equal(journey.attempt('context','b',false), true);
assert.equal(journey.snapshot().phase, 'activity_requested');
assert.equal(journey.snapshot().clues[1].id, 'clue-context');
assert.deepEqual(navigation, ['activities'], 'only the solved archive clue opens the activity list');
assert.equal(journey.bindSession(base, 'synthetic-other'), false, 'different profiles must not attach');
assert.equal(journey.bindSession({...base,lesson_id:'different-lesson'}, base.student_id), false, 'only the map fixture fits this case');
assert.equal(journey.bindSession({...base,status:'completed',stage_index:5,revision:9}, base.student_id), false, 'old completed sessions cannot start a journey');
assert.equal(journey.bindSession(base, base.student_id), true);
assert.equal(journey.snapshot().phase, 'activity_started');
for (const [key,value] of [['session_id','other'],['workspace_id','other'],['student_id','other'],['lesson_id','other'],['lesson_version','other']]) {
  assert.equal(journey.observeSession({...completed,[key]:value}), false, key + ' must remain pinned');
}
assert.equal(journey.observeSession({...completed,revision:0}), false, 'completion must use a newer server revision');
assert.equal(journey.observeSession({...completed,stage_index:4,revision:1}), false, 'only the final stage can complete');
assert.equal(journey.returnToWorld(), false);
assert.equal(journey.visit('signin'), false, 'bookshop remains locked during the lesson');
assert.equal(journey.observeSession({...completed,responses:[],revision:2}), true);
assert.equal(journey.snapshot().phase, 'activity_requested', 'completing without practice requires a retry');
assert.match(journey.snapshot().message, /map practice response/i);
assert.equal(journey.returnToWorld(), false);
assert.equal(journey.bindSession({...base,session_id:'retry'}, base.student_id), true);
assert.equal(journey.observeSession({...completed,session_id:'retry',responses:[{stage:'practice',response:'   '}]}), true);
assert.equal(journey.snapshot().phase, 'activity_requested', 'blank practice is not a response');
assert.equal(journey.bindSession({...base,session_id:'retry-2'}, base.student_id), true);
assert.equal(journey.observeSession({...completed,session_id:'retry-2',revision:5,status:'active'}), true);
assert.equal(journey.observeSession({...completed,session_id:'retry-2',revision:5}), false, 'replayed revision is ignored');
assert.equal(journey.observeSession({...completed,session_id:'retry-2',revision:6}), true);
assert.equal(journey.snapshot().phase, 'activity_completed');
assert.equal(journey.cancelBoundSession(),false,'an already completed lesson is not cancelled');
assert.equal(journey.returnToWorld(), true);
assert.equal(journey.snapshot().phase, 'returned');
assert.deepEqual(Array.from(journey.snapshot().allowedDestinations), ['signin']);
assert.equal(journey.visit('signin'), true);
assert.equal(journey.snapshot().challengeId, 'sequence');
assert.equal(journey.attempt('sequence','a',false), false);
assert.equal(journey.attempt('sequence','c',false), true);
assert.equal(journey.snapshot().phase, 'case_solved');
assert.deepEqual(Array.from(journey.snapshot().clues, clue => clue.id), ['clue-decode','clue-context','clue-sequence']);
assert.match(journey.snapshot().message, /does not establish mastery/);
assert.ok(Object.isFrozen(journey.snapshot()) && Object.isFrozen(journey.snapshot().clues));
assert.ok(changes.length > 0);
journey.reset();
assert.equal(journey.snapshot().phase, 'exploring');
assert.equal(journey.snapshot().visited.length, 0);
assert.equal(journey.snapshot().clues.length, 0);
assert.equal(journey.observeSession(completed), false, 'old responses cannot finish a new case');

// A withdrawn or invalidated activity cannot unlock the final clue; the
// fictional case can retry only by obtaining another authorized session.
journey.visit('voice'); journey.attempt('decode','a',false);
journey.visit('activities'); journey.attempt('context','b',false);
assert.equal(journey.bindSession(base,base.student_id),true);
assert.equal(journey.observeSession({...base,status:'invalidated',revision:1}),true);
assert.equal(journey.snapshot().phase,'activity_requested');
assert.equal(journey.visit('signin'),false);
assert.equal(journey.observeSession(completed),false);
assert.equal(journey.snapshot().clues.length,2);
assert.equal(journey.bindSession({...base,session_id:'left-early'},base.student_id),true);
assert.equal(journey.cancelBoundSession(),true,'leaving an active lesson permits a retry');
assert.equal(journey.snapshot().phase,'activity_requested');
assert.match(journey.snapshot().message,/Reopen/);
assert.equal(journey.snapshot().clues.length,2,'leaving a lesson keeps case clues');
assert.equal(journey.observeSession({...completed,session_id:'left-early'}),false,'a late response cannot complete a cancelled binding');
assert.equal(journey.cancelBoundSession(),false,'an unbound session is not cancelled');
assert.equal(journey.bindSession({...base,session_id:'fresh'},base.student_id),true);
assert.equal(journey.observeSession({...completed,session_id:'fresh'}),true);
assert.equal(journey.cancelBoundSession(),false,'completion remains available for return');

// Never accept an arbitrary UI-supplied "solved" or mismatched evaluator clue.
const unavailable = vm.createContext({window:{}});
vm.runInContext(fs.readFileSync('prototype/web/world3d-journey.js','utf8'), unavailable);
const missing = unavailable.window.LivingJourney.create();
missing.visit('voice');
assert.equal(missing.attempt('decode','a',false), false);
assert.equal(missing.snapshot().clues.length, 0);
unavailable.window.LivingInvestigationReading = {evaluate: () => ({solved:true,clue_id:'other',hint_used:false})};
assert.equal(missing.attempt('decode','a',false), false);
assert.equal(missing.snapshot().clues.length, 0);
console.log('Synthetic mystery journey checks passed');
