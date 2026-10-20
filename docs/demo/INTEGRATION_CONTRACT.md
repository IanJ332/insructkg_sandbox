# Integration contract — 2026-10-19

Baseline `5d1a3ec`; inherited, unverified demo snapshot `7b13fa0`. Original checkout and research databases remain untouched. Worktrees use separate branches and temporary test databases. Main alone owns the dashboard, queue/schema, authentication, global configuration and final services.

Critical audit findings controlling work: course/module controls missing; graph selection implicit; fresh uploaded graph not used by async feedback; project interest UI missing; extraction failure status incomplete; inherited video not truly uncut. Component tests: 23 passed; complete current browser path not yet verified.

Contracts: course → module → uploaded UTF-8 source/hash/version → graph/mode/version → persisted review → local published assignment → assessment-linked attempt → deterministic grade/profile → durable feedback job → reviewed graph grounding → EM/project review → event lineage. Keep existing public module methods backward compatible. Local publication is `PUBLISHED_LOCAL_DEMO`; grading is exclusively the existing deterministic grader. KG modes and feedback provenance must describe actual execution.

Ownership: authoring agent owns authoring/student adapters, audit and scoped negative tests; extraction agent owns KG/extraction adapter; recording agent owns recorder and browser evidence; main integrates shared files and runs release acceptance. No agent mutates final databases or deployment.

Research ZIP not located in supplied attachments or searched Downloads/Desktop/D:\\AI locations. The four objectives in the user request remain provisional requirements until the proposal can be read. No claim of having read unavailable PDFs is permitted.
