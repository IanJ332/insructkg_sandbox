# Audited commit and file inventory

Generated directly from fetched Git history on 2026-10-20. Each range excludes its base and includes its head. PR #3 as opened also includes the PR #2 range.

## PR #1: 2288d9d..61c60d2

Commit boundaries:

```text
581c5e407712a2c78ef6f350d821701c980bfbc3 chore: preserve verified Phase 1 integration baseline
3da9dbc02825ef4eb2b32f4b8b5b456d28a3a0b7 fix: harden grading feedback ingestion and local service boundaries
122164ad1b68e57e3161d3b4637bbf45ee2462fb ci: verify public fixtures security packaging and actual PrairieLearn flow
86e860a314f37554dfe264a9d91a9c2a36316377 fix: make clean fixture setup and browser dependencies portable
11b803ed91a91520d053427acf79740607c81eff fix: distinguish synthetic contract graph in smoke checks and UI
5de2dd79d5830e4a71e695f83d2853bb5f3d17d3 docs: add evidence-backed engineering research and review handoff
8eabeca0c6d9d446fe6c660ab489845964da77f4 docs: record passing remote CI and actual platform persistence evidence
c674a7498eafa85d86d90732d8223cf1bbf15aa6 feat: add scoped synthetic personalization and atomic PL snapshot synchronization
f9589ce7f80ac37917368958d0407eeb9bb8006d feat: profile non-generative ingestion and prepare local GPU server configuration
47626e6c0326fb0cee59e61beceaebd76f071c6a fix: preserve feedback origin and cleanly stop bundled PostgreSQL
df6a461a9c99ca5c479b6532dcef0b817d3f5524 docs: distinguish synthetic personalization and record cross-validation evidence
d65028a41b81be9b120f21734ece6e5edabdb864 fix: bind each API poll to one assessment-instance owner
61c60d2a5e73fc60175e94246c061ff34503dcc3 docs: record verified single-owner synchronization contract and final results
```

Changed files:

