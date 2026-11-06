'use strict';

// Original, unreviewed fictional reading-practice candidates for the adult
// synthetic demonstration. This client-side fixture is not an assessment,
// an authorization boundary, a record of ability, or evidence of mastery.
(function (global) {
  const scope = Object.freeze({review_status: 'unreviewed', audience: 'synthetic_adult_demo'});
  function candidate(id, title, teaching, passage, prompt, options, hint) {
    return Object.freeze({id, title, teaching, passage, prompt,
      options: Object.freeze(options.map(([choice, label]) => Object.freeze({id: choice, label}))),
      hint, ...scope});
  }
  const challenges = Object.freeze([
    candidate('decode', 'Read the folded note',
      'Blend the sounds /m/, short /a/ as in apple, and /p/ in order.',
      'A folded note has one word written on it.',
      'Which word matches those three sounds?',
      [['a', 'map'], ['b', 'mop'], ['c', 'mat']],
      'The first sound is /m/ and the last sound is /p/.'),
    candidate('context', 'Use the nearby words',
      'Nearby words and sentences can help explain what a word means.',
      'A blue lantern glowed. Its light made the dark archive doorway easy to see.',
      'In this story, what is the lantern?',
      [['a', 'A locked box'], ['b', 'A light'], ['c', 'A folded map']],
      'Look for the sentence that tells what the lantern gives.'),
    candidate('sequence', 'Follow the order',
      'Words such as first, next, and last show the order of events.',
      'First, the detective found a key. Next, the detective opened a locked box. Last, the detective saw a storybook inside.',
      'What happened immediately after the detective found the key?',
      [['a', 'The detective found the key'], ['b', 'The detective saw the storybook'], ['c', 'The detective opened the box']],
      'Find the sentence that begins with the word next.')
  ]);
  // Answers and clue text are client-side demonstration data, not secrets or a
  // source of reliable evidence. Educational release requires human review.
  const outcomes = Object.freeze({
    decode: Object.freeze({correct: 'a', clue_id: 'clue-decode',
      clue_text: 'The folded map shows a blue lantern outside the archive.',
      feedback: 'Yes. The sounds /m/, short /a/, and /p/ make map.'}),
    context: Object.freeze({correct: 'b', clue_id: 'clue-context',
      clue_text: 'Beside the blue lantern, a note says: Take the key to the bookshop.',
      feedback: 'Yes. The sentence says the lantern gives light.'}),
    sequence: Object.freeze({correct: 'c', clue_id: 'clue-sequence',
      clue_text: 'Inside the box is the missing storybook.',
      feedback: 'Yes. The detective opened the box next.'})
  });
  function get(id) {
    if (typeof id !== 'string') return null;
    return challenges.find(item => item.id === id) || null;
  }
  function evaluate(id, choiceId, hintUsed) {
    const challenge = get(id);
    if (!challenge || typeof choiceId !== 'string' || typeof hintUsed !== 'boolean'
        || !challenge.options.some(option => option.id === choiceId)) {
      throw new TypeError('A known challenge, choice and explicit hint status are required.');
    }
    const outcome = outcomes[id];
    const solved = choiceId === outcome.correct;
    return Object.freeze({solved, hint_used: hintUsed,
      feedback: solved ? outcome.feedback : 'Not quite. Read the clue and try again.',
      clue_id: solved ? outcome.clue_id : null,
      clue_text: solved ? outcome.clue_text : null});
  }
  global.LivingInvestigationReading = Object.freeze({list: () => challenges, get, evaluate});
})(window);
