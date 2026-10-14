> Phase 1 historical record. For current Phase 2 status, see [CURRENT_STATUS](handoff/CURRENT_STATUS.md). Counts and blockers below describe the earlier snapshot.

# Security and privacy boundaries

## SQL as untrusted data

The sandbox accepts the SQLite SELECT/WITH subset required by these exercises. The initial leading-keyword check is **not** the security boundary. SQLite compiles the query and invokes an authorizer that permits only SELECT, bounded recursive queries, reads of Employees/Departments and a short safe built-in function allowlist. It denies DDL, writes (including WITH followed by DELETE), PRAGMA, attachment, unrelated metadata-table reads and extension functions. sqlite3.execute enforces one statement, while semicolons inside strings remain valid.

Every dataset runs in a fresh isolated Python process and in-memory database. Parent subprocess timeout: three seconds. SQLite progress deadline: 0.3 seconds. Result cap: 1,000 rows. SQL cap: 12,000 characters. SQLite limits also bound text values, columns, expression depth, compound queries and opcode count. Workers initialize clean datasets, enable query_only and disable extension loading where the build exposes it. macOS Python omits extension loading entirely; that path is handled explicitly.

The child runs with `-I`, a fresh temporary working directory and a minimal environment (no API keys or application secrets). POSIX CPU/file/descriptor limits apply where available. Linux also uses a 256 MiB address-space limit; macOS relies on SQLite allocation/value limits, CPU/progress deadlines and parent termination because reliable equivalent RLIMIT_AS behavior is unavailable. The SQL interface exposes no file/network function; ATTACH/readfile/load_extension/sqlite_master and mutation tests are executed.

This is process isolation and a restricted SQL capability surface, not a kernel filesystem/network sandbox against a compromised SQLite binary. The process still has its OS user's permissions. For hostile public/production workloads, use dedicated non-root containers with filesystem/network isolation, runtime patch management, concurrency quotas and infrastructure review. Do not call this research prototype a production security boundary.

## Containers and local UI

The official PL image is pinned and bound to 127.0.0.1:3000. The course mount is read-only. There is no privileged mode, Docker socket mount, external-grader job service or publicly exposed endpoint. PostgreSQL remains inside the container and uses a project-scoped named volume. Dashboard binds 127.0.0.1:8080. It is synthetic-only local tooling without authentication, with escaped output, bounded request sizes, a same-origin POST check, no CORS access, restrictive content-security policy and no shell execution of SQL. Do not expose it to a network or port-forward it.

## Data minimization

No existing UIUC course, real student data, Canvas content, CS418 records, institutional student API or private repository was accessed. All five profile IDs are artificial. Local Dev User is the official development identity, explicitly mapped to S003 in the narrow local importer. API/export adapters never assume Course Editor grants instance student-data access; unsupported identities/team records are rejected until authorized mappings exist.

The future pseudonym helper uses HMAC-SHA256 with a study-specific secret, avoiding reversible raw IDs and predictable unsalted hashing. An institution-approved identity linkage service should retain the mapping separately, with restricted access, retention/deletion rules and consent/approval controls. The demo's S001–S005 allowlist intentionally prevents accidental ingestion of production IDs.

## Credentials, LLMs and evidence

.env is ignored; .env.example contains no secrets. Workers do not inherit credentials. Provider errors log only exception class. Optional local compatible inference receives safe grades, no hidden dataset rows or reference SQL, and untrusted-source instructions are constrained. No paid usage or remote inference occurred. Provider output is schema/filter checked, but the leakage filter is not a complete semantic safeguard. The deterministic grade is authoritative even when feedback fails.

Original graph provenance and errors are preserved; no instructor-approved status is fabricated. Course PDF and copied lecture/graph evidence remain local, excluded from integration tracking where appropriate. Raw exports and backup dumps are local-only and ignored. Before sharing artifacts, review evidence snippets for course-material redistribution permissions.

## Executed checks

See test_system.SQLTests for unsafe statements, writes through CTEs, metadata and file-function denial, semicolon handling, clean state, row caps and actual recursive timeout. Feedback tests cover malformed/leaking JSON and timeout fallback. Profile tests cover identity/record separation. Compose inspection and HTTP/browser evidence are recorded independently. These checks establish tested boundaries for the local subset, not a general penetration test.
