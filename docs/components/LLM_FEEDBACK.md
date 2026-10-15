# LLM feedback component

The existing CompatibleProvider is extended, not replaced. `ProviderConfig` validates deterministic/local/compatible modes, endpoint scheme/credentials, model, 0.1–15s timeout, 32–500 output tokens and 0–2 retries. Default: deterministic, eight seconds, 350 tokens, zero retries. Remote compatible HTTPS additionally needs an environment key and SIIP_ALLOW_PAID_API=I_AUTHORIZE_PAID_MODEL_USAGE after explicit user authorization. No paid call was made during offline hardening.

Baseline gets question/SQL/safe grade. RAG adds the top bounded lexical page excerpts from the real local lecture corpus, with original checksum/page provenance. KG adds diagnosis, concept mapping, provisional/reviewed edges, original unreviewed judgments and available mastery. All modes use one base model and generation settings. Prompt version is siip-feedback-v3. Native page retrieval is not fresh InstructKG extraction.

The client rejects redirects and responses over 64 KiB, sanitizes usage metadata, and retries only selected HTTP errors within explicit bounds. Timeouts are not retried automatically. Provider 401/429/5xx errors become safe codes; response bodies/secrets are not logged. Malformed output, invalid concepts/citations, excess text and SQL disclosure trigger fallback; missing lecture/KG context is labeled context_error_fallback rather than sent as a complete research condition.

Contract tests use a mock HTTP model server and are not live inference evidence. Actual live Baseline/RAG/KG verification remains BLOCKED until approved resources/usage are supplied. The evaluator supports an explicit live flag and reads literal ignored .env values without shell evaluation. Provider availability is never inferred from a health endpoint or an API key's presence.

## Follow-up precision

Prompt version is now siip-feedback-v3. Only relevant numeric concept aggregates enter the history field; identity/raw historical SQL/free text are stripped. A deterministic history cue differs for contrasting synthetic histories. This is verified through the separate post-submission principal service, **not the immediate anonymous PL hook**. Live model inference is still blocked. See [capability distinctions](../research/FEEDBACK_CAPABILITIES.md) and [lifecycle](../architecture/PERSONALIZED_FEEDBACK_LIFECYCLE.md). Local endpoint/model/JSON-mode and failure contracts pass; Windows/GPU serving remains NOT_RUN.
