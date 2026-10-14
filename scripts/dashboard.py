"""Loopback-only synthetic instructor analytics and experiment viewer."""
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse
import uuid
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'prairielearn-course/serverFilesCourse'))
from siip.store import SubmissionRepository, STUDENTS
from siip.grader import QUESTIONS, grade
from siip.feedback import generate_feedback, load_graphs

REPO = SubmissionRepository(ROOT/'artifacts/synthetic.sqlite3')
STYLE = '''body{margin:0;background:#f2f5f7;color:#172b3a;font:16px/1.55 system-ui}header{background:#132e40;color:white;padding:28px 6%}main{max-width:1150px;margin:30px auto;padding:0 24px}h1{margin:0}h2{font-size:22px}a{color:#087674}nav a{color:#b9eeee;margin-right:22px}section,.card{background:white;border:1px solid #dce4e8;border-radius:12px;padding:22px;margin-bottom:22px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.metric{font-size:34px;font-weight:650}table{border-collapse:collapse;width:100%;text-align:left}td,th{padding:10px;border-bottom:1px solid #e4e9ec;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}summary{cursor:pointer;color:#087674}textarea{width:98%;height:100px;font:14px monospace}button{background:#087674;color:white;border:0;border-radius:6px;padding:12px 20px;cursor:pointer}select{padding:9px}small,.muted{color:#526672}.badge{background:#fff0d4;color:#744800;padding:3px 10px;border-radius:20px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}@media(max-width:760px){.cards,.grid{grid-template-columns:1fr}td,th{padding:6px}}'''

def esc(value): return html.escape(str(value))
def pretty(value): return '<pre>'+esc(json.dumps(value,indent=2))+'</pre>'
def table(headers, rows):
    return '<table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table>'
def shell(title,body):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+esc(title)+' · SIIP</title><style>'+STYLE+'</style><header><span class="badge">SYNTHETIC DATA · LOCAL RESEARCH</span><h1>SQL learning observatory</h1><p>PrairieLearn × InstructKG · JOINs and NULL semantics</p><nav><a href="/">Overview</a><a href="/students">Students</a><a href="/graph">Graph review</a><a href="/compare">Feedback lab</a><a href="http://localhost:3000/pl">PrairieLearn</a></nav></header><main>'+body+'</main></html>'

def overview():
    data=REPO.analytics()
    cards=''.join('<div class="card"><div class="metric">'+str(v)+'</div>'+esc(k)+'</div>' for k,v in [('Synthetic students',data['student_count']),('Attempts',data['attempt_count']),('Correct',data['correct']),('Needs revision',data['attempt_count']-data['correct'])])
    body='<div class="cards">'+cards+'</div><section><h2>Question performance</h2>'+table(['Question','Attempts','Correct'],[[esc(q),v['attempts'],v['correct']] for q,v in data['questions'].items()])+'</section>'
    body+='<section><h2>Concepts associated with errors</h2><p class="muted">Candidates inferred from task tags and observed errors. These are not confirmed misconceptions.</p>'+table(['Concept','Associated errors','Mean heuristic estimate'],[[esc(c),n,round(data['mean_mastery'].get(c,0),3)] for c,n in data['associated_error_concepts'].items()])+'</section>'
    body+='<section><h2>Source boundaries</h2>'+pretty(data['sources'])+'<p>PrairieLearn owns its real assessment history. Offline fixture attempts are labeled separately. Import only authorized local sandbox exports. No production data connection is active.</p></section>'
    return shell('Overview',body)

def students(sid=None):
    if sid is None:
        return shell('Students','<section><h2>Synthetic students</h2>'+''.join(f'<p><a href="/students?id={s}">{s}</a> · {REPO.profile(s)["attempt_count"]} attempts</p>' for s in STUDENTS)+'</section>')
    profile=REPO.profile(sid)
    body='<section><h2>'+esc(sid)+' · synthetic learning history</h2><p>'+esc(profile['model'])+'</p>'+table(['Concept','Attempts','Correct','Estimate','Prerequisites'],[[esc(c),p['attempt_count'],p['correct_count'],round(p['mastery_estimate'],3),esc(', '.join(p['prerequisites']))] for c,p in profile['concepts'].items()])+'</section>'
    body+='<section><h2>Attempt trajectory</h2>'+table(['Time (UTC)','Question','Result','Observed error','Source'],[[esc(a['timestamp']),esc(a['question_id']),esc(a['grading']['status']),esc(a['diagnosis']['observed_error']),esc(a['source'])] for a in profile['history']])+'</section>'
    body+='<section><h2>Add a synthetic attempt</h2><p>This form exercises the shared engine and updates this synthetic profile. Use the PrairieLearn link for actual platform submissions.</p><form method="post" action="/attempt"><input type="hidden" name="student_id" value="'+esc(sid)+'"><label>Question <select name="question_id">'+''.join('<option>'+q+'</option>' for q in QUESTIONS)+'</select></label><p><label>SQL query<textarea name="sql" required maxlength="12000"></textarea></label></p><button>Evaluate and update synthetic profile</button></form></section>'
    return shell('Student '+sid,body)

