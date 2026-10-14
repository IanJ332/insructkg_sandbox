# SQL grader

Implementation: `grader.py` and `sql_worker.py`. Dataset A has four employees; B adds more matches, NULL references, a non-NULL unmatched reference and an unused department. Both initialize independently. There is intentionally no enforced foreign key on employee.department_id.

The parent spawns isolated Python with a minimal environment and temporary cwd. SQLite's authorizer, not the leading-keyword check, enforces supported reads. Statements cannot mutate, attach files, load extensions or read metadata/unrelated tables. Progress deadline is 0.3s, parent timeout 3s, result cap 1,000 rows and SQL length cap 12,000. Linux address-space cap is 256 MiB; macOS uses the other SQLite/process limits. These controls do not protect against an engine-level compromise.

Correctness compares multisets of typed SQLite values, preserving duplicates and NULL and ignoring row order. Column order/count matter; aliases do not. Alternative equivalent queries such as NOT EXISTS pass. Matching the finite fixtures is not proof of equivalence over every possible database.

Statuses: correct, semantic_error, compilation_error, execution_error and unsupported_query. Semantic observations distinguish missing unmatched rows and missed non-NULL references where execution evidence supports them. `public_grade()` excludes hidden rows, reference SQL and raw engine messages from student/model contexts. Regression tests cover syntax/runtime distinction, joins, filters, unsafe statements, duplicate/order semantics and actual exhaustion/timeout paths.
