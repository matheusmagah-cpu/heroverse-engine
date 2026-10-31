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

State on 2026-10-31 23:10Z: all 22 shots approved (5 FLUX stills, 8 Pavo agnes-image stills made at 0 credits and
kept by the owner, 7 earlier approved stills, k-question's released genesis-08 Pavo clip); thumbnail APPROVED (Pavo
image with ch-noah refs, E239 crop, E241 grade); preflight PASS. `episode.yml` run 41248615742 built master
d731b1ab…6206 (77,852,043 bytes, 174.39 s, -14.5 LUFS, 52 cuts; release asset bible-genesis-09-short-sha256-d731…).
`native-review.yml` run 41250892924 (gemini-3.8-flash, Free Tier proof read by the owner at 1793487327) completed:
**overall 6.8, not publishable** (every criterion 6.5-7.2). Its timed issues (public evidence artifact): 0:00-0:06 a
still with panning instead of natural motion; 0:23-0:40 the animal shots read as rigid and static; 1:39-1:48 water
against the figures and hull has no fluid motion; 2:29-2:45 the Keeper portrait speaks by voice-over with no mouth
movement. Round 1 of 2 failed.

## Next action

The defects are the source route itself (camera motion over stills; a silent Keeper portrait), not one shot. A
second round on the same route would repeat them. Owner decision needed before round 2: actual motion for the named
shots (Pavo video is limited to the hook, character lines and the Keeper's close; Buzzy video is support only) and a
talking Pavo Keeper for k-insight/k-question/k-close (Pavo video, exact 0-credit quote, lipsync gates). Then rebuild
with `episode.yml` and re-review with a fresh Free Tier readback (gemini-3.8-flash RPD 8 left on 31/10 22:56Z).
Publish only at overall ≥9.5 with every criterion ≥7, through `check-record` (the review gate of #575) and
`publish-episode.yml`. genesis-10 and genesis-11 follow; each needs 18 stills.

## Keep the established rules

Pavo is used only for the hook, speaking characters and the Keeper's close, with a fresh exact zero-credit quote,
GET-only reconciliation of saved jobs, no retry and at most two unread jobs. God's words stay exact KJV on Kokoro and
God is never depicted. No source or final score is invented. The long uses its separate route.

The existing heartbeat and supervisors remain; no new clock or queue is needed. Update this handoff at the next
accepted boundary, keeping historical receipts as evidence only.
