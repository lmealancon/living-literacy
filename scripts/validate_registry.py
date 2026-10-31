#!/usr/bin/env python3
"""Check domain manifest and imported candidate records; never confer approval."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
m=json.loads((ROOT/'registry/DOMAIN_MANIFEST.json').read_text())
r=json.loads((ROOT/'registry/SKILL_REGISTRY.json').read_text())
assert len(m['domains'])==12
assert sum(d['candidate_count'] for d in m['domains'])==m['expected_candidate_count']==91
assert sum(d['candidate_count'] for d in m['domains'] if d['strand']=='word_recognition')==49
assert sum(d['candidate_count'] for d in m['domains'] if d['strand']=='language_comprehension')==42
skills=r['skills']; keys=[(s['skill_id'],s['version']) for s in skills]
assert len(keys)==len(set(keys)), 'duplicate skill version'
known={s['skill_id'] for s in skills}
for s in skills:
    assert s['domain_code'] in {d['code'] for d in m['domains']}
    assert all(dep in known for dep in s['prerequisite_skill_ids']), 'missing dependency'
    assert s['status']!='approved_for_production' or s['review']['decision_ref'], 'unreviewed production skill'
# cycle check by skill ID across current imported candidates
graph={s['skill_id']:s['prerequisite_skill_ids'] for s in skills}; active=set(); seen=set()
def visit(n):
    if n in active: raise AssertionError('dependency cycle')
    if n in seen: return
    active.add(n)
    for d in graph[n]: visit(d)
    active.remove(n);seen.add(n)
for n in graph: visit(n)
print(f'Manifest OK: 12 domains, 91 candidate count; imported skill records: {len(skills)}.')
if not skills: print('EXPECTED BLOCKER: canonical definitions absent; no skills approved or imported.')
