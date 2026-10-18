# Pre-publication validation reinforcement — 2026-10-18

Owner's 7-point proposal ("Análise com precisão"). Incremental: no architecture rebuilt, no valid approval reopened,
pilot-002 (v4zN53ZiUIs) not touched.

## 1. Evidence inventory and reuse

| Artifact | File / hash | Evaluator (version) | Scope | Result | Reused? |
|---|---|---|---|---|---|
| pilot-002 script | script.json `2cc30084…` | — | text | frozen | yes |
| pilot-002 render | output `d0c35d58…` (1,294.9 s) | qa_pilot, criteria v2 `49fedd2e…` | whole file, deterministic | QA PASS 24/24 | yes: same file, same criteria |
| pilot-002 approval | APPROVAL.json bound to `d0c35d58…` | owner, after frame-sheet review | perceptual | approved | yes: valid, not reopened |
| pilot-002 publication | receipt `pilot-002-39077626519.json`, ledger key `pilot-002:d0c35d58…` | publish_video (idempotent) | upload, thumbnail, captions, playlist | v4zN53ZiUIs scheduled | yes |
| pilot-002 final decision | out/gate.json (prepublish-gate-v1) | new gate over the existing evidence | all dimensions | UNKNOWN: no automatic watched review/scorecard/scan exists for this file (it was approved by the owner, which stays valid) | informative only |
| pilot-002 Shorts | shorts.json (5 files, hashes inside) | shorts_qa + watched review | per Short | short-02 PASS + selected (D-03); short-01 failed review; 00/03/04 passed, not selected | yes |
| pilots 003–006 | no render yet (003 rendering, runner run 39091018546) | — | — | — | — |

**Invalidation rules** (what a change forces to run again):

| Change | Re-run | Not re-run |
|---|---|---|
| title, description, tags, thumbnail | preflight | render, QA, review, scan (file unchanged, hash unchanged) |
| captions sidecar only | preflight, caption checks | render, picture checks |
| audio (voice, music, mix) | new render → new hash → everything bound to the hash | — |
| any re-render | QA, review, scan, gate, approval are bound to `output_sha256`; old approvals stop matching automatically (publish.yml asserts the match) | — |
| QA criteria | never edited for a rendered pilot; the gate fails a render whose criteria file differs from the frozen hash | — |

Technical approval ≠ perceived quality ≠ financial return: the gate's `not_claimed` field says so in every gate.json.

## 2. Mining-accuracy defects (fixed, PR #88)

| Symptom | Cause | Fix | Test |
|---|---|---|---|
| openings 0.733 < 0.80 | comparator borrowed lines across windows; miner kept windows with relative/rescaled times | window-local comparison; miner rejects out-of-window, unordered, one-line, truncated transcripts | `test_structure_mining` ×6, `test_accuracy_check` ×5 |
| 2 "no speech" windows with 71 and 65 ASR words | mined omission labelled no-speech | new state `ASR_SILENT_MINED_SPEECH` / `MINED_OMISSION`, counted as errors | yes |
| 8YXRtsNnGX0 0–30 s: 893 mined vs 64 ASR words | lines from other windows (times stamped outside the window) borrowed | `TRANSCRIPT_TIME_OUTSIDE_WINDOW` → window invalid, re-mined | yes |
| the 0.109 window | same as above (rescaled times) | same | yes |
| median hid grave errors | verdict on median | strict window pass rate (≥ 80% of speech windows ≥ 0.85) + openings ≥ 0.80; no speech/openings → UNKNOWN | yes |

Neither extractor was presumed right: each disagreement was traced to the timestamps and lines of both sides.
45/141 windows of `20261017` were defective. Honest re-run on the 12 windows used to find the bugs (tuning set):
**FAIL** (pass rate 0.50, openings 0.818). Re-mining dispatched (structure-mining run 39092143590); proof comes from the
holdout (`evidence/mining-accuracy-holdout.json`, criteria fixed before acquisition, videos never used). Until it
passes, transcript-derived numbers (wpm, beats, shots) are informative only (flagged in MODELING_SPEC and DECISIONS).

## 3. Evaluator validation

- **Mining evaluator:** tuning vs holdout separated; the holdout is acquired by the daily 00:20 job from videos never
  used before; independent signal = our own faster-whisper ASR of the native audio (not the same model with another prompt).
- **Watched review (long):** calibration with known answers (`review_calibration.py`, workflow `review-calibration.yml`):
  control reviewed twice + 5 deliberate defects (A/V desync 1.5 s, audio dropouts, degraded picture, 0.8 s black flash,
  60 s frozen picture). Expected answers fixed in code before the run. Results: `evidence/review-calibration/<pilot>.json`
  (filled when the run completes; see section 7).
- **Complementary signal added:** `signal_scan.py` — ffmpeg black/silence/freeze detectors over every frame and sample;
  covers what the 0.5 fps review can miss. Blocking: black ≥ 0.5 s, digital silence ≥ 3 s; frozen picture reported until
  calibrated on known-good renders. 4 synthetic known-defect tests.
