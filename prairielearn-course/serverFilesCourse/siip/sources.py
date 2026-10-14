"""Read-only input boundaries; no fabricated PrairieLearn submission writes."""
import hashlib
import hmac
import json
from pathlib import Path
from typing import Protocol
import urllib.request
from .grader import QUESTIONS


class SubmissionSource(Protocol):
    def records(self): ...


class SyntheticFixtureSource:
    def __init__(self, path): self.path = Path(path)
    def records(self):
        return json.loads(self.path.read_text())


def normalize_pl(record, identity_map):
    """Fields verified against official SubmissionDataSchema. Never persist names/UID/UIN."""
    sid = identity_map.get(str(record.get('user_id')))
    if sid is None:
        raise ValueError('Missing authorized pseudonymous identity mapping; team records need separate approval')
    qid = record.get('question_name')
    if qid not in QUESTIONS:
        raise ValueError('Question outside sandbox allowlist')
    answer = record.get('submitted_answer')
    if not isinstance(answer, dict) or not isinstance(answer.get('sql'), str):
        raise ValueError('Unsupported submitted_answer mapping')
    return {'student_id': sid, 'question_id': qid, 'attempt_id': 'pl-' + str(record['submission_id']),
            'timestamp': record['date'], 'submitted_sql': answer['sql'],
            'assessment_id': str(record['assessment_id']),
            'external_links': {k: str(record[k]) for k in ['assessment_instance_id','variant_id','submission_id']},
            'external_score': record.get('score')}


class LocalPrairieLearnSource:
    """Consumes authorized export files, not a connection to PL's internal database."""
    def __init__(self, path, identity_map):
        self.path, self.identity_map = Path(path), identity_map
    def records(self):
        return [{**normalize_pl(row, self.identity_map), 'source': 'local_prairielearn_export'}
                for row in json.loads(self.path.read_text())]


class AuthorizedPrairieLearnAPISource:
    def __init__(self, base_url, token, course_instance_id, assessment_instance_id, identity_map, authorized=False):
        if not authorized:
            raise PermissionError('Explicit authorization and course-instance scope required')
        if not str(course_instance_id).isdigit() or not str(assessment_instance_id).isdigit():
            raise ValueError('Numeric PrairieLearn IDs required')
        self.url = (base_url.rstrip('/') + '/pl/api/v1/course_instances/' + str(course_instance_id) +
                    '/assessment_instances/' + str(assessment_instance_id) + '/submissions')
        self.token, self.identity_map = token, identity_map
    def records(self):
        request = urllib.request.Request(self.url, headers={'Private-Token': self.token})
        with urllib.request.urlopen(request, timeout=10) as response:
            rows = json.load(response)
        return [{**normalize_pl(row, self.identity_map), 'source': 'authorized_prairielearn_api'} for row in rows]


def pseudonym(user_id, secret):
    if len(secret) < 32:
        raise ValueError('Use an approved secret of at least 32 bytes')
    return hmac.new(secret, str(user_id).encode(), hashlib.sha256).hexdigest()[:24]
