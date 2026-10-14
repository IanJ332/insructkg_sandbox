# Submission data flow

1. PL renders a multiline string element. Student SQL is data, not executable Python. `generate_question` exposes the statement and no reference SQL.
2. `grade_question` invokes `grader.grade`. For each independently initialized A/B dataset, `sql_worker.py` executes one parser-authorized read-only statement with limits and returns bounded rows/status.
3. The parent compares row multisets, including multiplicity and NULL, with server-only reference results. Row order is ignored. Syntax/unsupported/runtime/semantic outcomes remain distinct.
4. `diagnosis` records observed output patterns. Only executed semantic failures propose possible task concepts. No calibrated confidence is invented.
5. `generate_feedback` constructs baseline, retrieved-page or graph-enhanced contexts. Missing context/provider errors produce labeled fallback and preserve the grade. No hidden/reference rows are passed to the provider.
6. PL stores its actual score/feedback and attempt history. No student UID is guessed in question code.
7. The supported instructor CSV is downloaded only from the local SIIP assessment. `ingestion.read_local_csv` validates all rows and minimizes fields. `SubmissionRepository.process_many` verifies grades before one transaction; a later invalid/colliding row leaves no partial import.
8. Profiles aggregate latest executed outcomes by concept-linked question. Timestamp-filtered prior persisted history is used for feedback. Analytics refreshes from the persistent repository.

The same grading/feedback components process original synthetic batch attempts, but source labels distinguish fixtures from actual PL exports. Model outputs, existing research judgments, provisional edges and fresh pipeline outputs must never share an invented provenance label. Batch feedback uses already-persisted as-of history; records prepared within the same uncommitted batch are not a sequential tutoring session.
