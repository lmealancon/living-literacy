'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({window: {}});
vm.runInContext(fs.readFileSync('prototype/web/investigation-reading.js', 'utf8'), context);
const reading = context.window.LivingInvestigationReading;
const all = reading.list();
assert.equal(all.length, 3);
assert.equal(Array.from(all, item => item.id).join(','), 'decode,context,sequence');
assert(Object.isFrozen(reading) && Object.isFrozen(all));
for (const item of all) {
  assert(Object.isFrozen(item) && Object.isFrozen(item.options) && Object.isFrozen(item.options[0]));
  assert.equal(item.review_status, 'unreviewed');
  assert.equal(item.audience, 'synthetic_adult_demo');
  assert(item.teaching && item.passage && item.prompt && item.hint);
  assert.equal(item.options.length, 3);
  assert.equal(new Set(Array.from(item.options, option => option.id)).size, 3);
}
// The mystery's ending should not appear in the teaching passage or answer
// choices before the final question is solved.
const finalTask = reading.get('sequence');
assert.doesNotMatch(finalTask.passage, /storybook/i);
for (const option of finalTask.options) assert.doesNotMatch(option.label, /storybook/i);
assert.match(reading.evaluate('sequence', 'c', false).clue_text, /storybook/i);
// Plain-letter descriptions avoid slash notation that screen readers may
// announce as punctuation rather than as sounds.
assert.doesNotMatch(reading.get('decode').teaching, /\//);
// Wrong answers do not reveal the next clue and a learner can retry.
for (const [id, correct, wrong, clue] of [
  ['decode', 'a', 'b', 'clue-decode'],
  ['context', 'b', 'c', 'clue-context'],
  ['sequence', 'c', 'a', 'clue-sequence']
]) {
  const first = reading.evaluate(id, wrong, false);
  assert.equal(first.solved, false);
  assert.equal(first.hint_used, false);
  assert.equal(first.clue_id, null);
  assert.equal(first.clue_text, null);
  assert.match(first.feedback, /try again/i);
  const retry = reading.evaluate(id, correct, true);
  assert.equal(retry.solved, true);
  assert.equal(retry.hint_used, true);
  assert.equal(retry.clue_id, clue);
  assert(retry.clue_text && retry.feedback);
  assert(Object.isFrozen(retry));
  // Calling a challenge has no stored state and cannot unlock a different one.
  assert.equal(reading.evaluate(id, wrong, false).clue_id, null);
}
assert.equal(reading.get('unknown'), null);
for (const bad of [
  () => reading.evaluate('missing', 'a', false),
  () => reading.evaluate('decode', 'wrong', false),
  () => reading.evaluate('decode', 'a'),
  () => reading.evaluate('decode', 'a', 'yes'),
  () => reading.evaluate('__proto__', 'a', false)
]) assert.throws(bad, /known challenge/i);
console.log('Synthetic investigation reading checks passed');