- **Conflict rule:** any signal FAIL → FAIL; a signal missing or errored → UNKNOWN → no publication.

## 4. Final decision PASS / FAIL / UNKNOWN (PR #89, #91)

`publish/prepublish_gate.py` → `out/gate.json`. Only PASS makes a new render eligible. Per dimension:

| Dimension | Method (instrument) | Criterion |
|---|---|---|
| binding | sha256 of qa, manifest, review, downloaded file; criteria file vs frozen hash | all equal; else UNKNOWN (missing) or FAIL (mismatch / edited criteria) |
| technical | QA: full decode, 1920×1080 H.264 30 fps + AAC, duration ≥ 601 s | frozen criteria v2 |
| audio | QA: −16…−14 LUFS, true peak ≤ −1 dBTP, speech ≥ 0.85, no singing; review item ≥ 7; scan: no digital silence ≥ 3 s | all |
| transcript | QA: ASR WER vs script ≤ 0.10, 115–165 wpm, first word ≤ 1.5 s, 2nd person ≤ 8 s | all |
| captions / sync | QA: caption coverage of speech ≥ 0.95, hold median, ≤ max chars; review "captions readable and synced" ≥ 7 | all |
| image | QA: title card, figure ≥ 98%, background holds; review picture + figure integrity ≥ 7 (**sampled at 0.5 fps**); scan: no black ≥ 0.5 s (every frame) | all |
| rights / originality | QA: open-licence images with revision, no third-party footage, owned music, pinned voice | all |
| content & policy | review: opening, pacing, scripture on screen, policy-safe ≥ 7, overall ≥ 8 | all |
| scorecard | same miner as references: minutes 10.02–50, wpm, first spoken, scripture/10 min, coverage ≥ 0.9 | hard rows |
| preflight | YouTube limits, thumbnail, schedule, captions, units | no problem |
| informative (never decide) | winners' bands ("beat the reference"), frozen-picture scan | reported |

Timeout, quota, provider error, missing file, other-file evidence → UNKNOWN, never PASS (tests). approve.yml writes
APPROVAL.json only on PASS; publish.yml refuses an automatic approval without gate PASS for the same hash; reconcile
retries UNKNOWN (and ERROR), never FAIL.

**Shorts states** (`pending_shorts.py --states`): failed / not_selected / approved_awaiting_slot / scheduled / published.
pilot-002 now: 01 failed, 00·03·04 not_selected, 02 approved_awaiting_slot (07:35 run).
**NOT_ENOUGH_SLOTS:** real defect found — after a partial run, already-uploaded Shorts still consumed slots and their
(deleted) files were downloaded again. Fixed: slots, download and QA only for Shorts not in the ledger; duplicate
uploads impossible (ledger key per Short hash, tested); the Shorts step no longer hides failure behind
`continue-on-error` (a green run can no longer mean a failed Short).

## 5. Business indicators (PR #90)

| Indicator | Before | Now | Source class |
|---|---|---|---|
| Watch hours toward YPP | 76.9 h = all content 365 d incl. Shorts and private/removed videos, labelled "long-form" (wrong) | public long-form videos only, 365 d, per-video Analytics rows (content type when the API gives it) | own calculation (estimate of the YPP counter) |
| Shorts views toward YPP | 2,645 = lifetime views of public Shorts (wrong period) | public Shorts, last 90 d | own calculation |
| Subscribers | Data API | unchanged | official |
| "need X/day" | — | labelled plan arithmetic | plan |
| D-03 p = 0.062 | written as "93.8%" | not a 93.8% chance of success; observational, 48 channels (5/22 vs 1/26), not ours | — |

Contradiction fixed: OPERATIONS listed D-05 as active; it was reverted.

## 6. Retrospective predictability

- **Per-video forecasts:** no comparable history that avoids leakage. Our channel has 23 public videos in other formats
  (fear-bait Shorts, short reflections); pilot-002 is the first of the registered format. Market data is a single
  cross-section (panel 2026-10-17): later views of earlier videos are not pre-publication information. A per-video
  model now would be invented precision. **Not done; conditional scenarios instead (below).**
- **Channel-level forecasts:** a forward, leakage-free test already exists: `market-forecast-registered-20261017.json`
  (method, baseline "no change"/constant probability, pass criteria and ≥ 30 scored channels fixed before the outcome),
  scored automatically by every daily panel. First meaningful score at +7 days (2026-10-24).

**Pre-publication opinion per candidate** (same for each unless stated). Demand: queries "morning prayer", "night prayer
before sleep", "prayer for protection", "psalm 91", "prayer for healing", "scripture for sleep" all return 60–95
channels in the panel, and 2–3 of the 45 fast channels came through each. Comparable strategy (daily long ≥ 20 min):
5 of 22 channels reached the YPP proxy within 30 days (Wilson 90%: 12–40%), proxy assumes 20% retention, panel found by
search (survivor bias, so the true rate is likely lower). Our own baseline: the last long video before the new format
got 9 views, 3.1 h, 11% average view.

