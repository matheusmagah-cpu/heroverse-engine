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

## 2026-11-01 — Strategy reset: Shorts, longs and TikTok toward YPP, on automatic

Owner, 2026-11-01: "Resolva o que falta e já refaça a estratégia de longos e shorts e TIKTOK para alcançar a meta e
deixa lá no automático."

Measured on 2026-11-01 (daily report 09:41 UTC):
- 300 / 1,000 subscribers;
- 27.9 / 4,000 public long watch hours;
- 2,447 Shorts views in 90 days.

The best recent Bible Shorts reached 157-532 views each, held 72-85% of their length on average and gained 2-8
subscribers each. The prayer longs averaged 2-9 minutes viewed per view and received no traffic from Shorts. At this
rate 4,000 hours by day 30 (16/11) is not reachable; the YPP hours window is 365 days, so it is a target to accumulate,
not a cliff. Subscribers come from Shorts volume and consistency. Hours come only from longs with long average view
duration.

**Shorts**
- The Buzzy posting flow (above) is the only Short route: one Bible story per Short, in canonical order (genesis-10,
  genesis-11, then the next arc).
- Cadence: 1 Short a day at 23:30 UTC, automated; 2 a day (13:30 too) once the measured token cost of one automated
  Short fits the weekly budget twice daily.
- Each Short's pinned comment and description point to its arc's long.

**Longs (redesigned)**
- A long is the "complete story" of an arc, assembled from that arc's already-published Shorts: their accepted masters
  in order, framed for 16:9 with a blurred fill, joined by short Keeper bridges and one chapter card per story.
  Nothing is regenerated. Target length is 15-30 minutes.
- A second, sleep-oriented edit of the same material runs about 60 minutes: slower pacing, no hook music, a calm Keeper
  intro. The prayer longs' 8-9 minute average views show this audience watches long calm content.
- The long reuses the Short track's defect-finder review (no cut speech, no incoherent scene, policy). It still
  publishes only through approve.yml -> prepublish_gate.py -> publish.yml.
- Changing the long review from the 9.5 score floor to that defect gate is owner-directed here and is implemented as
  its own code change with tests before the first compilation long.
- First compilation: arc-02 (Noah: genesis-06 to genesis-09, all public).

**TikTok**
- tiktok.yml already mirrors every public Short through Buffer's free channel (8 posts SENT); it stays automatic, with
  no new spending.

**Automation**
- The 4 old clocks are disabled.
- One daily production session (fresh session, cheaper model) runs the Short flow end to end for the next plan and
  publishes at 23:30 UTC. Gemini's Free Tier proof is read on the owner's PC through Desktop Commander. If the PC or a
  provider is unavailable, the session stops and tells the owner; it does not invent evidence.
- Longs are built when an arc's Shorts are all public.

## 2026-11-01 — Quality, authenticity, originality and critical insight remain pillars (Shorts and longs)

Owner, 2026-11-01: "A gente mudou um pouco, né? Mas a qualidade ainda precisa ser um pilar... tem que entrar aí a
questão da autenticidade, originalidade e crítica. Não pode esquecer disso de jeito nenhum, nem no longo e nem no
short." And for the long: "o longo vai ter hook novo... e o fechamento tem que ser novo também... narração, tudo lá no
pavo... gerado pronto para só conectar no final e conectar no início... por isso que eu quero a mineração, para saber
como que vai ser o melhor início."

Every Short and every long carries the Keeper's own layer: an interpretive or critical insight (why the story matters,
what readers miss in the text, an honest question), stated as commentary and kept distinct from KJV scripture. A
script whose hook and close only summarize the passage is not ready.

A compilation long gets its own new hook and new close: Keeper Pavo video (exact 0-credit quote), made for 16:9 and
splice-ready at head and tail. The hook follows the opening structure measured from winning long Bible-story videos
(vidIQ mining, logged). Joins must be clean (no cut speech, no pop, consistent loudness).

## 2026-11-01 — Compilation long: hook, close and quality layer (owner, via coordinator)

The arc-02 compilation (Shorts genesis-06 to genesis-09, Noah) gets a NEW Keeper hook and close written for the long,
spoken by the Keeper in Pavo clips (fresh exact 0-credit quote, our Kokoro line, 16:9, still beat at each end),
and its hook is written on the structure measured in `evidence/vidiq/20261101/compilation-hook-mining.json`
(question that puts the viewer in the story, the stakes, the promise and scope, one marked critical insight).
Authenticity, originality and critical insight are mandatory in the long and in the Shorts: the Keeper's voice adds an
interpretive layer (what people miss in the text, an honest question) in KJV-faithful commentary clearly marked apart
from scripture. The review track is the defect gate (E251), implemented as `compilation-qa-criteria-v1`.

## 2026-11-01 — Token economy: more Shorts with the same tokens

Measured: 71.1M tokens in the first ~19 h of the week (budget 239M = half of the 478M weekly cap), a projection of
~630M, which is over budget. Most of it came from the long-context coordinator session and its agents, not from Shorts.
The owner asked to sustain the whole week and post more Shorts without spending more tokens. The goal is unchanged.

