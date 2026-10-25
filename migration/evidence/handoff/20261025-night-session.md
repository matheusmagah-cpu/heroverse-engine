# Handoff 2026-10-25 22:15 UTC (session_01UF5QVCPyk1KywgwBkFn7GG → new main session)

The owner asked for a fresh session (it loads the Pavo MCP v0.3 with frames and references) and to archive this one.
Read `20261025-session.md` first (today's decisions); this file lists only what changed after it.

## Done tonight
- **E85 (#384, merged):** the 2026-10-13 release hit GitHub's 1000-asset limit. `migration/ci/assets.sh` writes to
  `v0.0.0-cloud-assets-20261025` (created on first upload) and reads newest first. `shorts.yml`/`shorts-review.yml`
  are byte-frozen by tests and still use only the old release: a new upload from `shorts.yml` fails until the owner
  lifts that freeze.
- **Pavo live test (branch `claude/pavo-test-20261025`, no PR by the owner's instruction):** one Flash 6 s 9:16 clip after a fresh exact
  0-credit quote: 720×1280, 24 fps, 6.59 s, clip_check clean, no watermark, **audible AAC audio despite sound:false
  (strip with -an)**. Evidence: `migration/evidence/pavo/20261025/`. The CDN host `cos-aigc-default.agnes-ai.space`
  is now allowed by the owner.
- **Pavo MCP v0.3 (#385, merged):** `pavo_quote_video`/`pavo_generate_video` take `first_frame` (+ `last_frame`) or up
  to 5 `references` (repository PNG/JPEG paths); ratios 9:16, 3:4, 1:1, 4:3, 16:9, 21:9; 4-12 s. Quotes of 12 s 9:16,
  10 s 16:9, 4 s 1:1 were exactly 0. The upload storage host is not yet observed: if blocked, the call fails with
  `PAVO_UPLOAD_HOST_UNREACHABLE` before any job; give the owner the host name to allow.
- Every Pavo generation needs the owner's explicit approval in the chat (the auto-mode classifier blocks it otherwise).
- **Genesis 5 Short** scheduled 2026-10-26 13:30 UTC (publish-episode run 40234795984).

## In flight (do next)
1. **Genesis 6 Short, slot 2026-10-26 23:30 UTC.** Draft script on branch `claude/genesis-06-short`
   (`migration/production/bible/drafts/genesis-06-short.json`): kjv_check PASS, short_problems PASS (~74 s, 71 %
   our words). Hook visual: the Pavo clip (audio stripped). After 00:00 UTC (vidIQ daily budget resets; 198/200 used
   on 25/10): voiceover, stock picked by preview frames + clip_check, compose with `cut` only, `clip_check --composed`,
   Claude review ≥ 9.5, move the record to `episodes/`, publish-episode.yml with publish_at 2026-10-26T23:30:00Z.
2. **First live test of v0.3** (owner approval per generation): a first-frame clip from an approved still, then Eve in
   reference mode (`production/characters/`).
3. **pilot-015 footage:** beats-1 re-dispatched on the fixed main after E85 (footage.yml, queries
   `migration/production/pilot-015/beats-1.json`); beats-2 (run 40218510076) ran on the old code and will fail at its
   upload: re-dispatch it with `beats-2.json`. Then map clips to `shots`, stills, preview, review, render (publish 28/10 10:00).
4. **Agnes keyframe test** (agnes-clip.yml 20:35 run) failed `AGNES_QUEUE_FULL` (provider queue, not code).
5. TikTok: Genesis 3 QUEUED in Buffer; Genesis 2 FAILED once (E80, fixed): check the next runs.

## Plugins and connectors (checked 22:10 UTC)
- Connected and loaded: vidIQ, Higgsfield (read-only), Runway (paid: denied), adplane (ads on hold), manifold (paid
  credits: do not use), heroverse-pavo (local MCP).
- Account plugins show as not enabled in cloud sessions; an install card for vidIQ, Social Media Skills and hookify
  was shown to the owner. Not suggested: schedulers and paid tools (CLAUDE.md).

## Scheduled tasks
The hourly clock (minute 14), the 08:05 UTC daily analysis and the 09:47 UTC vidIQ mining are re-created bound to the
new session; the copies bound to session_01UF5QVCPyk1KywgwBkFn7GG are disabled, not deleted.
