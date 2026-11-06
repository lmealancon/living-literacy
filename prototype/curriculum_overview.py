"""Read the supplied draft domain manifest without inventing skill definitions.

The overview is descriptive only. It does not approve skills, provide an
assessment, make recommendations, or determine a learner's abilities.
"""
import json
from pathlib import Path

from prototype.lesson_engine import PolicyError

MANIFEST = Path(__file__).resolve().parents[1] / 'registry' / 'DOMAIN_MANIFEST.json'


def candidate_domains(path=MANIFEST):
    """Return the existing candidate domain names; reject missing or malformed data."""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if (not isinstance(data, dict) or data.get('status') != 'candidate_counts_only'
                or data.get('canonical_skill_definitions_present') is not False
                or not isinstance(data.get('domains'), list) or len(data['domains']) != 12):
            raise ValueError('invalid manifest')
        domains = []
        for row in data['domains']:
            if (not isinstance(row, dict) or not isinstance(row.get('code'), str)
                    or not isinstance(row.get('name'), str) or not row['name'].strip()
                    or row.get('strand') not in ('word_recognition', 'language_comprehension')
                    or type(row.get('candidate_count')) is not int or row['candidate_count'] < 0):
                raise ValueError('invalid domain')
            domains.append({k: row[k] for k in ('code', 'name', 'strand', 'candidate_count')})
        if len({row['code'] for row in domains}) != len(domains):
            raise ValueError('duplicate domain')
        if {row['strand'] for row in domains} != {'word_recognition', 'language_comprehension'}:
            raise ValueError('missing strand')
        if sum(row['candidate_count'] for row in domains) != data.get('expected_candidate_count'):
            raise ValueError('invalid count')
        return {'status': 'candidate_counts_only', 'canonical_skill_definitions_present': False,
                'domains': domains}
    except (OSError, TypeError, ValueError, UnicodeError) as exc:
        raise PolicyError('CURRICULUM_OVERVIEW_UNAVAILABLE') from exc