- Shorts: 3 slots a day (13:30, 18:30, 23:30 UTC). The production routine (Sonnet, fresh session, 06:43 and 16:43 UTC)
  makes a batch of 2 Shorts per run. Plans, clip submission, the lease and one Free Tier proof (valid 1 h) are shared,
  so the fixed cost of a run is paid once for 2 Shorts. Up to 4 a day are produced against 3 slots, and the surplus
  builds runway. The quality pillars (Keeper's interpretive and critical layer, coherent edit, no cut speech) are
  unchanged.
- Longs: compilation of each completed arc, built by Actions (no tokens). 3 Shorts a day completes arcs faster, so
  there are more longs for the same tokens.
- Clocks:
  - the coordinator's 4-hourly clock is off;
  - the Haiku light clock runs every 3 h and wakes the coordinator only on a failure;
  - the analysis runs every 2 days;
  - the vidIQ mining runs weekly (Monday).
  GitHub Actions (heartbeat, reconcile, TikTok, links) carry the mechanical work at zero tokens.
- Coordinator: answers the owner and failures only, with no recurring work in the long-context session.

## 2026-11-01 — Resource plan: no tool runs out, quality at the peaks

The owner asked for a measured budget per tool, free tools first, no tool overloaded, video where it matters and
images animated cinematically elsewhere. Balances measured today:
- Buzzy: 41,994 credits (header, 14:10 UTC). Seedance 2.0 mini at 720p costs ~58 credits a clip (234 for 4 clips).
  The credits are treated as a finite stock.
- Pavo: 1,474 credits, 0 daily free. Used only with an exact 0-credit quote, unchanged.
- vidIQ: 3,179 credits (2,959 renewable, reset 2026-11-18).
- Cloudflare FLUX: ~44 free images a day through `scene-stills.yml`. It runs in Actions, so it costs no Claude tokens.

Per Short (3 a day):
- Peaks in video. The 3–4 key action moments (climax, the KJV line, the turn) are Buzzy image-to-video, Seedance mini
  720p. The cap is 240 credits a Short, so 3 Shorts a day use ≤720, which lasts ≥58 days (past the YPP window). The
  balance is read in the owner's browser before and after each batch and written to the Buzzy ledger, so the cost is
  measured, not estimated.
- Pavo for 1–2 shots: the hook and/or the Keeper's close (direction and voice), at a 0-credit quote only.
- Every other shot is a free still animated cinematically in the edit (push-in, pan, parallax, light), with no
  generation cost:
  - stills come first from FLUX in Actions;
  - the owner's PC tools (AI Studio image generation, ChatGPT desktop app) are used only for a hero still FLUX cannot
    make, because driving a desktop UI costs Claude tokens.
- No regeneration for cosmetic artifacts. Retime, trim or replace with an animated still.

Longs: compilations of the public Shorts (Actions, no generation), plus the new Pavo hook and close at a 0-credit quote.

Mining: weekly (Monday), thorough, at most 900 vidIQ credits a run, so the balance lasts to the 18/11 reset. It uses
the validated-structure rule (≥6 winners from ≥4 channels, weak contrasts). The channel's own Shorts and longs are
read free from YouTube analytics (goal-report). Its findings change the Short and long formats only with that
validated evidence, and the authenticity, originality and critical layer (the Keeper's interpretation) is never
traded away for reach.

## 2026-11-01 — Comment replies on YouTube and TikTok, without rework

Owner: every comment answered by reading what the person wrote and replying to that, so the person sees a direct
answer, not a generic one. The mechanics already exist and stay:
- YouTube: `comment-replies.yml` (heartbeat, 6 a day) queues new comments and posts the decided replies (20 a day).
- TikTok: the local runner on the owner's PC (`migration/integrations/tiktok-local`, text-only, no screenshots).
- Both pass the same gate (`reply_policy.py`).

The missing piece was the writer, which was the retired 4-hourly clock. From now on, each production run (twice a day)
writes the decisions for the comments still undecided:
- reply in the commenter's language, 1–2 sentences, answering their exact point;
- be honest when they question the scripture: KJV quoted word for word, scenes dramatized;
- quote a verse only through the checked `verse` field;
- SKIP spam, hate and provocation (never argue);
- deliver them in its own PR.
TikTok runs only while the runner reports LOGGED_IN; the owner logs in by hand once (`runner.py login`).

## 2026-11-01 — Long-first, Shorts cut from the long

Owner, 2026-11-01: "Faça os longos e do longo faça os cortes para os Shorts e vá postando a partir do longo. É muito
mais fácil cortar uma imagem que já está enquadrada para o longo para um Short do que o inverso (a tela quebra).
Depois da compilação atual do Noé, ao invés de fazer Shorts, faça os longos e, dos longos, faça alguns cortes
COERENTES para postar como Shorts."

- After the current Noah compilation, each story (or arc) is made as a 16:9 long of about 8–12 minutes: plan track
  `buzzy-long`, built by the existing episode route at 1920x1080 with burned 16:9 captions; the caption-free master
  and the sentence/shot timeline are kept, bound to the master's sha256.
- Every picture keeps its subject in the centre 9:16 column (PROMPT_GUIDE "Long-first"), so the cut does not break.
- The Shorts are coherent cuts of that long (`short_cuts.py`): each starts and ends between sentences (no cut speech),
  lasts 20–179 s, and is a unit (recommended: hook line → beat → KJV line or the Keeper's insight). Each cut is its
  own file with its own native defect review and the session reviewer's decision; it links its parent long.
- The long publishes through approve.yml → prepublish_gate.py → publish.yml on its own defect-gated track
  (buzzy-long-qa-criteria-v1: the owner's defect finder, not the 9.5 floor). The 9.5 story-long track, the Short
  route, the compilation and every frozen QA file are unchanged. Implemented in E259.
