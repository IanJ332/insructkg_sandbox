"""Persistent research records. SQLite repository can be replaced by PostgreSQL."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from .grader import QUESTIONS, grade
from .feedback import diagnosis, generate_feedback, load_graphs

STUDENTS = ['S001', 'S002', 'S003', 'S004', 'S005']


def utc_timestamp(value):
    timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if timestamp.tzinfo is None:
        raise ValueError('Timestamp requires a timezone')
    return timestamp.astimezone(timezone.utc).isoformat()


class SubmissionRepository:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
                INSERT OR IGNORE INTO schema_version VALUES(1);
                CREATE TABLE IF NOT EXISTS attempts(
                    attempt_id TEXT PRIMARY KEY, student_id TEXT NOT NULL,
                    question_id TEXT NOT NULL, timestamp TEXT NOT NULL, source TEXT NOT NULL,
                    assessment_id TEXT NOT NULL, record TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS attempts_student_time ON attempts(student_id,timestamp);''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def process(self, record, mode='kg', provider=None):
        sid, qid = record['student_id'], record['question_id']
        if sid not in STUDENTS or qid not in QUESTIONS:
            raise ValueError('Unknown synthetic identity or question')
        timestamp = utc_timestamp(record['timestamp'])
        aid = record['attempt_id']
        if not isinstance(aid, str) or not aid:
            raise ValueError('Attempt ID required')
        if record.get('source', 'synthetic_fixture') not in {'synthetic_fixture', 'local_prairielearn_export', 'authorized_prairielearn_api'}:
            raise ValueError('Unknown submission source')
        with self.connect() as db:
            existing = db.execute('SELECT record FROM attempts WHERE attempt_id=?', (aid,)).fetchone()
        if existing:
            saved = json.loads(existing[0])
            if any(saved[k] != record[k] for k in ['student_id', 'question_id', 'submitted_sql']):
                raise ValueError('Attempt ID collision')
            return saved
        result = grade(qid, record['submitted_sql'])
        history = self.profile(sid)
        feedback = generate_feedback(qid, record['submitted_sql'], result, mode, history['concepts'], provider)
        output = {**record, 'timestamp': timestamp, 'source': record.get('source', 'synthetic_fixture'),
            'assessment_id': record.get('assessment_id', 'sql-sandbox'),
            'grading': result, 'diagnosis': diagnosis(qid, result),
            'concepts': QUESTIONS[qid]['concepts'], 'feedback_mode': mode, 'feedback': feedback,
            'dataset_version': 'employees-departments-v1', 'profile_version': 'beta-heuristic-v1'}
        with self.connect() as db:
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?,?)',
                (aid, sid, qid, timestamp, output['source'], output['assessment_id'], json.dumps(output)))
        return output

    def records(self, student_id=None):
        with self.connect() as db:
            if student_id is None:
                rows = db.execute('SELECT record FROM attempts ORDER BY timestamp,attempt_id').fetchall()
            else:
                rows = db.execute('SELECT record FROM attempts WHERE student_id=? ORDER BY timestamp,attempt_id', (student_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def profile(self, student_id):
        if student_id not in STUDENTS:
            raise ValueError('Unknown student')
        records = self.records(student_id)
        grouped = defaultdict(list)
        for record in records:
            for concept in record['concepts']:
                grouped[concept].append(record)
        _, provisional = load_graphs()
        concepts = {}
        for concept, attempts in sorted(grouped.items()):
            correct = sum(a['grading']['score'] for a in attempts)
            # Each question contributes its latest attempt, preventing retry volume dominance.
            latest = {a['question_id']: a for a in attempts if a['grading']['status'] in {'correct', 'semantic_error'}}
            latest_correct = sum(a['grading']['score'] for a in latest.values())
            estimate = (1 + latest_correct) / (2 + len(latest))
            errors = Counter(a['diagnosis']['observed_error'] for a in attempts if not a['grading']['score'])
            concepts[concept] = {'attempt_count': len(attempts), 'correct_count': correct,
                'incorrect_count': len(attempts)-correct, 'last_attempt': attempts[-1]['timestamp'],
                'questions': sorted({a['question_id'] for a in attempts}), 'observed_errors': dict(errors), 'mastery_estimate': estimate,
                'denominator': len(latest), 'prerequisites': provisional.prerequisites(concept, 2, True),
                'trajectory': [{'timestamp': a['timestamp'], 'question_id': a['question_id'], 'score': a['grading']['score']} for a in attempts]}
        for concept, profile in concepts.items():
            profile['prerequisite_context'] = [
                {'concept': prerequisite, 'mastery_estimate': concepts.get(prerequisite, {}).get('mastery_estimate'),
                 'status': 'possible_gap' if concepts.get(prerequisite, {}).get('mastery_estimate', 1) < 0.5 else
                           ('observed' if prerequisite in concepts else 'unobserved')}
                for prerequisite in profile['prerequisites']]
        return {'student_id': student_id, 'synthetic': True, 'attempt_count': len(records),
                'concepts': concepts, 'history': records,
                'model': 'Beta(1,1) smoothing on latest result per linked question; unvalidated heuristic'}

    def analytics(self):
        records = self.records()
        questions = {}
        for qid in QUESTIONS:
            rows = [a for a in records if a['question_id'] == qid]
            questions[qid] = {'attempts': len(rows), 'correct': sum(a['grading']['score'] for a in rows)}
        errors = Counter(c for a in records if not a['grading']['score'] for c in a['diagnosis']['candidate_concepts'])
        concept_profiles = defaultdict(list)
        for sid in STUDENTS:
            for c, p in self.profile(sid)['concepts'].items():
                concept_profiles[c].append(p['mastery_estimate'])
        return {'synthetic': True, 'student_count': len(STUDENTS), 'attempt_count': len(records),
                'correct': sum(a['grading']['score'] for a in records), 'questions': questions,
                'associated_error_concepts': dict(errors.most_common()),
                'mean_mastery': {c: sum(v)/len(v) for c,v in concept_profiles.items()},
                'sources': dict(Counter(a['source'] for a in records))}
