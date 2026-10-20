# Long qualification before Shorts

Owner directions at2026-10-19 23:55–23:57 UTC clarified that the system approves/rejects, and obsolete conflicting active instructions should be replaced. SYSTEM now has one automatic-governance instruction. No owner visual approval is asserted. Frozen QA bytes and every numeric/rights/model/structure/authenticity requirement remain unchanged; source hashes are in verification.json.

Three previously distinct paths are covered: the renderer no longer calls Shorts models before long QA; production/review workflows require current-script frozen-v3 long qualification through publication_binding before spending quota; reconcile suppresses Shorts while a pending long is in the existing quota cooldown, and permits only qualified-long Shorts. approve explicitly starts downstream Shorts after long PASS. The input-triggered job can wake before approval but exits without model work. Direct Shorts-review is also guarded.

6 prerequisite tests,14 queue tests,11 runner tests and all38 CI scripts PASS. Shell syntax and card interfaces pass. Workflow triggers, permissions, concurrency and secret references are unchanged. The existing publish step and scheduled slot remain unchanged. No dispatch occurred in this patch.

Limits: this is ordering and evidence-binding correctness, not a claim of cinematic quality or audience performance. Existing already-running independent jobs are not atomically preempted or globally quota-reserved. No quality rule was weakened; UNKNOWN/ERROR and malformed evidence remain blocking. A terminal failed long is no longer a valid source for Shorts in this revised scope.
