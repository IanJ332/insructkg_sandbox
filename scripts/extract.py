"""Preflight and guarded launch of the real, unmodified InstructKG pipeline."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--run',action='store_true',help='Execute actual pipeline with configured approved model resources')
parser.add_argument('--authorized-model-usage',action='store_true',help='Use only after explicit approval of the configured model and usage')
args=parser.parse_args()
packages=['docling','dotenv','pydantic','openai','anthropic','sentence_transformers','umap','hdbscan']
missing=[name for name in packages if importlib.util.find_spec(name) is None]
provider=os.environ.get('LLM_PROVIDER','openai')
issues=[]
if not os.environ.get('SIIP_EXTRACTION_MODEL'):issues.append('SIIP_EXTRACTION_MODEL must identify the approved extraction model.')
if missing:issues.append('Missing isolated pipeline packages: '+', '.join(missing))
if provider in {'vllm','hf','local','huggingface'}:
    issues.append('This Intel Mac has no CUDA GPU. Configure an approved compatible inference machine or API provider.')
if provider=='openai' and not os.environ.get('OPENAI_API_KEY'):issues.append('OPENAI_API_KEY unavailable in this process.')
if provider in {'anthropic','claude'} and not os.environ.get('ANTHROPIC_API_KEY'):issues.append('ANTHROPIC_API_KEY unavailable in this process.')
if not args.authorized_model_usage:issues.append('No paid/API model-usage authorization supplied; no inference initiated.')
status={'status':'BLOCKED' if issues else 'NOT_RUN','fresh_extraction_executed':False,'provider':provider,
        'blockers':issues,'source':'research/instructkg-jeffry/main.py','input':'research/instructkg-jeffry/data/sql',
        'expected_outputs':['chunks.jsonl','mentions.jsonl','concept_cards.jsonl','context_clusters.jsonl','pairpackets.jsonl','relations.jsonl']}
if args.run and not issues:
    destination=ROOT/'artifacts/fresh-kg';destination.mkdir(exist_ok=True)
    command=[sys.executable,str(ROOT/status['source']),'--data-dir',str(ROOT/status['input']),
        '--out-dir',str(destination),'--llm-model',os.environ.get('SIIP_EXTRACTION_MODEL','gpt-4o-mini')]
    with (destination/'run.log').open('w') as log:
        result=subprocess.run(command,cwd=ROOT/'research/instructkg-jeffry',stdout=log,stderr=subprocess.STDOUT)
    counts={name:sum(bool(line.strip()) for line in (destination/name).open()) if (destination/name).exists() else None for name in status['expected_outputs']}
    status.update({'status':'PASS' if result.returncode==0 and all(v is not None for v in counts.values()) else 'FAIL',
                   'fresh_extraction_executed':True,'returncode':result.returncode,'actual_counts':counts})
(ROOT/'artifacts/fresh_extraction_status.json').write_text(json.dumps(status,indent=2)+'\n')
print(json.dumps(status,indent=2))