def graph_page():
    existing, provisional=load_graphs()
    body='<section><h2>Graph provenance and review queue</h2><p>'+str(len(existing.records))+' existing model judgments · '+str(len(existing.nodes))+' concepts · '+str(len(existing.edges(True)))+' unique non-null edges. Original graph includes multiple SQL lectures.</p><p class="badge">All original judgments remain unreviewed. Development edges are provisional.</p><p>Direction means source → target. A depends_on B means B is a prerequisite of A. No questionable edge is silently reversed.</p></section>'
    module=existing.evidence(['JOIN_OPERATION','LEFT_OUTER_JOIN'])
    body+='<section><h2>JOIN module judgments</h2>'
    for record in module:
        body+='<details><summary>'+esc(record['source']+' → '+str(record['relation'])+' → '+record['target'])+' · '+esc(record['review_status'])+'</summary>'+pretty(record)+'</details>'
    body+='</section><section><h2>Developer provisional dependencies</h2>'+table(['Source','Relation','Target'],[[esc(e['source']),esc(e['relation']),esc(e['target'])] for e in provisional.edges(True)])+'</section>'
    body+='<section><h2>Full original judgment inventory</h2>'
    for rec in existing.records:
        body+='<details><summary>'+esc(f"{rec['id']} · {rec['source']} → {rec['relation']} → {rec['target']}")+'</summary>'+pretty(rec)+'</details>'
    return shell('Graph review',body+'</section>')

def compare(params):
    qid=params.get('question_id',['sql_join_02'])[0]
    sql=params.get('sql',[QUESTIONS['sql_join_01']['reference_sql']])[0]
    result=grade(qid,sql)
    body='<section><h2>Feedback comparison lab</h2><p>All three outputs below use deterministic development fallback. Live LLM comparison is pending model resources; these are not inference-quality measurements.</p><form><label>Question <select name="question_id">'+''.join('<option '+('selected' if q==qid else '')+'>'+q+'</option>' for q in QUESTIONS)+'</select></label><p><label>Submitted SQL<textarea name="sql" maxlength="12000">'+esc(sql)+'</textarea></label></p><button>Compare contexts</button></form></section><div class="grid">'
    for mode in ['baseline','rag','kg']:
        feedback=generate_feedback(qid,sql,result,mode)
        body+='<section><h2>'+mode.upper()+'</h2><p>'+esc(feedback['feedback_text'])+'</p><p>'+esc(', '.join(feedback['evidence_references']))+'</p><small>'+esc(feedback['inference_status'])+'</small></section>'
    return shell('Feedback lab',body+'</div>')

class Handler(BaseHTTPRequestHandler):
    def send(self,body,status=200,content='text/html; charset=utf-8'):
        self.send_response(status);self.send_header('Content-Type',content);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");self.end_headers();self.wfile.write(body.encode())
    def do_GET(self):
        parsed=urlparse(self.path);params=parse_qs(parsed.query)
        try:
            if parsed.path=='/': self.send(overview())
            elif parsed.path=='/students': self.send(students(params.get('id',[None])[0]))
            elif parsed.path=='/graph': self.send(graph_page())
            elif parsed.path=='/compare': self.send(compare(params))
            elif parsed.path=='/api/analytics':self.send(json.dumps(REPO.analytics()),content='application/json')
            elif parsed.path=='/health':self.send('{"status":"ok","synthetic":true}',content='application/json')
            else:self.send('Not found',404)
        except (ValueError,KeyError):self.send('Invalid input',400)
    def do_POST(self):
        if self.headers.get('Origin') not in {None,'http://127.0.0.1:8080','http://localhost:8080'}:
            return self.send('Forbidden origin',403)
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':return self.send('Forbidden origin',403)
        size=int(self.headers.get('Content-Length','0'))
        if size>16000:return self.send('Request too large',413)
        params=parse_qs(self.rfile.read(size).decode())
        try:
            if self.path!='/attempt':return self.send('Not found',404)
            sid=params['student_id'][0]
            result=REPO.process({'student_id':sid,'question_id':params['question_id'][0],
                'submitted_sql':params['sql'][0],'timestamp':datetime.now(timezone.utc).isoformat(),
                'attempt_id':'demo-'+str(uuid.uuid4()),'source':'synthetic_fixture'})
            self.send(shell('Attempt recorded','<section><h2>'+esc(result['grading']['status'])+'</h2><p>'+esc(result['feedback']['feedback_text'])+'</p><p><a href="/students?id='+esc(sid)+'">View updated synthetic profile</a></p></section>'))
        except (ValueError,KeyError):self.send('Invalid input',400)

if __name__=='__main__':
    print('Synthetic analytics: http://127.0.0.1:8080',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8080),Handler).serve_forever()
