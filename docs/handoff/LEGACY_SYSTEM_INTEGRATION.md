# Future integration with the original SQL feedback backend

The complete Year 1 backend repository/API is unavailable. The ai-cs411 demonstration and paper titles are context, not an implementation contract. No speculative request/response schema or compatibility claim is implemented.

Current replaceable boundaries: grader.py (deterministic SQL semantics), feedback.py (context/provider/output), graph.py (provenance/review), store.py (records/profiles), sources.py + ingestion.py (authorized submission normalization), dashboard.py (presentation), pl_bridge.py (supported PL lifecycle). Keep thin PL hooks and tested contracts even if backend internals change.

When access is authorized, first read architecture/schema/license and run it in an isolated environment with synthetic data. Compare SQL dialect/reference semantics, concept ontology/direction, identity/consent controls, retention, error/fallback model, latency/cost and deployment dependencies. Map only documented interfaces; preserve provenance/version adapters and compare identical synthetic attempts.

| Choice | Criteria | Acceptance gate |
|---|---|---|
| Reuse backend unchanged | Supported API, verified rights, equal or better safety/quality and maintained deployment | Contract/SQL regression/E2E pass; no hidden grading/inference change |
| Wrap selected components | Valuable diagnosis/analytics with incompatible internal schema | Versioned mapping, explicit discrepancies, reversible feature flag, measured benefit |
| Keep existing integration | Missing rights, unavailable runtime, unsafe/unmaintained service or no demonstrated improvement | Document comparison evidence; avoid duplicate persistence or graders |
| Rebuild a boundary | Specific unmet requirement cannot be met by either implementation | Approved requirement, bounded change, migration/rollback plan and tests |

Potential PostgreSQL/Neo4j reuse requires evidence of benefit at target load; their presence in a described prior system alone is insufficient reason to replace working SQLite fixtures. Human action is limited to repository access/rights and research decisions. Engineering audit, adapters, migration tests and implementation remain autonomous work once those facts exist.
