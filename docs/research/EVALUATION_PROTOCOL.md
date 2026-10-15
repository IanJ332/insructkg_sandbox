# SIIP Research Evaluation Protocol & Experimental Design

**Document Version:** 1.0.0  
**Date:** 2026-10-15  
**Hardware Verified:** NVIDIA RTX 5070 Ti Laptop GPU (12 GB VRAM) &bull; Ollama 0.17.7 (`qwen3:8b`, Q4_K_M) &bull; Local D: Drive Storage  
**Dataset Provenance:** Australian National University (ANU) Relational Database Course Dataset (Wang et al., 2020), Zenodo [6526769](https://zenodo.org/records/6526769), CC-BY 4.0 License.

---

## 1. Research Questions & Hypotheses

This protocol establishes an offline, scientifically controlled evaluation comparing generative feedback across five conditions to answer three primary research questions:

- **RQ1 (Educational KG Fidelity):** Does an educational knowledge graph accurately represent course concept hierarchies, prerequisites, and misconceptions compared to ungrounded lecture representations?
- **RQ2 (Comparative Feedback Quality):** Does grounding LLM feedback in an educational knowledge graph improve pedagogical correctness, evidence grounding, concept relevance, and actionability compared to Baseline LLM and Lecture RAG?
  - *Hypothesis 2.1:* Baseline LLMs will have higher rates of solution leakage and hallucinated concepts.
  - *Hypothesis 2.2:* Lecture RAG will improve citation grounding but may cite overly broad slide decks.
  - *Hypothesis 2.3:* Lecture RAG + KG will achieve significantly higher actionability and concept relevance scores by identifying precise misconception paths.
- **RQ3 (Historical Personalization Impact):** Does tailoring guidance to a student's prior mastery profile improve guidance specificity without introducing bias or leaking future assessment data?

---

## 2. Experimental Conditions

To prevent confounding variables, the underlying model (`qwen3:8b`), deterministic grading outcome, question context, and evaluation cases are held strictly constant:

| Condition ID | Name | Model Context Inputs | Experimental Purpose |
| :--- | :--- | :--- | :--- |
| **Condition A** | **Baseline LLM** | Schema + Question prompt + Student SQL + Grading status | Measures vanilla LLM zero-shot diagnostic capabilities without course grounding. |
| **Condition B** | **Lecture RAG** | Schema + Question prompt + Student SQL + Grading status + **Retrieved Lecture Excerpts** | Measures impact of standard semantic retrieval over unstructured course slide decks. |
| **Condition C** | **Lecture RAG + KG** | Schema + Question prompt + Student SQL + Grading status + **Lecture Excerpts** + **Prerequisite Knowledge Graph Subgraph** | Tests whether adding structured relation paths and prerequisite hierarchies improves feedback accuracy. |
| **Condition D** | **KG without History** | Condition C inputs with empty learner prior profile (`attempt_count: 0`) | Baseline for measuring personalization effect in Condition E. |
| **Condition E** | **KG with Prior History** | Condition C inputs with authorized student concept profile (`as_of < submission_time`) | Evaluates whether historical attempt evidence improves guidance calibration for struggling vs. advanced students. |

> [!IMPORTANT]
> **Experimental Control Invariants:**
> - Condition C receives **zero** student historical data to prevent confounding KG grounding with learner personalization.
> - Condition E uses **strictly prior** submissions (`as_of < submission_time`); future attempts are mathematically excluded.
> - All conditions use identical system instructions, temperature (0.1), and response schema.

---

## 3. Dataset Audit & 25-Case Evaluation Manifest

### Authentic Dataset Selection (ANU vs. SQLRepair)
- **ANU Dataset (Wang et al., 2020):** 12,899 authentic student submissions from 393 undergraduate students across 15 exercises, stored in `D:\AI\Datasets\SIIP\anu\Submission.sqlite`. Includes actual relational database tables with full SQLite data, question preambles, and reference solutions under CC-BY 4.0.
- **SQLRepair (Presler-Marshall et al., 2021):** 2,782 submissions across 3 semesters in `D:\AI\Datasets\SIIP\sqlrepair`. Relies on a Java/Hibernate/Z3 environment with synthetic table names (`alpha`, `bravo`).
- **Decision:** ANU was selected as the authoritative benchmark because it contains complete relational SQLite tables, real-world movie/person schemas, human TA benchmark scores, and explicit question prompts.

### Evaluation Manifest Structure
The 25 authentic SQL error cases are recorded in [`datasets/authentic_sql_eval_manifest.json`](file:///D:/AI/SIIP/insructkg_sandbox/datasets/authentic_sql_eval_manifest.json):
- Exercises covered: Ex 4 (Natural Join), Ex 5 (Inner Join), Ex 8 (Subquery/Join), Ex 9 (3-Way Join), Ex 10 (Compound Key Join), Ex 11 (Anti-Join / NOT EXISTS), Ex 12 (Anti-Join Negation), Ex 13 (NOT IN / Set Difference).
- Error patterns: Missing Joins (Cartesian products), missing group-by aggregation, predicate filter omissions, anti-join subquery correlation errors, and NULL equality comparison errors.
- 25 distinct authentic students (`anu-student-69` through `anu-student-385`).

---

## 4. Evaluation Rubrics

Each generated response is evaluated across six criteria by blinded reviewers:

### 1. Correctness (1–5 Likert Scale)
- **1 (Completely Incorrect):** Misdiagnoses error or asserts correct query is broken.
- **2 (Mostly Incorrect):** Misidentifies the root cause.
- **3 (Partially Correct):** Diagnoses symptoms but misses the core conceptual flaw.
- **4 (Accurate):** Accurately diagnoses the error with minor ambiguity.
- **5 (Precise):** Unambiguous, completely accurate diagnosis of the student's misconception.

### 2. Evidence Grounding (1–5 Likert Scale)
- **1 (Fabricated/Irrelevant):** Hallucinated or completely irrelevant citation.
- **2 (Vaguely Related):** Cites general topic without supporting the specific advice.
- **3 (Moderately Grounded):** General lecture reference loosely connected to the error.
- **4 (Well Grounded):** Directly cites appropriate lecture slide or section.
- **5 (Exemplary):** Highly targeted citation providing the exact instructional context needed.

### 3. Concept Relevance (1–5 Likert Scale)
- **1 (Irrelevant):** Unrelated concepts listed.
- **2 (Tangential):** Weakly related SQL concepts.
- **3 (Broadly Relevant):** Broad category correct, but wrong specific concept.
- **4 (Targeted):** Directly relevant SQL concept identified.
- **5 (Optimal):** Precisely identifies the concept and its prerequisite gap.

### 4. Actionability (1–5 Likert Scale)
- **1 (Unhelpful/Confusing):** Leaves student unable to proceed.
- **2 (Vague):** Ambiguous hint requiring guessing.
- **3 (Adequate):** Helpful hint but requires substantial inferential leaps.
- **4 (Actionable):** Clear guided question directing the student toward self-correction.
- **5 (Exemplary Socratic):** Guides student to discover and correct the flaw without giving away the answer.

### 5. Answer Leakage (Binary Flag: 0 = Safe, 1 = Leaked)
- Evaluates whether the advice gives away the reference SQL, solution query, or exact column lists.

### 6. Hallucination (Binary Flag: 0 = Grounded, 1 = Hallucinated)
- Evaluates whether the model invents non-existent SQL keywords, nonexistent schema tables, or phantom columns.

---

## 5. Blind Review & Analysis Protocol

1. **Randomized Variant Blinding:** [`scripts/experiment_runner.py`](file:///D:/AI/SIIP/insructkg_sandbox/scripts/experiment_runner.py) generates `blind_review_packet.json` where conditions A–E are shuffled and assigned hashed blind identifiers (`variant-a1b2c3d4`). Evaluators score responses without knowing which condition produced them.
2. **Key Storage:** The unblinding mapping is stored separately in `blind_review_key.json`.
3. **Statistical Analysis:** [`scripts/analyze_results.py`](file:///D:/AI/SIIP/insructkg_sandbox/scripts/analyze_results.py) unblinds the evaluations and computes mean, standard deviation, and paired non-parametric tests (Wilcoxon signed-rank test, Kruskal-Wallis) comparing Condition C vs A and C vs B.

---

## 6. Resource & Execution Estimate (Local GPU)

- **Model:** `qwen3:8b` Q4_K_M running on local Ollama 0.17.7
- **Hardware:** NVIDIA GeForce RTX 5070 Ti Laptop GPU (12 GB VRAM)
- **Evaluations:** 25 cases &times; 5 conditions = **125 total inferences**
- **Average Measured Latency:** ~9.5 seconds per inference
- **Total Runtime:** $\approx 1,187.5\text{ seconds}$ (**~19.8 minutes**)
- **Token Volume:** $\approx 156,250\text{ total tokens}$
- **Financial Cost:** **\$0.00** (100% local GPU execution)

---

## 7. Institutional Dependencies & Pre-Pilot Blockers

The following dependencies remain external requirements before any live classroom deployment:
1. **Course Instructor Authorization:** Formal review and sign-off on generated knowledge graph concepts, relation edges, and prerequisite hierarchy.
2. **Institutional SSO/SAML Integration:** Production PrairieLearn authentication boundary integration replacing synthetic local tokens.
3. **IRB & Research Ethics Approval:** Human subjects study approval for student feedback interactions.
