"""Fictional fixtures test infrastructure, not real skill definitions."""
import copy
import tempfile
import unittest
from pathlib import Path

from prototype.lesson_engine import PolicyError
from prototype.skill_registry import SyntheticSkillRegistry


def fictional_record(skill_id, dependencies=None):
    return {'skill_id': skill_id, 'version': '0.0.1', 'domain_code': skill_id[:2],
        'name': 'Fictional fixture', 'observable_behavior': 'Fictional observable behavior for test only.',
        'instructional_routine_id': 'synthetic-routine', 'status': 'draft',
        'prerequisite_skill_ids': dependencies or [], 'eligible_evidence': [],
        'review': {'reviewer_ref': None, 'decision_ref': None, 'decision_date': None}}


class SkillRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'test.sqlite'
        self.registry = SyntheticSkillRegistry(self.path)
        self.records = [fictional_record('PA-001'), fictional_record('OL-001', ['PA-001'])]

    def tearDown(self): self.tmp.cleanup()

    def create(self, records=None):
        self.registry.create_snapshot('synthetic-snapshot', 'synthetic-source', 'synthetic-author',
                                      self.records if records is None else records)

    def test_snapshot_is_persisted_unchanged_and_immutable(self):
        self.create()
        self.records[0]['name'] = 'Altered after import'
        reopened = SyntheticSkillRegistry(self.path).get_snapshot('synthetic-snapshot')
        self.assertEqual(reopened['records'][0]['name'], 'Fictional fixture')
        with self.assertRaises(PolicyError): self.create([])
        self.assertEqual(reopened['records'][1]['prerequisite_skill_ids'], ['PA-001'])

    def test_missing_dependency_and_cycle_are_rejected(self):
        for records in ([fictional_record('PA-001', ['OL-001'])],
                        [fictional_record('PA-001', ['OL-001']), fictional_record('OL-001', ['PA-001'])]):
            with self.subTest(records=records):
                with self.assertRaises(PolicyError): self.create(records)
        with self.assertRaises(PolicyError): self.registry.get_snapshot('synthetic-snapshot')

    def test_duplicate_ids_and_preapproved_records_rejected(self):
        records = [fictional_record('PA-001'), fictional_record('PA-001')]
        with self.assertRaises(PolicyError): self.create(records)
        approved = fictional_record('PA-001'); approved['status'] = 'approved_for_production'
        with self.assertRaises(PolicyError): self.create([approved])
        supplied_review = fictional_record('PA-001'); supplied_review['review']['decision_ref'] = 'pretend-approval'
        with self.assertRaises(PolicyError): self.create([supplied_review])

    def test_review_is_separate_and_does_not_change_draft_status(self):
        self.create()
        with self.assertRaises(PolicyError):
            self.registry.record_synthetic_review('synthetic-snapshot', 'synthetic-author', 'approve_synthetic_review', 'note')
        self.registry.record_synthetic_review('synthetic-snapshot', 'synthetic-reviewer', 'approve_synthetic_review', 'reviewed fiction')
        self.assertEqual(self.registry.get_snapshot('synthetic-snapshot')['records'][0]['status'], 'draft')
        with self.assertRaises(PolicyError):
            self.registry.record_synthetic_review('synthetic-snapshot', 'synthetic-reviewer', 'approve_synthetic_review', 'again')

    def test_invalid_scope_and_structure_rejected(self):
        with self.assertRaises(PolicyError):
            self.registry.create_snapshot('actual-snapshot', 'synthetic-source', 'synthetic-author', self.records)
        invalid = copy.deepcopy(self.records); invalid[0]['domain_code'] = 'OL'
        with self.assertRaises(PolicyError): self.create(invalid)
        invalid = copy.deepcopy(self.records); invalid[0]['eligible_evidence'] = [{'task_condition': 'test'}]
        with self.assertRaises(PolicyError): self.create(invalid)


if __name__ == '__main__': unittest.main()
