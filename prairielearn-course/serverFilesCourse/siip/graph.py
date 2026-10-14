import copy
import hashlib
import json
from pathlib import Path

ALLOWED = {'depends_on', 'part_of'}
STATUSES = {'unreviewed', 'accepted', 'rejected', 'modified'}


class ConceptGraph:
    def __init__(self, path, provenance=None, reviews=None):
        self.nodes, self.records, self.errors, self.duplicates = {}, [], [], []
        self.path = Path(path)
        self.provenance = provenance or {'kind': 'existing_model_generated', 'file': str(path)}
        self.sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        seen = set()
        for line_no, line in enumerate(self.path.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                a, b = raw['A']['name'], raw['B']['name']
                if not isinstance(a, str) or not a or not isinstance(b, str) or not b:
                    raise ValueError('Missing concept')
                relation = raw.get('relation')
                if isinstance(relation, str):
                    relation = relation.strip().lower().replace('-', '_').replace(' ', '_')
                    if relation in {'null', 'none', ''}:
                        relation = None
                if relation is not None and relation not in ALLOWED:
                    raise ValueError('Unsupported relation')
                if not isinstance(raw.get('evidence_chunks', []), list):
                    raise ValueError('Invalid evidence')
                for key in ['A', 'B']:
                    node = raw[key]
                    self.nodes.setdefault(node['name'], {'id': node['name'], 'roles': []})
                    role = node.get('role', 'NA')
                    if role not in self.nodes[node['name']]['roles']:
                        self.nodes[node['name']]['roles'].append(role)
                record_id = f'{self.sha256[:12]}:{line_no}'
                overlay = (reviews or {}).get(record_id, {})
                status = overlay.get('status', 'unreviewed')
                if status not in STATUSES:
                    raise ValueError('Invalid review status')
                if status == 'modified' and (not overlay.get('reviewer') or not overlay.get('reason') or
                    overlay.get('source') not in self.nodes or overlay.get('target') not in self.nodes or
                    overlay.get('relation') not in ALLOWED):
                    raise ValueError('Modification needs known concepts, relation, reviewer and reason')
                rec = {'id': record_id, 'source': a, 'target': b, 'relation': relation,
                       'original_direction': [a, b], 'review_status': status,
                       'provenance': {**self.provenance, 'sha256': self.sha256, 'line': line_no},
                       'evidence': raw.get('evidence_chunks', []), 'justification': raw.get('justification', ''),
                       'raw': raw, 'review': overlay,
                       'invalid_inference': bool(raw.get('_meta', {}).get('_error'))}
                signature = (a, b, relation)
                if signature in seen:
                    self.duplicates.append(record_id)
                seen.add(signature)
                self.records.append(rec)
            except (KeyError, TypeError, ValueError) as exc:
                self.errors.append({'line': line_no, 'error': str(exc)})

    def edges(self, include_unreviewed=False):
        result, seen = [], set()
        for rec in self.records:
            if rec['invalid_inference'] or rec['review_status'] == 'rejected':
                continue
            edge = copy.deepcopy(rec)
            if edge['review_status'] == 'modified':
                edge.update({k: edge['review'][k] for k in ['source', 'target', 'relation']})
            if not edge['relation'] or (not include_unreviewed and edge['review_status'] not in {'accepted', 'modified'}):
                continue
            signature = (edge['source'], edge['target'], edge['relation'])
            if signature not in seen:
                result.append(edge)
                seen.add(signature)
        return result

    def prerequisites(self, concept, depth=2, include_unreviewed=False):
        if not 0 <= depth <= 4:
            raise ValueError('Traversal depth must be 0–4')
        found, frontier = set(), {concept}
        for _ in range(depth):
            new = {e['target'] for e in self.edges(include_unreviewed)
                   if e['relation'] == 'depends_on' and e['source'] in frontier}
            new -= found | {concept}
            found |= new
            frontier = new
        return sorted(found)

    def evidence(self, concepts):
        return [r for r in self.records if r['source'] in concepts or r['target'] in concepts]
