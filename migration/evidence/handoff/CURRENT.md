# HeroVerse: current continuation

Read `../../SYSTEM.md` for the operating contract and `../../OPERATIONS.md` for existing entry points.
This is the only active public handoff. Media, private provider identifiers and exact receipts stay out of it.

## Current delivery

**genesis-09-short is rebuilt through the repository's own episode route** (owner decision of 2026-10-31 in
`../../strategy/DECISIONS.md`). The earlier accepted master (sha256 bf98d9…) exists only in a prior executor's private
package; its native review ended in a provider error with no grade and its recovery route is closed. That master and
its private Keeper drafts are not reconstructed or transferred; no score of theirs applies to the rebuild.

Route: plan `plans/genesis-09-short.json` (structure and lines unchanged) → approved stills (`scene_stills.py
approve`) and `shots/genesis-09-short.json` → `episode_build.py preflight` / `verify-preflight` → `episode.yml` →
`native-review.yml` on the new master (new sha256) → episode record and `check-record` → `publish-episode.yml` →
public/processed readback of the same video ID.

State on 2026-10-31: 9 of 22 shots approved (s-voice, s-finished, s-sky, s-float, s-peak-crowd, s-drift,
k-insight, k-close as Keeper stills with Kokoro voice-over, k-question as genesis-08's released Pavo clip, used as
is). The remaining 13 scene stills are DRAFT: 7 FLUX prompts now name the period robes positively (s-pairs, s-lions,
s-music, s-windows, s-springs, s-climb, s-hills); s-rock's man matches s-drift's; the other prompts are unchanged. The OpenAI
candidates of 29/10 cannot be approved (their exact prompts were never recovered: STILL_PROMPT_CHANGED).

## Next action

1. Under a current shared lease, run `scene-stills.yml` for the DRAFT shots within the day's FLUX allocation (E134),
   review the candidates image by image, approve ≥9.5 by PR; a shot with no qualifying still gets a second option
   (new FLUX wording or licensed footage through `footage.yml`).
2. With all 22 shots approved: `episode_build.py preflight` (local pinned Kokoro), commit, `episode.yml`.
3. Native review needs a current AI Studio Free Tier readback bound to the configured key (verified within the hour
   before upload); the owner supplies it, nothing is assumed. Every criterion ≥7 and overall ≥9.5, then record,
   `check-record` and `publish-episode.yml` at the next slot (13:30 / 23:30 UTC). Below 9.5: fix exactly the timed
   issues in the run's public evidence artifact, rebuild and review once more; stop after two failed rounds.
4. Then genesis-10 and genesis-11 on the same route.

## Keep the established rules

Pavo is used only for the hook, speaking characters and the Keeper's close, with a fresh exact zero-credit quote,
GET-only reconciliation of saved jobs, no retry and at most two unread jobs. God's words stay exact KJV on Kokoro and
God is never depicted. No source or final score is invented. The long uses its separate route.

The existing heartbeat and supervisors remain; no new clock or queue is needed. Update this handoff at the next
accepted boundary, keeping historical receipts as evidence only.
