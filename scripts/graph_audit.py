import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'prairielearn-course/serverFilesCourse'))
from siip.feedback import load_graphs
existing,provisional=load_graphs()
queue=[]
for r in existing.records:
    flags=[]
    if r['source']=='JOIN_OPERATION' and r['target']=='LEFT_OUTER_JOIN' and r['relation']=='part_of':
        flags.append('Justification describes broader source and narrower target; inspect compositional direction.')
    if r['invalid_inference']:flags.append('Invalid model response metadata')
    if not r['evidence']:flags.append('No evidence')
    queue.append({**r,'review_flags':flags})
(ROOT/'datasets/knowledge-graphs/review_queue.json').write_text(json.dumps(queue,indent=2)+'\n')
summary={'records':len(existing.records),'nodes':len(existing.nodes),
    'nonnull_records':sum(r['relation'] is not None for r in existing.records),
    'null_records':sum(r['relation'] is None for r in existing.records),
    'duplicate_records':existing.duplicates,'parse_errors':existing.errors,
    'flagged':sum(bool(r['review_flags']) for r in queue),'instructor_accepted':len(existing.edges()),
    'developer_provisional_edges':len(provisional.edges(True))}
(ROOT/'artifacts/graph_audit.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
