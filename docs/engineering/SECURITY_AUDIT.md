# Publication and security audit

The destination was independently verified **PUBLIC** before publication. The initial remote README commit was retained; no force push or history rewrite is authorized. NOTICE.md records rights boundaries; no blanket LICENSE is assigned without established rights.

Publication checks scan every prospective tracked/untracked nonignored file and every reachable historical Git blob using detect-secrets without provider verification. Restricted prefixes/suffixes fail closed. Only original integration code, owned synthetic teaching fixtures and sanitized documentation are publishable. Entire research/, artifacts/, PDF/text/real graph exports, databases, secrets, weights and recordings are ignored. Wheel contents are separately allowlisted and checked. Manual source review accompanies scanners; scanning is not a proof of ownership or absence of secrets.

The reviewed non-secret manifest accepts exact detector type plus hash for public upstream Git SHAs and literal negative-test values. It does not exempt paths or future keys. SHA1 here only matches detect-secrets identifiers and explicitly sets usedforsecurity=False; it is not an integrity/security primitive. No real credential was found. See publication-audit.json locally and sanitized verification.json publicly for final results.

Bandit runs maintained integration/scripts. B101 tool assertions and B404/B603 deliberate bounded shell-free subprocess use are configured exceptions. Specific B608 prompt text and B310 fixed loopback URLs are annotated; no broad severity suppression. The SQL subprocess, loopback API and provider response boundaries have adversarial tests. Final Bandit findings and pip-audit results are recorded, including tool scope.

Remaining risks: worker resource controls are defense in depth, not an OS container boundary on every platform; dashboard has no authentication and must stay loopback; escaped SQL/prompt content can still influence an LLM semantically; rule filters cannot prove no answer leakage; real student ingestion requires new identity/access/retention controls. Provider configuration has paid-consent gating, bounded responses and redirect denial but no production egress proxy.

GitHub receives no course PDF, extracted real lecture/graph payloads, raw educational records, model weights, runtime logs or screenshots. Public CI uses clearly synthetic fixtures. Hosted institutional deployment, real data and inference remain outside this audit. Owner branch-protection settings are documented recommendations, not silently changed.
