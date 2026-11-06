import json
import tempfile
import unittest
from pathlib import Path

from prototype.curriculum_overview import MANIFEST, candidate_domains
from prototype.lesson_engine import PolicyError


class CurriculumOverviewTests(unittest.TestCase):
    def test_existing_domains_are_descriptive_and_unapproved(self):
        overview = candidate_domains()
        self.assertEqual(overview['status'], 'candidate_counts_only')
        self.assertFalse(overview['canonical_skill_definitions_present'])
        self.assertEqual(len(overview['domains']), 12)
        self.assertEqual({d['strand'] for d in overview['domains']},
                         {'word_recognition', 'language_comprehension'})
        self.assertEqual(sum(d['candidate_count'] for d in overview['domains']), 91)

    def test_invalid_or_missing_manifest_fails_closed(self):
        data = json.loads(MANIFEST.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'manifest.json'
            with self.assertRaises(PolicyError):
                candidate_domains(path)
            data['canonical_skill_definitions_present'] = True
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(PolicyError):
                candidate_domains(path)
            data['canonical_skill_definitions_present'] = False
            data['domains'][0]['candidate_count'] = -1
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(PolicyError):
                candidate_domains(path)


if __name__ == '__main__':
    unittest.main()