```text
A	.dockerignore
A	.editorconfig
A	.env.example
A	.gitattributes
A	.github/workflows/ci.yml
A	.github/workflows/integration.yml
A	.github/workflows/security.yml
A	.gitignore
A	CHANGELOG.md
A	CONTRIBUTING.md
A	MANIFEST.in
A	Makefile
A	NOTICE.md
M	README.md
A	datasets/questions/expected_outputs.json
A	datasets/questions/questions.json
A	datasets/synthetic-students/students.json
A	datasets/synthetic-submissions/attempts.json
A	docs/ARCHITECTURE.md
A	docs/DEMO.md
A	docs/DEPLOYMENT_GUIDE.md
A	docs/EXPERIMENT_PLAN.md
A	docs/FEEDBACK_DESIGN.md
A	docs/HUMAN_ACTION_REQUIRED.md
A	docs/INSTRUCTKG_INTEGRATION.md
A	docs/PRAIRIELEARN_INTEGRATION.md
A	docs/PROGRESS.md
A	docs/README.md
A	docs/REPOSITORY_AUDIT.md
A	docs/SECURITY_AND_PRIVACY.md
A	docs/STUDENT_PROFILE.md
A	docs/VERIFICATION_REPORT.md
A	docs/architecture/DATABASE_SCHEMA.md
A	docs/architecture/DATA_FLOW.md
A	docs/architecture/INTEGRATION_CONTRACTS.md
A	docs/architecture/PERSONALIZED_FEEDBACK_LIFECYCLE.md
A	docs/architecture/SECURITY_MODEL.md
A	docs/architecture/SYSTEM_OVERVIEW.md
A	docs/audits/BASELINE_AUDIT.md
A	docs/components/INSTRUCTKG.md
A	docs/components/LLM_FEEDBACK.md
A	docs/components/PRAIRIELEARN.md
A	docs/components/SQL_GRADER.md
A	docs/components/STUDENT_ANALYTICS.md
A	docs/engineering/CI_CD.md
A	docs/engineering/DEPENDENCIES.md
A	docs/engineering/INGESTION_PROFILING.md
A	docs/engineering/LOCAL_SETUP.md
A	docs/engineering/OPERATIONS.md
A	docs/engineering/SECURITY_AUDIT.md
A	docs/engineering/SUBMISSION_SYNCHRONIZATION.md
A	docs/engineering/TEST_STRATEGY.md
A	docs/engineering/WINDOWS_GPU_READINESS.md
A	docs/handoff/CURRENT_STATUS.md
A	docs/handoff/EXTERNAL_REVIEW_PACKET.md
A	docs/handoff/HUMAN_ACTION_REQUIRED.md
A	docs/handoff/LEGACY_SYSTEM_INTEGRATION.md
A	docs/handoff/NEXT_IMPLEMENTATION_PLAN.md
A	docs/handoff/REMAINING_WORK.md
A	docs/handoff/verification.json
A	docs/history/DECISION_LOG.md
A	docs/history/IMPLEMENTATION_TIMELINE.md
A	docs/history/ISSUE_LOG.md
A	docs/research/EXPERIMENT_DESIGN.md
A	docs/research/FEEDBACK_CAPABILITIES.md
A	docs/research/FEEDBACK_EVALUATION.md
A	docs/research/GRAPH_VALIDATION.md
A	docs/research/RESEARCH_CONTEXT.md
A	docs/research/RESEARCH_LIMITATIONS.md
A	infrastructure/Dockerfile.extraction
A	infrastructure/compose.yaml
A	infrastructure/extraction-cpu.lock
A	infrastructure/local-pl-scope.example.json
A	infrastructure/requirements-gpu.txt
A	infrastructure/requirements-pipeline.txt
A	infrastructure/windows/local-model-versions.json
A	infrastructure/windows/ollama.env.example
A	infrastructure/windows/readiness.ps1
A	prairielearn-course/courseInstances/Fall2026/assessments/sql-sandbox/infoAssessment.json
A	prairielearn-course/courseInstances/Fall2026/infoCourseInstance.json
A	prairielearn-course/infoCourse.json
A	prairielearn-course/questions/sql_join_01/info.json
A	prairielearn-course/questions/sql_join_01/question.html
A	prairielearn-course/questions/sql_join_01/server.py
A	prairielearn-course/questions/sql_join_02/info.json
A	prairielearn-course/questions/sql_join_02/question.html
A	prairielearn-course/questions/sql_join_02/server.py
A	prairielearn-course/questions/sql_join_03/info.json
A	prairielearn-course/questions/sql_join_03/question.html
A	prairielearn-course/questions/sql_join_03/server.py
A	prairielearn-course/serverFilesCourse/siip/__init__.py
A	prairielearn-course/serverFilesCourse/siip/configuration.py
A	prairielearn-course/serverFilesCourse/siip/data/dataset_A.sql
A	prairielearn-course/serverFilesCourse/siip/data/dataset_B.sql
A	prairielearn-course/serverFilesCourse/siip/data/mapping.json
A	prairielearn-course/serverFilesCourse/siip/data/provenance.json
A	prairielearn-course/serverFilesCourse/siip/data/provisional_relations.jsonl
A	prairielearn-course/serverFilesCourse/siip/data/questions.json
A	prairielearn-course/serverFilesCourse/siip/extraction.py
A	prairielearn-course/serverFilesCourse/siip/feedback.py
A	prairielearn-course/serverFilesCourse/siip/grader.py
A	prairielearn-course/serverFilesCourse/siip/graph.py
A	prairielearn-course/serverFilesCourse/siip/ingestion.py
A	prairielearn-course/serverFilesCourse/siip/observability.py
A	prairielearn-course/serverFilesCourse/siip/personalization.py
A	prairielearn-course/serverFilesCourse/siip/pl_bridge.py
A	prairielearn-course/serverFilesCourse/siip/py.typed
A	prairielearn-course/serverFilesCourse/siip/sources.py
A	prairielearn-course/serverFilesCourse/siip/sql_worker.py
A	prairielearn-course/serverFilesCourse/siip/store.py
A	prairielearn-course/serverFilesCourse/siip/synchronization.py
A	pyproject.toml
A	requirements-dev.txt
A	research_tests/test_existing_graph.py
A	scripts/bootstrap.py
A	scripts/check_local_model.py
A	scripts/check_wheel.py
A	scripts/dashboard.py
A	scripts/demo_personalization.py
A	scripts/evaluate.py
A	scripts/expected.py
A	scripts/extract.py
A	scripts/extraction_cpu.py
A	scripts/graph_audit.py
A	scripts/import_pl.py
A	scripts/init_public.py
A	scripts/manage.py
A	scripts/persistence_probe.py
A	scripts/personalize.py
A	scripts/prepare.py
A	scripts/profile_ingestion.py
A	scripts/publication_audit.py
A	scripts/refresh_records.py
A	scripts/report.py
A	scripts/review_graph.py
A	scripts/seed.py
A	scripts/smoke.py
A	scripts/sync_pl.py
A	scripts/validate_config.py
A	scripts/verify_ingestion.py
A	security/secret-allowlist.json
A	tests/e2e/prairielearn_flow.py
A	tests/fixtures/lesson.md
A	tests/test_followup.py
A	tests/test_hardening.py
A	tests/test_system.py
```

