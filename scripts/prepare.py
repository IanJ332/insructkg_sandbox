"""Rebuild local fixtures and course; preserve the upstream PDF and raw graph."""
import hashlib
import json
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
COURSE = ROOT / 'prairielearn-course'
DATA = COURSE / 'serverFilesCourse/siip/data'

def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + '\n')

def stable_id(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'siip-local-sandbox/' + name))

questions = {
    'sql_join_01': {'title': 'Matching employees and departments',
                    'statement': 'Retrieve employees who have a matching department record. Return employee name and department_name, in that column order.',
                    'concepts': ['INNER_JOIN', 'JOIN_CONDITION', 'JOIN_OPERATION'],
                    'reference_sql': 'SELECT e.name, d.department_name FROM Employees e INNER JOIN Departments d ON e.department_id=d.department_id;'},
    'sql_join_02': {'title': 'Keep every employee',
                    'statement': 'Retrieve every employee, including employees without matching departments. Return employee name and department_name, in that column order.',
                    'concepts': ['LEFT_OUTER_JOIN', 'UNMATCHED_ROWS', 'NULL_SEMANTICS'],
                    'reference_sql': 'SELECT e.name, d.department_name FROM Employees e LEFT JOIN Departments d ON e.department_id=d.department_id;'},
    'sql_join_03': {'title': 'Find employees without a department match',
                    'statement': 'Retrieve the names of employees for whom no matching department record exists. Return one column: name. Include both NULL references and non-NULL references with no match.',
                    'concepts': ['LEFT_OUTER_JOIN', 'IS_NULL', 'FILTERING_AFTER_JOIN'],
                    'reference_sql': 'SELECT e.name FROM Employees e LEFT JOIN Departments d ON e.department_id=d.department_id WHERE d.department_id IS NULL;'}
}
write(DATA / 'questions.json', questions)
write(ROOT / 'datasets/questions/questions.json', questions)
base = '''CREATE TABLE Employees(employee_id INTEGER PRIMARY KEY, name TEXT NOT NULL, department_id INTEGER);
CREATE TABLE Departments(department_id INTEGER PRIMARY KEY, department_name TEXT NOT NULL);
INSERT INTO Employees VALUES (1,'Alice',10),(2,'Bob',20),(3,'Carol',NULL),(4,'David',10);
INSERT INTO Departments VALUES (10,'Engineering'),(20,'Sales'),(30,'Research');
'''
for dataset in ['A', 'B']:
    text = base
    if dataset == 'B':
        text += "INSERT INTO Employees VALUES (5,'Erin',30),(6,'Frank',NULL),(7,'Gina',99);\nINSERT INTO Departments VALUES (40,'Operations');\n"
    (DATA / f'dataset_{dataset}.sql').write_text(text)

write(COURSE / 'infoCourse.json', {'uuid': stable_id('course'), 'name': 'SIIP SQL',
    'title': 'SIIP Synthetic SQL Research Sandbox', 'timezone': 'America/Chicago',
    'topics': [{'name': 'SQL', 'color': 'blue1', 'description': 'JOINs and NULL semantics'}],
    'tags': [{'name': 'synthetic', 'color': 'gray1', 'description': 'Synthetic local research'}]})
write(COURSE / 'courseInstances/Fall2026/infoCourseInstance.json',
      {'uuid': stable_id('Fall2026'), 'longName': 'Fall 2026 Synthetic Sandbox',
       'publishing': {'startDate': '2026-01-01T00:00:00', 'endDate': '2027-12-31T23:59:59'}})
write(COURSE / 'courseInstances/Fall2026/assessments/sql-sandbox/infoAssessment.json', {
    'uuid': stable_id('assessment'), 'type': 'Homework', 'title': 'SQL Concept-Aware Feedback Sandbox',
    'set': 'Homework', 'number': '1', 'allowAccess': [{'startDate': '2026-01-01T00:00:00', 'endDate': '2027-12-31T23:59:59', 'credit': 100}],
    'zones': [{'title': 'SQL JOINs and NULL Semantics', 'questions': [{'id': k, 'points': 1} for k in questions]}]})
