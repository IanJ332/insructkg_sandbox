# Student profiles and analytics

S001–S005 are synthetic IDs with 21 reproducible batch attempts. Additional actual local Dev User PL submissions are mapped explicitly to S003 by the narrow export importer, and source labels remain distinct. Dashboard form/API attempts are synthetic fixtures, not PL records.

`store.py` tracks immutable attempts, observed errors, task concepts, correctness, feedback and available external links. Phase 2 validates/minimizes inputs, rejects source/scope collisions, atomically checks export grades and commits batches, resolves concurrent duplicates, and filters prior feedback history by timestamp. Optional graph lookup failures yield unavailable context rather than silently fabricated dependencies.

For each concept, n counts distinct linked questions with executed correct/semantic-error outcomes, c counts the latest correct outcomes, estimate=(1+c)/(2+n). Retries replace a question's latest outcome instead of inflating n. Compiler/runtime/unsupported failures remain visible but do not enter that denominator. This is an unvalidated descriptive heuristic, not knowledge tracing or proof of misconception.

The loopback dashboard displays aggregate/question/source counts, concept-associated errors, individual history and prerequisites, the full original graph review inventory and fallback feedback comparison. POST /api/attempts has strict schema and optional idempotency key. Health distinguishes storage, KG and unprobed LLM state. Authenticated multi-user/real-data analytics remains a separate approved deployment task.

The follow-up uses the same profile system for authorized post-submission feedback, with an exclusive event-time cutoff and minimized concepts. New API snapshots update profiles via atomic idempotent ingestion. Snapshot contracts and distinct-history feedback tests pass; actual PL API polling and hosted personalization are not claimed. See the lifecycle document.