## Windows migration: 61c60d2..ec81b84

Commit boundaries:

```text
e1e7671a97b1c3ff15026d715e8ecca4a8824eb4 fix(windows): resolve cross-platform process, path, and test execution compatibility
c37d962567e594118a7a626328e7066b21895879 fix(windows): harden process verification in dashboard_stop and add offline InstructKG schema validation
a821e5bde6cfc71cb23292d58831cfd3f2232a3f fix(security): resolve bandit B607 and B310 annotations in Windows scripts
cfde9b6059e6ec9facd3dadf0635b3b17c1ffbb2 feat(jobs): decouple deterministic grading from generative feedback via durable SQLite job queue
3ac914b58f2c3b4b01b6dd48e47ca5e731ad9a5d feat: complete Phase 4.1 async feedback lifecycle, safe identity resolution, and queue hardening
07b1b16a0f7020e2eaafd347ba210222e8577c88 feat: complete Phase 4.2 engineering closure, cryptographic authorization, and async browser delivery
4271f70ca875f6bb9dd398224dc3a07de3958ea1 docs(handoff): update Current Status and Remaining Work for Phase 4.2 closure
da2d8b470ac55e4acdd468a4eace1a771412b7ec feat: Phase 4.3 security boundary closure, provenance validation, and authentic SQL benchmark protocol
53291885b05667b0e17a56ef2fa79ecceda2bc33 feat(research): scientific evaluation readiness and genuine evidence grounding (Phase 4.4)
ec81b84a10b29ef29d9fa0187974f0a8cbc7742a fix(ci): restore CI test determinism, pure-Python statistics fallback, and secret allowlisting (Phase 5.0)
```

Changed files:

```text
A	datasets/authentic_sql_eval_manifest.json
M	docs/handoff/CURRENT_STATUS.md
M	docs/handoff/REMAINING_WORK.md
A	docs/research/EVALUATION_PROTOCOL.md
M	infrastructure/compose.yaml
M	prairielearn-course/infoCourse.json
M	prairielearn-course/questions/sql_join_01/question.html
M	prairielearn-course/questions/sql_join_02/question.html
M	prairielearn-course/questions/sql_join_03/question.html
A	prairielearn-course/serverFilesCourse/siip/authentic_history.py
M	prairielearn-course/serverFilesCourse/siip/configuration.py
A	prairielearn-course/serverFilesCourse/siip/data/identity_map.json
A	prairielearn-course/serverFilesCourse/siip/evidence_registry.py
M	prairielearn-course/serverFilesCourse/siip/feedback.py
M	prairielearn-course/serverFilesCourse/siip/grader.py
A	prairielearn-course/serverFilesCourse/siip/identity.py
A	prairielearn-course/serverFilesCourse/siip/instructkg_schema.py
A	prairielearn-course/serverFilesCourse/siip/jobs.py
M	prairielearn-course/serverFilesCourse/siip/pl_bridge.py
A	research_tests/test_authentic_anu_dataset.py
A	scripts/analyze_results.py
A	scripts/audit_datasets.py
A	scripts/benchmark_adapters.py
A	scripts/benchmark_performance.py
A	scripts/canary_test.py
M	scripts/dashboard.py
A	scripts/experiment_runner.py
A	scripts/feedback_worker.py
A	scripts/gpu_smoke_test.py
M	scripts/manage.py
M	scripts/publication_audit.py
M	security/secret-allowlist.json
M	tests/e2e/prairielearn_flow.py
A	tests/e2e/test_async_browser_flow.py
A	tests/test_async_lifecycle.py
A	tests/test_authorization.py
A	tests/test_feedback_jobs.py
M	tests/test_followup.py
M	tests/test_hardening.py
A	tests/test_historical_personalization.py
A	tests/test_instructkg_schema.py
A	tests/test_pl_identity_contract.py
A	tests/test_queue_topology.py
A	tests/test_scientific_readiness.py
A	tests/test_submission_identity.py
```

