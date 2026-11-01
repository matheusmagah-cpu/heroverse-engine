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

## Long-first long: flood-ends-long (2026-11-01 evening, branch claude/stoic-edison-gii4wc)

Plan `plans/flood-ends-long.json` (buzzy-long, Genesis 8-9, 33 shots, ~515 s est.) passes `plan_check --strict` except
STILL_NOT_APPROVED. 30 DRAFT still records exist. ChatGPT-desktop candidates (1920x1080 JPEG from the 1672x941 PNG, sidecars
with the PNG sha256) exist for: s-voice, s-hold, s-door, s-wind, s-fountains, s-lines (unreviewed for approval; the exterior
ark shots s-wind/s-fountains draw a rounded hull with a cabin, against the box canon: regenerate if the native review flags it).
STOPPED at s-ararat: the ChatGPT app showed the Codex/Work usage limit ("Voce esgotou o uso do Codex e do Work", reset 4 Nov
07:01) after a queue script mis-typed into the Work composer; not worked around. Resume: check the Chat tab can still make
images, then `C:\HeroVerse\one.ps1 -still <id>` per still (send, wait, save, upload candidate). Nothing approved, built or published.

Relayed by the coordinator session (owner preference, not yet confirmed by the owner in this run): use ONE ChatGPT chat named
"HeroVerse — stills" for all stills (create it once, send every prompt in it, download from each reply, same style line);
do not delete existing chats. `one.ps1`/`send.ps1` still open a new chat per still and must change before resuming.

Cleanup (relayed, apply only after ALL 30 stills are downloaded): delete the project's per-image chats ("Create ... Image"
titles opened today) via "..." > Excluir; keep "HeroVerse — stills" and every owner chat; ambiguous titles stay. Report the count.
