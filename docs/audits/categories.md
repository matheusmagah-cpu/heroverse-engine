# Security and correctness categories (verified-security-sweep)

A list of categories, not patterns. Each row says how the category is covered in this project and whether the
coverage is a sentence or a mechanical guard. When text and guard diverge, the guard is right.

| Category | Covered by | Enforced mechanically? |
|---|---|---|
| Secrets and credentials | Repository secrets only (`HERO_YT_AUTHORIZED_USER_JSON`, `HERO_GEMINI_API_KEY`, Cloudflare, Pexels, Pixabay, `HERO_RUNNER_PAT`); `.claude/claude-security-guidance.md` | Partly: security-guidance diff review; no secret scan in `pr-checks.yml` |
| Workflow script injection | Dispatch inputs passed through `env:` (`approve.yml`, `cf-images.yml`, `channel-config.yml`) | No |
| Runner token scope | `HERO_RUNNER_PAT` used to dispatch heroverse-runner `render.yml`, which writes results back to the engine | No |
| Publish gate integrity | `approve.yml` → `prepublish_gate.py` writes `APPROVAL.json` bound to `output_sha256`; `publication_binding.py` | Yes: `test_prepublish_gate.py`, `test_publication_binding.py`; hookify blocks hand-written approvals |
| Frozen QA criteria | SHA256 pins in `render_queue.py`, `script_check.py`, `prepublish_gate.py` | Yes: pinned hashes; hookify blocks edits |
| Failure turned into a pass | Missing, errored or hash-mismatched evidence blocks (`OPERATIONS.md`) | Partly: gate tests |
| Spend ceiling | vidIQ ledger `migration/evidence/vidiq/ledger.json`, ceiling in `production/bible/SERIES.md` | No |
| External integrations | YouTube Data API, vidIQ, Gemini, Cloudflare, Pexels/Pixabay: how each reports errors and quota | Partly: `ops/test_engine_fallback.py`, `ops/ERRORS.json` |
| Publish idempotency and concurrency | One publish per approved file; workflow `concurrency:` groups | Partly: 22 workflows declare `concurrency:` |
| Path containment for downloads | Stock and generated media written to code-chosen paths | No |
| Calendar day | Schedules in UTC (Shorts 13:30 and 23:30 UTC, `SERIES.md`) | No |