## PR #2: ec81b84..5d1a3ec

Commit boundaries:

```text
3d614673c8022abad081c14067b6a0f36d562c87 feat(em): implement Phase 5.1 minimum EM vertical slice and instructor review
83b55b980c3a694668d4425b137990d5a5a70d1b feat(adaptive): implement Phase 5.2 adaptive recommender and dynamic project generator
6d3cbb251783145ac384b9293dfe9f28173a3b6d feat(evaluation): implement Phase 5.3 multi-stakeholder evaluation instruments and cohort analytics
c29cebe0fbb68c18a71bb7eb3eec70668c53c0dd feat(reliability): implement Phase 5.4 concurrency stress tests and reproducible rehearsal scripts
bd6d59680f80de9b9b1502d083be2131f49b6d06 docs: add comprehensive Phase 5 prototype report and meeting rehearsal guide
4f38a5ee35749b14a2a12f6ab3517c584be31fd6 feat(phase5.5): prototype acceptance, role authorization security, browser e2e, and meeting brief
606125d091095bd9974e8d9184f91fef34e0e1f1 fix(ci): reconcile 4-question assessment total points and CI runner latency threshold
e2993ed16da7ac2efd1eb2a665908d4ac6f69ed3 feat(phase5.6): final security closure, role-based access control, browser e2e, and metric qualifications
aaead9dfe6412265373bd086d4871d3cb711d984 feat(phase5.6): isolate synthetic login in dev mode, correct browser test classification, and verify sequential demo flow
64b7a0d4e132c9517d53a3f7de3f54b75a90b880 fix(ci): bandit token defaults and integration runner data initialization
8026510dbd4d73a7f44aaf77538682cedf8854e9 fix(smoke): test 401 unauthenticated fail-closed and authenticated student history
f56323d8610767756f8e56894feb74a1da37ff10 fix(integration): synthetic session endpoint URL and development env vars
5d1a3ece81b1009207054593971595ad6095e215 fix(e2e): authenticate as S003 before viewing learner history in PL flow
```

Changed files:

```text
M	.github/workflows/integration.yml
M	datasets/questions/expected_outputs.json
M	datasets/questions/questions.json
A	docs/research/GPU_CAPACITY_TEST_PLAN.md
A	docs/research/PHASE5_PROTOTYPE_REPORT.md
A	docs/research/PROFESSOR_ALAWINI_MEETING_BRIEF.md
M	prairielearn-course/courseInstances/Fall2026/assessments/sql-sandbox/infoAssessment.json
A	prairielearn-course/questions/sql_join_04/info.json
A	prairielearn-course/questions/sql_join_04/question.html
A	prairielearn-course/questions/sql_join_04/server.py
M	prairielearn-course/serverFilesCourse/siip/data/questions.json
A	prairielearn-course/serverFilesCourse/siip/em_models.py
A	prairielearn-course/serverFilesCourse/siip/em_repository.py
M	prairielearn-course/serverFilesCourse/siip/identity.py
A	prairielearn-course/serverFilesCourse/siip/project_generator.py
A	prairielearn-course/serverFilesCourse/siip/project_models.py
A	prairielearn-course/serverFilesCourse/siip/recommender.py
M	prairielearn-course/serverFilesCourse/siip/store.py
A	prairielearn-course/serverFilesCourse/siip/survey_instruments.py
M	scripts/dashboard.py
A	scripts/demo_a_personalized_learning.py
A	scripts/demo_b_entrepreneurial_mindset.py
A	scripts/demo_c_dynamic_project.py
A	scripts/measure_actual_reliability.py
M	scripts/smoke.py
A	scripts/verify_sequential_demos.py
M	tests/e2e/prairielearn_flow.py
M	tests/e2e/test_async_browser_flow.py
A	tests/e2e/test_browser_demos.py
A	tests/e2e/test_em_lifecycle_browser.py
A	tests/e2e/test_real_browser_e2e.py
A	tests/test_adaptive_projects.py
A	tests/test_concurrency_stress.py
A	tests/test_em_vertical_slice.py
A	tests/test_evaluation_instruments.py
A	tests/test_role_authorization_security.py
```

