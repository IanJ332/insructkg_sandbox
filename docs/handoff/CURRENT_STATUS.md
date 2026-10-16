# Current status — Phase 5.0 CI Stabilization and Baseline Restoration

Snapshot date: 2026-10-15, America/Chicago. Branch: `engineering/windows-migration`. All 201 distinct public tests pass (53.3s). Code formatting, linting, Mypy strict typing, and configuration validation are 100% clean.

| Area | Status | Actual result/evidence | Boundary |
|---|---|---|---|
| CI Public Deterministic Suite | PASS | 201/201, 0 fail/skip, 53.28s | SQLite test fixture decouples CI from local external D: drive; pure-Python Wilcoxon fallback |
| CI Security & Secret Scanning | PASS | `scripts/publication_audit.py` PASS; Bandit: 0 issues; pip-audit: 0 vulnerabilities | Public dataset & model SHA-256 checksums explicitly allowlisted; no global scanner disabling |
| Authentic ANU Integration Test | PASS | `research_tests/test_authentic_anu_dataset.py` verifies local ANU `Submission.sqlite` | Preserved separately from deterministic CI fixtures |
| Authentic SQL benchmark audit | PASS | 25 cases audited: 7 distinct exercises (Ex 4,5,8,9,10,11,12; Ex 13 missing), 21 distinct students, 24 unique queries, 20/25 rule-based fallback | Original ANU labels preserved separately; heuristic patterns not presented as ground truth |
| Authentic Evidence Registry | PASS | `siip/evidence_registry.py` registers source hashes, document IDs, approval statuses; 0/25 instructor-approved KG edges | Honest fail-closed eligibility; synthetic and unreviewed edges clearly distinguished |
| Genuine student histories | PASS | `siip/authentic_history.py` extracts strictly prior ANU attempts (3–28 prior per student); future records excluded | Artificial mastery constants removed from real research condition |
| Local Ollama inference pipeline | PASS | `scripts/experiment_runner.py` with `--dry-run` and `--execute`; local Qwen3 8B (digest `500a1f067a9f...`) on RTX 5070 Ti | Measured latency ~9.2s/call; idempotent result caching; full 125-call run held for authorization |
| Single-blind review protocol | PASS | `artifacts/research/blind_review_packet.json` isolates prompts, condition labels, and treatments from reviewer | Key stored separately in `blind_review_key.json`; scoring template in `scoring_form.json` |
| Statistical analysis suite | PASS | `scripts/analyze_results.py` implements paired Wilcoxon signed-rank, paired t-test, Cohen's d, r, 95% CIs, pairwise deletion | Pure-Python analytical fallback ensures CI portability without SciPy dependency; no swallowed errors |
| Docker host deployment boundary | BLOCKED | Container `host.docker.internal:8080` cannot connect to Windows host default `127.0.0.1` binding without broadening access | Service key present but transport unreachable; marked BLOCKED per protocol; queue architecture preserved |
| Hosted learner pilot | BLOCKED | Institutional SSO, IRB approval, authorized course materials | Offline research evaluation ready; live pilot held |

## What personalization means in Phase 4.4

Condition E uses **genuine temporal prior submissions** extracted directly from the ANU course dataset (`Submission.sqlite`). For each of the 25 benchmark cases, all student attempts recorded prior to the target submission timestamp are aggregated into empirical concept mastery estimates using a Bayesian Beta prior. Submissions occurring at or after the target timestamp are mathematically excluded (3–11 excluded future submissions per case) to prevent temporal leakage. Artificial constants (`prior_attempts = 2, concept_mastery = 0.35`) have been completely eliminated from the research condition. Condition D serves as the exact control, receiving identical question and KG contexts but an explicit empty learner profile (`prior_attempts = 0`).

## Evidence grounding and KG coverage findings

An independent audit of the instructional materials and knowledge graphs confirmed:
1. **Lecture Materials:** The public ANU Zenodo deposit published `db_schema.pdf` and `Submission.sqlite`, but did not include course lecture slides. UIUC CS418 course slides are not accessible in this environment. Therefore, authentic lecture text retrieval is limited to verified schema documentation. Generic hardcoded lecture strings have been removed from the runner.
2. **Knowledge Graph Coverage:** The available InstructKG relations in the sandbox consist of 8 developer provisional edges, all marked `unreviewed` with `instructor_reviewed = False`. None have formal course instructor approval, and none cover concepts for Exercises 4, 8, 9, 10, 11, or 12.
3. **Scientific Invariant:** In accordance with scientific integrity requirements, rather than fabricating connections to force eligibility, **0 of 25 cases** are classified as eligible for an instructor-aligned KG claim. This empty set is documented as an authentic research finding.

## Local GPU Server & Ollama Execution Status

The local Ollama server (version 0.17.7) is active on the host and verified against the NVIDIA GeForce RTX 5070 Ti Laptop GPU (12 GB VRAM):
- Model: `qwen3:8b` (Q4_K_M quantization, digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`).
- Measured Inference Latency: ~9.2 seconds per response.
- Response Formatting: Enforces JSON mode, schema validation, and solution leakage checks.
- Preflight Dry-Run: `python scripts/experiment_runner.py --dry-run` passes completely non-inferentially.
- Full 125-inference experiment: Preserved as unexecuted pending explicit authorization.
