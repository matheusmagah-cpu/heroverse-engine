# HeroVerse: current decisions

`../SYSTEM.md` is the single operating contract. This page records current generic policy only; execution and the
next concrete action live in `../evidence/handoff/CURRENT.md`. Historical decisions remain in Git history and their
original evidence. This page is not a historical task queue or a second production ledger.

## Current policy

- Deliver the English KJV Bible series in story order: Short09, Short10, Short11, then the next planned Short and
  the existing arc-01 long. Preserve valid construction and original accepted audio where it is reachable.
- Owner, 2026-10-31 ("faça o que for mais entregue o que eu pedi.. como vai fazer voce escolhe.. só não mexe nas do
  pavo"): the accepted Short09 master exists only in a prior executor's private package and its review route is
  closed, so Short09 is rebuilt through the repository's own episode route from sources the repository, its releases
  and workflows can reach. The plan's structure, voices and timing are kept; unreachable accepted audio is regenerated
  only on the same pinned Kokoro voices and settings. Existing Pavo clips are never regenerated, recut in content or
  replaced; they are used as stored (release asset or saved provider ID read by GET). New visuals other than the hook,
  speaking characters and the Keeper's close are animated FLUX stills or licensed footage, each with a second option.
- Build within the 9.5 quality parameters before final review. Review the actual complete audio/video, retain
  grounded defects and require overall ≥9.5 before a new upload. Never manufacture scores or approvals.
- Bible Shorts use the existing episode route and `publish-episode.yml`. Longs use their existing build/handoff and
  `approve.yml` → `prepublish_gate.py` → `publish.yml`. An upload completes only after public/processed readback.
- Native Gemini audio/video review for Short09 is authorized by the owner. Record the real model, exact file and
  sampling/coverage. Actual session reviews likewise identify the performer and what was heard and seen.
- Pavo is first for the hook and speaking Keeper/characters when its zero-cost and media checks qualify.
  The authorized silent Keeper Plan B retains the original narration and requires its own still-mouth evidence.
- Appropriate other visuals may use licensed/public-domain footage and GPT-generated stills with cinematic
  motion. Retain truthful rights/provenance and distinguish camera motion from acted motion.
- No new spending or paid fallback. Use current cost/capacity evidence and existing ledgers; reconcile uncertain
  provider jobs instead of repeating them.
- Owner, 2026-10-31 (Buzzy track): to get flow, a Short may be produced as a whole by Buzzy (prepaid annual
  plan, its cheapest adequate model, credits managed to last the year), with Pavo only for the hook and the
  Keeper's close. The owner set the 9.5 floor for image-only videos; for this Buzzy track the bar is "coherent,
  a minimum of appearance and a good layer of originality". Concretely: our own KJV script, narration, Keeper
  commentary and captions are the originality layer (never Buzzy's agent rewriting the script); hard refusals stay
  (KJV text exact, God never shown as a figure, nothing modern, no on-screen AI text or watermark, AI disclosure,
  technical/loudness checks); the audiovisual review floor for this track is 8.0 overall with every item >= 7.
  The 9.5 floor and the frozen QA stay unchanged for the existing image/Pavo track and for longs.
- Owner, 2026-10-31 (correction): Pavo generates VIDEO only for the hook, character-specific spoken lines and the
  Keeper's closing lines, nothing else; plus the one exception the owner named: the episode's THUMBNAIL image may
  be made in Pavo, built from the mined package rules (character close-up, emotion, few words) to be striking and
  irresistible. No other Pavo images (scene stills, probes) and no Pavo video elsewhere: its quota is kept for
  those. Every other visual is an image not generated in Pavo: public images (`public_sources.py`) first, then
  Buzzy's lowest-credit image model as support, then FLUX when available.
- Owner, 2026-10-31: Pavo is the main video source ("temos o pavo como principal"). Buzzy (annual plan already
  paid, connected as the claude.ai connector `https://mcp.buzzy.now/mcp`) is support only, when Pavo, FLUX
  stills and licensed footage cannot cover a shot, and always with the lowest-credit model that meets the shot
  ("utilize no modelo de menor gasto"). Read the balance before and after each generation, record model, credits
  and purpose in `evidence/buzzy/ledger.json`, and never buy credits or upgrade. Not new spending: prepaid credits.
- Keep the shared executor lease, heartbeat, durable requests and current supervisors. Do not add a scheduler,
  parallel ledger or generic approval system to continue an existing delivery.
- Restore two daily Shorts only when completed masters sustain it; preserve the long and the existing reserve
  target. Re-anchor missed dates to actual qualifications and readback. No count or revenue promise replaces quality.
- Ads and the digital product remain on hold.

## Evidence-led changes

Keep measurements in the existing evidence/learning records with their source, observation time, comparison age
and limits. A sparse sample is inconclusive. A strategic change needs the existing high-confidence evidence
standard; change one supported attribute and measure its result. Proven defects and policy failures are fixed
immediately without waiting for an audience experiment. Frozen criteria are not edited to improve a result.

Update the relevant current guide when a valid owner decision changes behavior. Remove the superseded instruction
instead of appending its contradiction. Keep receipts, source approvals, revocations, QA and idempotency history;
a record is not obsolete merely because it is old.

## Buzzy track: defect-finder review and the posting flow (owner, 2026-11-01; E250)

Owner: "já tem vídeo pra publicar.. tem uma meta.. e tem que ser atingida". His bar for a Buzzy video is "algo
coerente... um mínimo de aparência e uma camada de originalidade boa". The owner approved this final design: for a
plan/record with `"track": "buzzy"` the Gemini native review is a defect finder (eyes and ears only; its prompt drops
the 9.5 floor and score anchors and lists, with timecodes and a category, only: [a] speech cut off mid-word or
mid-sentence; [b] a scene that does not match its line or breaks story order; [c] audio errors; [d] captions out of
sync or unreadable; [e] policy problems; [f] broken or glitched clips; mild AI artifacts are `[info]`; it still returns
the rubric scores, as information). Publication does not gate on scores: `publish_episode.review_problems` requires the
same file sha, a designated reviewer, an issues list, `review.publish_decision` = `publish` by
`claude-session-reviewer` with a note, and `review.defects` classifying every issue; an unresolved [a], [b] or [e]
defect is refused. The Buzzy-shot ledger check, policy and frozen QA are unchanged. The image/Pavo track and every long
keep the 9.5 prompt and floor.

Hard limits of the flow, in the owner's words: "o que não pode é ter fala cortada sem sentido ou o vídeo sem
sentido.. tem que estar bom!" (1) no line of speech cut off mid-word or mid-sentence; (2) every scene makes sense
with the line it carries, in story order. They are the only reasons for the single fix round.

His posting flow, in his words: "precisamos de fluxo de postagem.. não precisa ficar nesse preciosismo.. faz algo bom
e sem papagaiada.. as duas ferramentas fazem vídeos bons já.. só edita.. deixa coerente.. camada de originalidade é
autenticidade e posta." Operating flow for every Short:

1. KJV script and plan.
2. Buzzy clips on the cheapest model at >= 720p, plus Pavo for the hook and the Keeper close (exact 0-credit quote).
3. One edit with `episode.yml`.
4. One Gemini native review, used only to catch defects against the buzzy floor; no regeneration loops.
5. Publish at the next slot.

At most one fix round, and only for a real defect (a broken clip, an audio error, a policy problem). No rework for
cosmetic AI artifacts.

Pacing rule (owner, 2026-11-01): "Referente ao ritmo você mesmo acelera ou desacelera o vídeo criado mediante cada
cena.. não precisa ficar fazendo e refazendo.. trabalha com o que tem.. não quero retrabalho.. faça bem os prompts e
vamos pra cima." A clip too long or too short for its line is retimed in the edit or trimmed, never regenerated;
quality effort goes into writing good prompts the first time. Existing support: `short_engine.speed` slows a clip up
to `MAX_SLOW` 1.3x to fill its span (never loops), a shot may carry an explicit `speed` (1.0-1.3, `explicit_speed`),
`src_start` trims the clip's start, `hold` freezes a talking clip's last frame (<= `HOLD_MAX` 1.3 s). Speeding a clip
up beyond 1.0 is done by trimming (`src_start`/shorter span); a 0.75x-1.5x speed-up range is not built.