## PR #3 incremental: 5d1a3ec..793cd0d

Commit boundaries:

```text
7b13fa0d64a5679e65747ef885e320c8239e3f6c feat(demo): preserve existing unverified instructor-to-learner prototype for audit
5a3395ac5c298a3693fae5cb3629bdb1927003e5 Make demo recordings complete and verify persisted browser lifecycle
226ecfe5d00a983b9dc5266ef1b57f42911533bd Record fresh course setup and explicit project interests
f8acdf914a8461c4f9bb676d382e05ff569f983d Audit full sandbox requirements and harden authoring and learner contracts
94f97df846999fc2f5578614bc193aa15c0ab2c4 Isolate browser test public contract fixtures
cae7227b08cfd22e3f19fe7e8c61b23a113e79d4 feat: add bounded source-grounded local KG extraction with honest fallback
54efd70a6a106da39dab13fba79df34efc4ad10b Record isolated demo regression results and fixture initialization
8161b050d679c1587335d2b8d6bb77c6d0b68f46 Derive demo entity lineage from persisted explicit associations
ed2f65c8b0f3c898fe63a767a2657555aef3a9ec Annotate audit with strict browser and genuine local inference evidence
2c3d6df0d9bb186ac2cf5046442d0a4353cdaf7b feat: integrate source-grounded instructor-to-learner research sandbox
793cd0d383849ff74742b7211cefbb2307ead8df fix(security): protect legacy lab, analytics and attempt ownership
```

Changed files:

```text
M	.github/workflows/integration.yml
A	demo_materials/SYNTHETIC_SQL_JOINS_LESSON.md
A	docs/demo/DEPENDENCY_GRAPH.md
A	docs/demo/DEPENDENCY_MAP.md
A	docs/demo/EXTRACTION_REPORT.md
A	docs/demo/FULL_REQUIREMENTS_AUDIT.md
A	docs/demo/HIDDEN_GAPS.md
A	docs/demo/INTEGRATION_CONTRACT.md
A	docs/demo/PROFESSOR_BRIEF.md
A	docs/demo/RECORDING_RUNBOOK.md
A	docs/demo/REQUIREMENTS_TRACEABILITY.csv
A	prairielearn-course/serverFilesCourse/siip/assignment_grounding.py
A	prairielearn-course/serverFilesCourse/siip/demo_authoring.py
A	prairielearn-course/serverFilesCourse/siip/demo_kg.py
A	prairielearn-course/serverFilesCourse/siip/demo_lineage.py
A	prairielearn-course/serverFilesCourse/siip/demo_observability.py
A	prairielearn-course/serverFilesCourse/siip/demo_student.py
M	prairielearn-course/serverFilesCourse/siip/feedback.py
M	prairielearn-course/serverFilesCourse/siip/jobs.py
A	prairielearn-course/serverFilesCourse/siip/local_kg_extractor.py
M	prairielearn-course/serverFilesCourse/siip/project_generator.py
M	scripts/dashboard.py
M	scripts/extract.py
M	scripts/feedback_worker.py
A	scripts/record_professor_demo.py
M	scripts/smoke.py
A	scripts/start_full_sandbox.ps1
M	security/secret-allowlist.json
M	tests/e2e/prairielearn_flow.py
A	tests/e2e/test_full_sandbox_browser.py
A	tests/e2e/test_professor_demo_script.py
A	tests/test_assignment_grounding.py
A	tests/test_demo_authoring.py
A	tests/test_demo_integration.py
A	tests/test_demo_kg.py
A	tests/test_demo_lineage.py
A	tests/test_demo_observability.py
A	tests/test_demo_security.py
A	tests/test_demo_student.py
M	tests/test_evaluation_instruments.py
M	tests/test_hardening.py
A	tests/test_local_kg_extractor.py
A	tests/test_ollama_feedback.py
M	tests/test_role_authorization_security.py
```
