# SIIP Research Evaluation Protocol & Experimental Design

**Document Version:** 1.1.0 (Audited Scientific Baseline)  
**Date:** 2026-10-15  
**Hardware Verified:** NVIDIA RTX 5070 Ti Laptop GPU (12 GB VRAM) &bull; Ollama 0.17.7 (`qwen3:8b`, digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`) &bull; Local D: Drive Storage  
**Dataset Provenance:** Australian National University (ANU) Relational Database Course Dataset (Wang et al., 2020), Zenodo [6526769](https://zenodo.org/records/6526769), CC-BY 4.0 License.

---

## 1. Research Questions & Hypotheses

This protocol establishes an offline, scientifically controlled evaluation comparing generative feedback across five conditions to answer three primary research questions:

- **RQ1 (Educational KG Fidelity):** Does an educational knowledge graph accurately represent course concept hierarchies, prerequisites, and misconceptions compared to ungrounded lecture representations?
- **RQ2 (Comparative Feedback Quality):** Does grounding LLM feedback in an educational knowledge graph improve pedagogical correctness, evidence grounding, concept relevance, and actionability compared to Baseline LLM and Lecture RAG?
  - *Hypothesis 2.1:* Baseline LLMs will have higher rates of solution leakage and hallucinated concepts.
  - *Hypothesis 2.2:* Lecture RAG will improve citation grounding when course materials are available, but broad slide decks may lead to vague guidance.
  - *Hypothesis 2.3:* Lecture RAG + KG will achieve higher actionability and concept relevance scores when verified prerequisite paths are available.
- **RQ3 (Historical Personalization Impact):** Does tailoring guidance to a student's prior mastery profile improve guidance specificity without introducing bias or leaking future assessment data?

---

## 2. Experimental Conditions

To prevent confounding variables, the underlying model (`qwen3:8b`), deterministic grading outcome, question context, schema context, and evaluation cases are held strictly constant:

| Condition ID | Name | Model Context Inputs | Experimental Purpose |
| :--- | :--- | :--- | :--- |
| **Condition A** | **Baseline LLM** | Schema + Question prompt + Student SQL + Grading status | Measures vanilla LLM zero-shot diagnostic capabilities without course grounding. |
| **Condition B** | **Authentic Lecture RAG** | Schema + Question prompt + Student SQL + Grading status + **Retrieved Verifiable Excerpts** | Measures impact of verifiable instructional text retrieval over course materials. |
| **Condition C** | **Authentic Lecture RAG + KG** | Schema + Question prompt + Student SQL + Grading status + **Verifiable Excerpts** + **Verified KG Subgraph** | Tests whether adding structured relation paths and prerequisite hierarchies improves feedback accuracy. |
| **Condition D** | **KG without History** | Condition C inputs with explicit empty learner prior profile (`attempt_count: 0`) | Control baseline for measuring personalization effect in Condition E. |
| **Condition E** | **KG with Genuine Prior History** | Condition C inputs with authentic student concept profile (`as_of < submission_time`) | Evaluates whether genuine historical attempt evidence improves guidance calibration. |

> [!IMPORTANT]
> **Scientific Control Invariants:**
> - Condition C receives **zero** student historical data to prevent confounding KG grounding with learner personalization.
> - Condition E uses **strictly prior** submissions (`submission_time < target_submission_time`); future attempts are mathematically excluded.
> - All conditions use identical system instructions, temperature (0.1), context window (4096), and response JSON schema.
> - No synthetic or fabricated lecture text (e.g. "Lecture 4: Join semantics...") or fabricated `REQUIRES` graph edges may be used.

---

## 3. Corrected Dataset Audit & Benchmark Manifest Statistics

### Authentic Dataset Provenance (ANU Wang et al., 2020)
- **Repository:** Zenodo record [6526769](https://zenodo.org/records/6526769), CC-BY 4.0 License.
- **Source Files & Verified SHA-256 Hashes:**
  * `Submission.sqlite`: `7248ea9a868b3418c28799393abfd3463d6d22154ab388c1d63d124b1ca46817` (3,805,184 bytes)
  * `db_schema.pdf`: `f319424eb470721bab8e76d5ba917734fdf6e860de4085267eaa114cd2e5c5e2` (43,503 bytes)
  * `README.md`: `22fbd7d790bcef897aa57d2e64451ff97b2c97542edc0a097b889900f5a841a7` (5,995 bytes)
- **Executable Instance Audit:** `Submission.sqlite` contains populated relational tables (`movie`: 102 rows, `person`: 576 rows, `director`: 102 rows, `writer`: 111 rows, `Role`: 325 rows). Queries execute directly against this database.
- **Grading Reproduction Boundary:** Reproduction of automated grades cannot be claimed from schema descriptions alone; it requires an executable database engine with exact test cases.

### Verified Benchmark Manifest Statistics ([`datasets/authentic_sql_eval_manifest.json`](file:///c:/Users/ian/Desktop/PROJECT/insructkg_sandbox/datasets/authentic_sql_eval_manifest.json))
An independent research methodology audit verified the actual committed manifest:
- **Total Cases:** 25 student submissions (`eval-anu-001` through `eval-anu-025`).
- **Distinct Exercises:** **7 distinct exercises** (`[4, 5, 8, 9, 10, 11, 12]`), **not 8**. Exercise 13 is absent from the selected cases.
- **Distinct Students:** **21 distinct students**, **not 25**. Students 12 and 25 have multiple submissions in the benchmark.
- **Unique SQL Texts:** **24 unique SQL queries**. One query text (`SELECT DISTINCT COUNT(title) FROM movie WHERE title NOT IN ...`) appears twice (`eval-anu-011` and `eval-anu-020`).
- **Error Patterns:** 20 of 25 cases fall into the rule-based heuristic fallback category `semantic_projection_or_condition_error`.
- **Ground Truth Grounding:** The authentic ANU dataset provides ONLY coarse execution categorization (`partially correct`). There are **no independently validated, expert-labeled concept-gap annotations** in the raw corpus. Syntactic patterns and pedagogical concepts are heuristic annotations.

---

## 4. Evidence Registry & Instructional Grounding

All instructional citations and knowledge graph subgraphs are managed by [`siip/evidence_registry.py`](file:///c:/Users/ian/Desktop/PROJECT/insructkg_sandbox/prairielearn-course/serverFilesCourse/siip/evidence_registry.py).

### Instructional Material Inventory
- **Authentic ANU Materials:** `db_schema.pdf` is registered as verified instructor-aligned documentation. The ANU Zenodo deposit did not publish lecture slides.
- **Offline Test Fixture:** `tests/fixtures/lesson.md` is registered as `synthetic_fixture`, not authentic lecture material.
- **Knowledge Graph Relations:** The 8 developer-created relations in `provisional_relations.jsonl` are registered as `developer_provisional` with `unreviewed` instructor approval status.

### Eligibility Counts for 25-Case Benchmark
- **Cases eligible for Condition A (Baseline LLM):** 25 / 25
- **Cases eligible for Condition B (Authentic Document RAG):** 25 / 25 (grounded in verified ANU schema documentation)
- **Cases eligible for Condition C (Instructor-Approved KG):** **0 / 25** (the available InstructKG graph has 0 instructor-approved edges covering ANU exercise concepts; an empty set is an honest scientific finding)
- **Cases eligible for Condition D / E (Authentic Prior History):** **25 / 25** (all 25 cases have between 3 and 28 verified prior submissions in `Submission.sqlite`)

---

## 5. Single-Blind Review Protocol

1. **Protocol Classification:** This is a **single-blind** review protocol. The independent human evaluator is blinded to condition identities, prompts, and experimental treatments. The automated generator is not a human participant.
2. **Reviewer Packet Isolation:** [`artifacts/research/blind_review_packet.json`](file:///c:/Users/ian/Desktop/PROJECT/insructkg_sandbox/artifacts/research/blind_review_packet.json) contains ONLY:
   - Case ID (`eval_id`)
   - Question prompt & Schema context
   - Authentic student SQL
   - Reference SQL (for reviewer evaluation key)
   - Anonymous responses identified only by random blind tokens (`resp-be4e1294`)
   - Standard rubric
   - **EXCLUDED:** Condition names (A–E), prompts, system instructions, retrieval metadata, and student history.
3. **Key Separation:** Unblinding mapping is stored strictly separately in [`artifacts/research/blind_review_key.json`](file:///c:/Users/ian/Desktop/PROJECT/insructkg_sandbox/artifacts/research/blind_review_key.json).

### Evaluation Rubrics (1–5 Likert & Binary Flags)
1. **Correctness (1–5):** Pedagogical correctness of error diagnosis.
2. **Evidence Grounding (1–5):** Fidelity and relevance of cited instructional evidence. *Note:* Baseline condition (A) receives no citations and is not penalized on general correctness for omitting citations.
3. **Concept Relevance (1–5):** Appropriateness of identified concepts to student misconception.
4. **Actionability (1–5):** Socratic quality guiding self-correction without solution leakage.
5. **Answer Leakage (0 or 1):** Flagged if reference query or solution syntax is revealed.
6. **Hallucination (0 or 1):** Flagged if non-existent SQL keywords or phantom schema tables are invented.

---

## 6. Statistical Analysis Capabilities ([`scripts/analyze_results.py`](file:///c:/Users/ian/Desktop/PROJECT/insructkg_sandbox/scripts/analyze_results.py))

- **Descriptive Statistics:** Mean, standard deviation, median, interquartile range (IQR), and 95% confidence intervals.
- **Paired Comparisons:** Within-case paired comparisons across conditions (C vs A, C vs B, B vs A, E vs D).
- **Hypothesis Tests:** Wilcoxon signed-rank test and paired Student's t-test with p-values and test statistics.
- **Effect Sizes:** Standardized mean difference (Cohen's $d_z$) and Wilcoxon effect size ($r = Z / \sqrt{N}$).
- **Missing Data:** Pairwise deletion for missing ratings.
- **Inter-Rater Agreement:** Percentage exact agreement, adjacent within-1 agreement, and Cohen's Kappa when multiple reviewers score cases.
- **Clustering Awareness:** Explicit audit of non-independent observations resulting from 21 students and 7 exercises across 25 cases.
- **Classification:** Strictly labeled as an **Exploratory Pilot Evaluation** ($N=25$).

---

## 7. Execution Resources & Pre-Pilot Status

- **Model:** `qwen3:8b` (Q4_K_M) on NVIDIA RTX 5070 Ti (12 GB VRAM)
- **Local Ollama Server:** `http://127.0.0.1:11434`
- **Total Inferences for Full Study:** 25 cases &times; 5 conditions = 125 calls
- **Measured Average Latency:** ~9.2 seconds per call
- **Estimated Full Runtime:** ~1,150 seconds (~19.2 minutes)
- **Estimated Cost:** $0.00 (100% local GPU, no external paid APIs)
- **Current Authorization Status:**
  - Dry-run validation: **PASSED**
  - Full 125-inference run: **NOT AUTHORIZED; HELD FOR APPROVAL**
  - Recommended bounded pilot: **3 cases (15 inferences, ~2.3 minutes)**
