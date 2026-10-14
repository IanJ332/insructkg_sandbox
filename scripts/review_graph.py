"""Explicit review overlay; never alters upstream research judgments."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'prairielearn-course/serverFilesCourse'))
from siip.grader import DATA
from siip.feedback import load_graphs
from siip.graph import ConceptGraph
parser=argparse.ArgumentParser()
parser.add_argument('record_id')
parser.add_argument('--status',choices=['unreviewed','accepted','rejected','modified'])
parser.add_argument('--reviewer')
parser.add_argument('--reason')
parser.add_argument('--source')
parser.add_argument('--target')
parser.add_argument('--relation',choices=['depends_on','part_of'])
args=parser.parse_args()
graph,_=load_graphs()
record=next((r for r in graph.records if r['id']==args.record_id),None)
if record is None:raise SystemExit('Unknown record ID; use graph review queue IDs')
if args.status is None:
    print(json.dumps(record,indent=2));raise SystemExit(0)
if not args.reviewer or not args.reason:raise SystemExit('Explicit reviewer and reason required; do not invent instructor approval')
if args.status=='modified' and (args.source not in graph.nodes or args.target not in graph.nodes or args.relation is None):
    raise SystemExit('Modification needs existing source/target concepts and relation')
path=DATA/'reviews.json'
reviews=json.loads(path.read_text()) if path.exists() else {}
reviews[args.record_id]={'status':args.status,'reviewer':args.reviewer,'reason':args.reason}
if args.status=='modified':reviews[args.record_id].update({'source':args.source,'target':args.target,'relation':args.relation})
verified=ConceptGraph(graph.path,graph.provenance,reviews)
if verified.errors:raise SystemExit(json.dumps(verified.errors))
path.write_text(json.dumps(reviews,indent=2)+'\n')
print('Saved separate review overlay; original research file unchanged. Rebuild graph audit and restart services to consume.')
