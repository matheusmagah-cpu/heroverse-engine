# Native review grounding: code boundary inspection

Reviewer: Codex. Scope: native_review.py validation/prompt and its offline test.
This is a code inspection, not audiovisual review or an external security-tool run.

- No endpoint, authentication, permissions, upload, retry, scheduler or publication code changed.
- Provider answers remain saved before validation; rejection cannot trigger another POST.
- Score values are never rewritten. Evidence links are type/range checked before indexing.
- No private media, provider URI, account data or recovery key is included in this change.
- Structural evidence cannot establish factual truth. A plausible invented quote can still pass the schema; independent exact-media consistency assessment remains required.
- Existing production and publication gates are unchanged. This patch must not grant approval.

Follow-up Codex code review: CI 40997416083 passed the original head. Seven regression cases then demonstrated that timestamp format alone allowed impossible fields and positions at/beyond the 175-second endpoint. The same E222 repair now parses timestamps and rejects those values; valid decimal MM:SS and HH:MM:SS cases are retained. This still does not establish factual correspondence within the video. No media inference or score mutation. PR review-toolkit execution remains outstanding; this record is a manual code inspection, not that plugin.

Validation: all 87 canonical suites passed locally for this follow-up, including 14 native-review tests. Two suites initially lacked OpenCV under isolated Python; both passed after exposing the already-installed dependency in a dedicated test environment, without source changes. The required pr-review-toolkit was not found in available integrations; no toolkit review or merge is claimed.
