"""Authorized assessment presentation for fictional engineering fixtures only.

This boundary does not approve, create, score, diagnose, or validate an
instrument. The application must not expose fixture authoring or simulated
consent management to untrusted users. Existing identity, guardian, profile,
and separate assessment-consent checks are required for every operation.
"""
from prototype.lesson_engine import PolicyError
from prototype.synthetic_assessment import SyntheticAssessmentStore


class SyntheticAssessmentService:
    def __init__(self, store):
        self.assessments = SyntheticAssessmentStore(store)
        self.store = store

    @staticmethod
    def _metadata(form_id, version, form):
        if (not isinstance(form, dict) or form.get('language') not in ('en', 'es')
                or not isinstance(form.get('items'), list)):
            raise PolicyError('ASSESSMENT_INTEGRITY_FAILURE')
        return {'form_id': form_id, 'version': version, 'language': form['language'],
                'item_count': len(form['items']), 'validation_status': 'unvalidated'}

    def list_forms(self, token, student_id):
        """List intact, available fixture metadata only after assessment authorization."""
        with self.store._connect() as db:
            self.assessments._actor(db, token, student_id)
            entries = db.execute("SELECT form_id,version FROM synthetic_assessment_forms WHERE status='approved_for_prototype' ORDER BY form_id,version").fetchall()
            forms = []
            for form_id, version in entries:
                try:
                    form, _ = self.assessments._form(db, form_id, version)
                    forms.append(self._metadata(form_id, version, form))
                except (PolicyError, ValueError):
                    # Corrupt, withdrawn, or invalid fixture: do not serve it.
                    continue
            return {'forms': forms}

    def get_run(self, token, run_id):
        """Return an authorized pinned form only while its content remains available."""
        with self.store._connect() as db:
            row = db.execute('SELECT student_id,workspace_id,form_id,version,digest FROM synthetic_assessment_runs WHERE id=?', (run_id,)).fetchone()
            if not row:
                raise PolicyError('RESOURCE_NOT_FOUND')
            actor = self.assessments._actor(db, token, row[0])
            if actor.workspace_id != row[1]:
                raise PolicyError('RESOURCE_NOT_FOUND')
            form, _ = self.assessments._form(db, row[2], row[3], row[4])
            metadata = self._metadata(row[2], row[3], form)
            return {'id': run_id, **metadata, 'items': form['items']}

    def list_history(self, token, student_id):
        """Return limited history without delivering suspended or withdrawn items."""
        with self.store._connect() as db:
            actor = self.assessments._actor(db, token, student_id)
            rows = db.execute('''SELECT r.id,r.form_id,r.version,COUNT(a.id)
                FROM synthetic_assessment_runs r LEFT JOIN synthetic_assessment_responses a ON a.run_id=r.id
                WHERE r.student_id=? AND r.workspace_id=? GROUP BY r.id,r.form_id,r.version ORDER BY r.rowid DESC''',
                              (student_id, actor.workspace_id)).fetchall()
            return {'runs': [{'id': row[0], 'form_id': row[1], 'version': row[2],
                              'responses_recorded': row[3], 'validation_status': 'unvalidated'} for row in rows]}
