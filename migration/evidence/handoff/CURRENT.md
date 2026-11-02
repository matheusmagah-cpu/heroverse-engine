# HeroVerse: current continuation

Read `../../SYSTEM.md` for the operating contract and `../../OPERATIONS.md` for existing entry points.
This is the only active public handoff. Media, private provider identifiers and exact receipts stay out of it.

## Current delivery

**genesis-09-short is public**: https://youtube.com/shorts/IYSxVKTikSs (went public 2026-11-01 13:30 UTC; readback
`publish-episode.yml` run 41312558551 shows privacy public and the first comment posted). It was built on the owner's
posting flow (2026-11-01 in `../../strategy/DECISIONS.md`): Buzzy/Pavo clips edited for pacing (speed, trim, hold;
no regeneration), the Keeper's interpretive layer for authenticity and originality, then the Gemini native review as a
defect finder only (`track: buzzy`; unresolved cut speech, scene mismatch or policy defects block; the reviewing
session decides publish).

## Next action

1. genesis-10-short on the same flow, at the next free slot (13:30 / 23:30 UTC). The production routine (two runs a
   day) produces it. Do not start a second producer for the same episode.
2. The arc-02 Noah compilation long (G06–G09) goes through its own route: new Pavo hook and close from mining,
   compilation build, native review, `approve.yml` → `prepublish_gate.py` → `publish.yml`.
3. TikTok mirrors each public Short through `tiktok.yml`.

## Daily routine state (2026-11-01 17:30 UTC)

No Short was scheduled for the next 24 h, so genesis-10-short (bridge) was started: plan now `track: buzzy` (#635).
FLUX allocation for the day is exhausted (scene-stills run 41331046448: CF_DAILY_ALLOCATION_EXHAUSTED HTTP 429), so no
stills exist yet; no Buzzy or Pavo credit was spent. Next run after 00:00 UTC: scene-stills.yml for the 16 FLUX shots
(s-hold ... s-door-shut, candidates 1); s-voice and s-ararat name the ark prop and need the Pavo engine (E122) or the
plan's fallback (mountain top, no ark). Then approve stills by PR, episode preflight/build, native review, publish at
13:30 UTC. No long-first long exists yet, so there are no cuts. TikTok runner: `playwright` missing on the PC.

## Keep the established rules

Pavo is used only for the hook, speaking characters and the Keeper's close, with a fresh exact zero-credit quote,
GET-only reconciliation of saved jobs, no retry and at most two unread jobs. God's words stay exact KJV on Kokoro and
God is never depicted. No source or final score is invented. The long uses its separate route.

The existing heartbeat and supervisors remain; no new clock or queue is needed. Update this handoff at the next
accepted boundary, keeping historical receipts as evidence only.

## Long-first long: flood-ends-long (2026-11-02, after PR #646)

Merged (#646): `plans/flood-ends-long.json` (buzzy-long, Genesis 8-9, 33 shots, ~530 s est.) with 30 ChatGPT-desktop stills
APPROVED (claude-session-reviewer, 9.5, frames actually viewed; the vessel in wind/fountains/wait7/ararat/exit/raven/dove-out
has a rounded hull, flagged for the native review). `plan_check --strict` is clean. The orchestrator session made the 30 images
in one ChatGPT chat after restarting the window and deleted the per-image chats.

Next, in order (`episode_build.py preflight PLAN` is BLOCKED, 2026-11-02):
1. VOICE_NOT_MEASURED: needs a local Kokoro python + prepared work (`preflight PLAN --voice VOICE_PYTHON WORK --refs --write`);
   none exists in the cloud sandbox: measure it on a host with Kokoro (or the PC) and commit the PASS preflight.
2. PROBE_REQUIRED k-insight, k-bow, k-close: each voice-over Keeper shot needs >= 2 direct 0-credit Pavo generations judged by
   lipsync_check --still-mouth (evidence/pavo/setups.json). Option: reuse an existing matching Keeper clip/still.
3. Then shared lease, `episode.yml`, merge report, `buzzy-long-pilot.yml`, native review, thumbnail, approve -> gate -> publish,
   then the cuts (cuts/flood-ends-long.json). No Short/bridge was made this run (owner's one-run exception).
