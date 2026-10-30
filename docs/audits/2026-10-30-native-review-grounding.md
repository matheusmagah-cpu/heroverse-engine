# Native review grounding: code boundary inspection

Reviewer: Codex. Scope: native_review.py validation/prompt and its offline test.
This is a code inspection, not audiovisual review or an external security-tool run.

- No endpoint, authentication, permissions, upload, retry, scheduler or publication code changed.
- Provider answers remain saved before validation; rejection cannot trigger another POST.
- Score values are never rewritten. Evidence links are type/range checked before indexing.
- No private media, provider URI, account data or recovery key is included in this change.
- Structural evidence cannot establish factual truth. A plausible invented quote can still pass the schema; independent exact-media consistency assessment remains required.
- Existing production and publication gates are unchanged. This patch must not grant approval.
