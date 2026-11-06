"""Fictional fixtures test infrastructure, not real skill definitions."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from prototype.lesson_engine import PolicyError
from prototype.skill_registry import SyntheticSkillRegistry, verify_snapshot_export


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

    def test_export_round_trip_is_stable_and_does_not_export_review_approval(self):
        self.create()
        self.registry.record_synthetic_review('synthetic-snapshot', 'synthetic-reviewer',
                                              'approve_synthetic_review', 'fixture only')
        envelope = self.registry.export_snapshot('synthetic-snapshot')
        self.assertEqual(envelope, self.registry.export_snapshot('synthetic-snapshot'))
        snapshot = verify_snapshot_export(envelope)
        self.assertEqual(snapshot['source_ref'], 'synthetic-source')
        self.assertEqual(snapshot['records'], self.records)
        self.assertEqual(set(envelope['payload']['snapshot']), {'snapshot_id', 'source_ref', 'author_ref', 'records'})
        self.assertTrue(all(record['status'] == 'draft' for record in snapshot['records']))
        snapshot['records'][0]['name'] = 'changed copy'
        self.assertEqual(envelope['payload']['snapshot']['records'][0]['name'], 'Fictional fixture')

    def test_export_integrity_rejects_mutation_bad_fields_and_db_corruption(self):
        self.create()
        envelope = self.registry.export_snapshot('synthetic-snapshot')
        for mutant in (None, {'payload': envelope['payload'], 'sha256': '0' * 64},
                       {**envelope, 'extra': True}, {**envelope, 'sha256': 'x' * 64}):
            with self.subTest(mutant=mutant), self.assertRaises(PolicyError):
                verify_snapshot_export(mutant)
        altered = copy.deepcopy(envelope)
        altered['payload']['snapshot']['records'][0]['name'] = 'Tampered'
        with self.assertRaises(PolicyError): verify_snapshot_export(altered)
        # A recomputed checksum is not approval; schema and synthetic scope
        # still have to pass even if the envelope was intentionally rewritten.
        altered['payload']['snapshot']['records'][0]['status'] = 'approved_for_production'
        raw = json.dumps(altered['payload'], sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        altered['sha256'] = hashlib.sha256(raw.encode('utf-8')).hexdigest()
        with self.assertRaises(PolicyError): verify_snapshot_export(altered)
        with self.registry._connect() as db:
            db.execute("UPDATE skill_snapshots SET records_json='not-json' WHERE snapshot_id=?", ('synthetic-snapshot',))
        with self.assertRaises(PolicyError): self.registry.export_snapshot('synthetic-snapshot')

    def test_dependency_view_reports_declared_edges_without_strand_lock(self):
        self.create()
        view = self.registry.dependency_view('synthetic-snapshot')
        by_id = {item['skill_id']: item for item in view['skills']}
        self.assertEqual(by_id['PA-001']['strand'], 'word_recognition')
        self.assertEqual(by_id['PA-001']['declared_dependencies'], [])
        self.assertEqual(by_id['OL-001']['strand'], 'language_comprehension')
        self.assertEqual(by_id['OL-001']['declared_dependencies'],
                         [{'skill_id': 'PA-001', 'strand': 'word_recognition', 'cross_strand': True}])
        self.assertNotIn('unlocked', by_id['OL-001'])
        self.assertIn('no eligibility', view['note'])

    def test_empty_draft_snapshot_does_not_invent_skills(self):
        self.create([])
        self.assertEqual(self.registry.dependency_view('synthetic-snapshot')['skills'], [])
        self.assertEqual(verify_snapshot_export(self.registry.export_snapshot('synthetic-snapshot'))['records'], [])


if __name__ == '__main__': unittest.main()
