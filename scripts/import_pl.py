"""Import only a reviewed local synthetic PrairieLearn all-submissions CSV."""
import argparse
import csv
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'prairielearn-course/serverFilesCourse'))
from siip.store import SubmissionRepository
from siip.grader import QUESTIONS

parser=argparse.ArgumentParser()
parser.add_argument('csv',type=Path)
parser.add_argument('--local-synthetic-only',action='store_true',required=True)
args=parser.parse_args()
repo=SubmissionRepository(ROOT/'artifacts/synthetic.sqlite3')
processed=[]
for row in csv.DictReader(args.csv.open()):
    # Deliberately narrow demo mapping, never generalize to actual course identities.
    if row['UID']!='dev@example.com' or row['Question'] not in QUESTIONS:
        raise SystemExit('Export contains identity/question outside the local demo allowlist')
    if row['Assessment'] not in {'Homework 1'}:
        raise SystemExit('Export assessment does not match local demo HW1')
    answer=json.loads(row['Submitted answer'])
    record={'attempt_id':'local-pl-'+row['submission_id'],'student_id':'S003',
        'question_id':row['Question'],'timestamp':row['Submission date'],
        'submitted_sql':answer['sql'],'assessment_id':'sql-sandbox',
        'source':'local_prairielearn_export',
        'external_links':{'submission_id':row['submission_id'],'assessment_instance_number':row['Assessment instance'],
                          'variant_number':row['Variant']},
        'external_score':float(row['Score'])}
    output=repo.process(record)
    if output['grading']['score']!=record['external_score']:
        raise SystemExit('Recomputed score differs from actual PL score')
    processed.append(output)
(ROOT/'artifacts/pl_import_results.json').write_text(json.dumps(processed,indent=2)+'\n')
print(f'Imported {len(processed)} actual local PrairieLearn submissions into S003; no UID/name/UIN persisted in normalized records.')
print(json.dumps(repo.analytics(),indent=2))
