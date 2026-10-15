# Security model and explicit limits

Trust boundaries are SQL → SQLite worker, untrusted student/lecture text → model context, model JSON → feedback gate, authorized export → strict synthetic repository, and local runtime → public Git publication.

The SQL worker uses a parser-level authorizer, query_only, function/table allowlists, one-statement execution, fresh memory databases, stripped environment, process/progress/row/value/CPU limits and no extension loading. It is not an OS sandbox against a compromised SQLite binary. Public hostile workloads need dedicated non-root runtime isolation and resource quotas.

The dashboard binds loopback, checks Host/Origin, validates bounded JSON/form inputs, escapes HTML, does not log SQL/query parameters, and returns safe correlated errors. It has no institutional authentication and must not be port-forwarded. A separate production service needs approved authentication/authorization and threat review.

Model calls are disabled by default. A key alone does not authorize spending. Nonlocal compatible inference requires HTTPS, an API key and explicit paid-use authorization. Redirects, excessive output and unsupported citations/concepts are rejected. Output filtering is conservative and cannot prove the absence of semantic answer leakage or prompt injection.

Publication excludes all artifacts/research checkouts/raw course text/real graph evidence/weights/data/recordings. The history scanner inspects reachable Git blobs and current prospective files; reviewed non-secret detections are restricted by exact hashed value/type, not entire paths. No blanket license is invented. See SECURITY_AUDIT.md for actual findings and CI limitations.
