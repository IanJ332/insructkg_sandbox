import os
from .grader import QUESTIONS, grade
from .feedback import generate_feedback, CompatibleProvider


def generate_question(data, qid):
    data['params']['statement'] = QUESTIONS[qid]['statement']
    # Built-in string element needs a value, but never place the reference SQL in answers/params.
    data['correct_answers']['sql'] = ''


def grade_question(data, qid):
    sql = data['submitted_answers'].get('sql', '')
    result = grade(qid, sql)
    provider = None
    if os.environ.get('SIIP_FEEDBACK_PROVIDER') == 'local':
        try:
            provider = CompatibleProvider(os.environ.get('SIIP_LLM_BASE_URL', 'http://host.docker.internal:8000/v1'),
                                          os.environ.get('SIIP_LLM_MODEL', 'local-model'))
        except ValueError:
            provider = None
    feedback = generate_feedback(qid, sql, result, mode='kg', provider=provider)
    data['score'] = float(result['score'])
    data['partial_scores']['sql'] = {'score': float(result['score']), 'weight': 1}
    data['feedback'].update({'status': result['status'], 'guidance': feedback['feedback_text'],
        'concepts': 'Possible concept gaps: ' + ', '.join(feedback['candidate_concepts']),
        'grounding': 'Lecture reference: ' + ', '.join(feedback['evidence_references']) +
                     '. KG prerequisites are developer provisional; original judgments await instructor review.',
        'inference': feedback['inference_status'] + ' · ' + feedback['model_identifier'],
        'siip': {'question_id': qid, 'grading_status': result['status'], 'observation': result['observation'],
                 'feedback': feedback}})
