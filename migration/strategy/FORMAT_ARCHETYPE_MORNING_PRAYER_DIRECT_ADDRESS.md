# FormatArchetype candidate: Morning Prayer, direct address (10–30 min)

Status: **CANDIDATE, from measured evidence. Pilot not yet approved.** Built 2026-10-17 by Claude Code (AI assistant), following `docs/03_MODELING_SPEC.md` §5 and the monetization decision of 2026-10-13. It is a hypothesis set for the modeler. It is not a causal rule, a forecast or a production/publication authorization.

## Evidence base
- Market: `migration/evidence/market-opportunity-20261017.json`. Eight official observer captures from 14–16/10 cover 367 videos in 11 channels; interval growth is measured in views gained per day between captures. Within the reference set, the 10–30 min and 30–60 min strata with the highest growth are "Morning Prayer" narrations (top: 7,564 views/day at 30 days old). In 3 h+, the leader is seasonal ambience ("Cozy Fall Day With Jesus", 8,087 views/day).
- Audiovisual: `migration/evidence/av-cohort-comparison-20261017.json`. Openings 0–40 s of winner, median and weak videos from 3 channels (9 videos) were acquired through the free route and measured with the qualified meter (count/timing), semantic layer (speech/music/words) and profile (cuts, loudness, colour).
- Limits: n = 3 per cohort; openings only (40 s); public views only (CTR, retention and revenue of these channels are UNKNOWN); reference channels were pre-selected for a prayer niche.

## Shared grammar (all 9 openings): format invariants
| Feature | Measured range |
|---|---|
| Spoken narration from 0 s | speech present in 93–95% of frames; no singing |
| Speaking rate | 140–150 words/min |
| Music bed under the voice | present; lower share in winners |
| Editing | 28–36 picture changes/min; median shot 1.3–1.9 s |
| Loudness | −14.9 to −16.8 LUFS integrated |
| Image–sound | cuts are not placed on audio onsets |

## Winner vs weak differences: hypotheses to test, not rules
1. **Hook = direct second-person address plus a concrete present moment.** The 3 highest-growth videos open this way ("Good morning, beloved. Before you get out of bed, before you check your phone…"; "Today, I want you to make a decision before we pray…"; "This morning, there is no need to pretend…"). The 3 near-zero-growth videos open with a first-person petition ("Heavenly Father, I come before you…"). One winner-by-rank (0.5 views/day) also opens that way, so the rule is not absolute.
2. **Voice forward.** Winners are louder (−14.9 vs −16.8 LUFS median) with less music presence (0.34 vs 0.43).
3. **Slightly calmer cutting.** Winners hold shots longer (1.9 vs 1.3 s), with more motion inside the shot and brighter images.

## Causal chain (03 §3), filled where evidence exists
audience: English-speaking Christians starting the day → desire: peace, guidance and protection before the day's pressure → theme: morning surrender / gratitude / breakthrough (winner title terms: *faithful, way, need, breakthrough, spirit*) → angle: OWN (see below) → packaging: "Morning Prayer" + concrete benefit in the title → expectation: a prayer to pray along with → **hook (0–8 s): address the viewer, name the moment they are in, promise what the next minutes do** → progression: invitation → scripture-anchored reflection → guided prayer → declaration → payoff: a calm, specific commitment for the day → CTA: soft, after the payoff.

## Originality requirements (08_POLICY_AND_RIGHTS, YPP inauthentic-content rule)
- The script must be original text written for HeroVerse, with its own angle, question and payoff. No reference wording, sequence or voice is reused.
- The voice must be HeroVerse's own (preserved Kokoro `am_michael`, already approved in its test scope). No imitation of a reference narrator.
- The music must be owned or licensed. The preserved owned music source is reused only with its rights record.
- **Visuals are the open blocker.** 28–36 cuts/min need many rights-cleared shots. No rights-cleared visual library is attached yet, and a single static image contradicts the measured grammar.

## Gates before a pilot
1. Approve this archetype for a pilot (contract F4 gate: "usuário aprova um arquétipo para piloto").
2. Choose a visual source with documented rights at zero cost.
3. Original script and TakePlan → render → existing QA gates (loudness target −15 ± 1 LUFS, speech intelligibility via ASR WER, meter and semantic checks against the archetype) → approval → publication within the D-047 envelope.

## Amendment 2026-10-17: visual grammar (after the pilot-001 review)
The "28–36 picture changes/min" above counted **caption changes**, not scene cuts (see `production/pilot-001/inspection/REVIEW.md` and `diagnostics/av-picture-change/references/SPOT_CHECK.md`). Corrected visual grammar for this archetype:
- a title card in the first 1–2 s, matching the thumbnail promise;
- one persistent central figure (Jesus in prayer) at the left ~40% of the frame, the same across the video;
- backgrounds behind it changing about every 6–13 s;
- a large caption box at right-centre showing the spoken line, changing every ~3–4 s and synchronized to the voice;
- persistent channel mark, a rotating subscribe/like badge and a "Type AMEN" prompt.
The "Visuals are the open blocker" item is resolved for pilot-002 by open-weight generated stills (SDXL base 1.0, CreativeML Open RAIL++-M). Its licence and revision are recorded per image.
