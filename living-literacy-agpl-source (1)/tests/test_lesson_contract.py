import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STAGES=['activate','model','guide','practice','apply_independently','review']
class LessonContractTests(unittest.TestCase):
    def test_schema_has_six_fixed_stages(self):
        s=json.loads((ROOT/'contracts/LESSON_RECORD.schema.json').read_text())
        stages=s['properties']['stages']
        self.assertEqual(stages['minItems'],6)
        self.assertEqual(stages['maxItems'],6)
        self.assertEqual([x['const'] for x in stages['prefixItems']],STAGES)
        self.assertFalse(stages['items'])
    def test_mastery_is_disabled(self):
        s=json.loads((ROOT/'contracts/LESSON_RECORD.schema.json').read_text())
        policy=s['properties']['evidence_policy']['properties']
        self.assertIs(policy['completion_is_mastery']['const'],False)
        self.assertIs(policy['auto_mastery_enabled']['const'],False)
    def test_canonical_registry_not_misrepresented(self):
        r=json.loads((ROOT/'registry/SKILL_REGISTRY.json').read_text())
        self.assertEqual(r['skills'],[])
        self.assertEqual(r['status'],'awaiting_source_inventory')
    def test_subscription_prices(self):
        p=json.loads((ROOT/'contracts/PLAN_CATALOG.json').read_text())
        self.assertEqual(p['family_plus']['monthly_usd_cents'],999)
        self.assertEqual(p['solo_educator']['monthly_usd_cents'],1999)
        self.assertFalse(p['solo_educator']['student_roster_authority_included'])
if __name__=='__main__': unittest.main()