for qid, q in questions.items():
    folder = COURSE / 'questions' / qid
    write(folder / 'info.json', {'uuid': stable_id(qid), 'title': q['title'], 'topic': 'SQL', 'tags': ['synthetic'], 'type': 'v3', 'singleVariant': True})
    (folder / 'server.py').write_text(f'''from siip.pl_bridge import generate_question, grade_question

def generate(data):
    generate_question(data, "{qid}")

def grade(data):
    grade_question(data, "{qid}")
''')
    (folder / 'question.html').write_text('''<pl-question-panel>
<h2>SQL JOINs and NULL Semantics</h2>
<p>{{params.statement}}</p>
<p>SQLite dialect. Read-only SELECT queries only. Row order is ignored; duplicate rows count.</p>
<p>Employees(employee_id INTEGER, name TEXT, department_id INTEGER);<br>
Departments(department_id INTEGER, department_name TEXT).</p>
<p>Example data: Alice → 10, Bob → 20, Carol → NULL, David → 10.
Departments: 10 Engineering, 20 Sales, 30 Research. Additional private cases test unmatched references.</p>
<p>This is a synthetic local research sandbox. Graph additions are provisional pending instructor review.</p>
</pl-question-panel>
<pl-string-input answers-name="sql" multiline="true" aria-label="SQL query" placeholder="Enter your SELECT query" show-help-text="false"></pl-string-input>
<pl-submission-panel>
<div class="alert alert-info" role="status">
<p><strong>{{feedback.status}}</strong></p>
<p>{{feedback.guidance}}</p>
<p>{{feedback.concepts}}</p>
<p>{{feedback.grounding}}</p>
<p><small>{{feedback.inference}}</small></p>
</div>
</pl-submission-panel>
<pl-answer-panel><p>Review the feedback and reason about which rows the query must preserve. A complete solution is withheld in this sandbox.</p></pl-answer-panel>
''')

research = ROOT / 'research/instructkg-jeffry'
graph = research / 'out/relations_sql_qwen14b.jsonl'
(DATA / 'existing_relations.jsonl').write_bytes(graph.read_bytes())
commit = subprocess.check_output(['git', '-C', str(research), 'rev-parse', 'HEAD'], text=True).strip()
write(DATA / 'provenance.json', {'kind': 'existing_model_generated', 'repo': 'https://github.com/code-royce/instructkg',
    'commit': commit, 'file': 'out/relations_sql_qwen14b.jsonl',
    'scope': 'Multiple SQL lectures, not solely the available JOIN PDF',
    'model': 'qwen14b (filename attribution; per-record model metadata absent)'})
concepts = sorted({c for q in questions.values() for c in q['concepts']} | {'SQL_SELECT', 'RELATIONAL_TABLES'})
provisional = [
    ('INNER_JOIN', 'JOIN_CONDITION', 'depends_on'), ('LEFT_OUTER_JOIN', 'JOIN_CONDITION', 'depends_on'),
    ('JOIN_CONDITION', 'RELATIONAL_TABLES', 'depends_on'), ('JOIN_OPERATION', 'RELATIONAL_TABLES', 'depends_on'),
    ('UNMATCHED_ROWS', 'LEFT_OUTER_JOIN', 'depends_on'), ('IS_NULL', 'NULL_SEMANTICS', 'depends_on'),
    ('FILTERING_AFTER_JOIN', 'IS_NULL', 'depends_on'), ('NULL_SEMANTICS', 'SQL_SELECT', 'depends_on')]
(DATA / 'provisional_relations.jsonl').write_text(''.join(json.dumps({
    'A': {'name': a, 'role': 'NA'}, 'B': {'name': b, 'role': 'NA'}, 'relation': rel,
    'justification': 'Developer-created teaching dependency; pending instructor approval.', 'evidence_chunks': [],
    '_meta': {'kind': 'developer_provisional'}}) + '\n' for a,b,rel in provisional))
write(DATA / 'mapping.json', {'review_status': 'developer_validated_pending_instructor', 'reviewer': 'local sandbox developer',
    'source': 'Exercise requirements and inspected JOIN/NULL lecture; exact conceptual names are developer annotations',
    'questions': {k: q['concepts'] for k,q in questions.items()},
    'aliases': {'INNER_JOIN': 'JOIN_OPERATION'}, 'provisional_concepts': concepts})

from pypdf import PdfReader
pdf = research / 'data/sql/3-SQL2-JOINS_Nulls.pdf'
lecture = []
for i, page in enumerate(PdfReader(pdf).pages, 1):
    text = page.extract_text() or ''
    if text.strip():
        lecture.append({'id': f'lecture:joins-null:p{i}', 'page': i, 'text': text,
                        'source_pdf': 'data/sql/3-SQL2-JOINS_Nulls.pdf', 'repo_commit': commit,
                        'sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(), 'extraction': 'pypdf native text (not InstructKG)'})
write(DATA / 'lecture.json', lecture)
write(ROOT / 'artifacts/input_manifest.json', {'lecture_pages_with_text': len(lecture),
    'pdf_sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(), 'graph_sha256': hashlib.sha256(graph.read_bytes()).hexdigest(),
    'repos': {name: subprocess.check_output(['git', '-C', str(ROOT/'research'/name), 'rev-parse', 'HEAD'], text=True).strip()
              for name in ['instructkg-jeffry','instructkg-reference','PrairieLearn']}})
print(f'Prepared {len(questions)} questions, 2 teaching databases, {len(lecture)} PDF pages, existing and provisional graphs.')