| Pilot | Length | Strengths | Risks / gaps | Eligibility |
|---|---|---|---|---|
| 003 morning, tired | ~14 min | QA-proven pipeline, warm hook | shorter than the 25–40 min strategy (control); CTA has subscribe ask (rendered before D-05 revert) | gate decides after render |
| 004 night, worries | ~30 min | sleep use → long sessions | first long night format, untested retention | needs render + gate |
| 005 morning, Psalm 91 | ~23 min | high-demand query | 6 images pending (Cloudflare reset 00:00 UTC) | needs images, render, gate |
| 006 night, healing | ~25 min | healing + sleep demand | health wording must stay promise-free (policy row) | needs images, render, gate |

Conditional scenarios (arithmetic, not forecasts): hours per video = views × minutes × average view % / 60.
At 30 min and 20%: 100 views → 10 h; 1,000 views → 100 h. Reaching 4,000 h by day 30 needs about 133 h/day, i.e.
~1,330 such views per day across the catalogue. Subscribers: 737 missing → ~53/day for day 14, ~25/day for day 30;
at the market median of 8.8 per 1,000 long views that is ~6,000 or ~2,800 long views/day. Costs: zero money (free tiers). Monetization conditions: 1,000 subscribers + 4,000 public
long-form hours (365 d) or 10 M Shorts views (90 d), plus policy review (no reused content, no misleading metadata).
The first measurable signal is 48 h after pilot-002/003 open; no horizon or range is claimed before that.

## 6b. First real runs (2026-10-18, after the reinforcement)

- **Indicators, corrected run (goal report 08:00 UTC):** public long-form watch hours 365 d = **3.3** (the old
  report showed 76.9 = all content incl. Shorts and hidden/removed videos); public Shorts views 90 d = **40** (old:
  2,645 lifetime). Subscribers 263 (official). The real starting point for YPP is close to zero watch hours.
- **Gate on pilot-003 (render `91e24033…`, QA PASS):** run 1 → **UNKNOWN** (watched review ERROR, Gemini quota),
  nothing approved; run 2 → **FAIL**: watched review pacing 6.5 < 7 ("figure completely static, zero pose variation
  or subtle animation", backgrounds cycling, reference lingering over "amen"); scorecard words/min 113.9 and
  coverage 0.69 came from the miner — our ASR on the same file measured 132.7 words/min (WER 3.8% vs script), so
  those rows measured the miner's error (now reported until the miner passes its holdout; the same limits stay
  blocking through frozen QA). Scan PASS, preflight PASS, binding PASS.
- **QA on pilot-004 (render `ecab8da5…`):** FAIL on three frozen rows, each traced to a cause and fixed with a
  regression test: repeated background (split-hold bug in `still_render.holds`), true peak −0.2 dBTP (one plosive at
  1087 s passed the sample limiter; 4× oversampled limiter → −2.8 dBTP on the same audio), speech presence 0.835
  (night pauses 201 s; shortened to 117 s, estimated 0.873; pilot-006 pre-emptively 210 → 106 s, est. 0.868).
- **Shorts:** pilot-003's three Shorts all failed the watched review (scores 5–7.9; overlap of hook and reference
  at 0–2 s fixed); pilot-002 short-02 scheduled (`_sUdOLxWy5c`). Shorts are now cut only from a QA-PASS render.
- **Operations defects found by the runs:** a mining run exhausted the shared free Gemini day (mining now yields to
  pending approvals/Shorts); Shorts that failed on quota had no retry (reconcile now re-dispatches); the runner's
  scheduled trigger has not fired once since it was added (renders dispatched manually meanwhile); GitHub delayed
  every morning cron by > 40 min (Shorts publication dispatched manually, idempotent ledger).
- **Re-render once** of pilot-003 and pilot-004 with the fixes (figure breathing, reference timing, QA fixes);
  one review each. If the gate still fails, the pilot is not published and the result is reported — no further
  tuning to force approval.

## 7. Proof and what remains unproven

Delivered with tests: mining validator (11), comparator (5), gate (5, good/bad/missing incl. timeout and quota),
Shorts publication (4, incl. no duplicate uploads), render queue (UNKNOWN retried), signal scan (4), indicators (2).

**Not proven yet:**
1. Mining accuracy on the holdout (UNKNOWN until re-mined windows are acquired and compared).
2. Watched-review calibration results (run pending on the pilot-003 render).
3. Frozen-picture threshold (informative until calibrated on known-good renders).
4. ~~Real end-to-end run of the new gate~~ — done on pilot-003 (UNKNOWN on quota, then FAIL with reasons); a PASS path on a real render is still unproven.
5. Transcript-derived spec numbers (to be recomputed from valid windows).
6. Any per-video performance forecast; channel forecast score arrives 2026-10-24.
7. Whether our Analytics estimate of public long-form hours matches YouTube Studio's YPP counter.
