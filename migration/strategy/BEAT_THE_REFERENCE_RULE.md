# Rule: the modelled video must beat the mined reference (owner directive, 2026-10-17)

Owner, in Portuguese, paraphrased: "Mining must be perfect. If the mined video is cinematic, model it cinematic and better still. Modelling must always be better than the mined video: structure, script, execution. Everything must be perfect."

## 1. Mining covers the whole work
For every format, mine **winner vs median vs weak** uploads of the same channel, at the same age band, with the qualified instruments (av-event-meter, av-semantic, av-profile, transcripts and contact sheets):
- **Structure:**
  - opening windows 0–1, 1–3, 3–8 and 8–30 s;
  - hook type;
  - promise;
  - body beats;
  - reveals or turns;
  - payoff;
  - CTA placement.
- **Script:**
  - transcript and words per minute;
  - open questions;
  - second-person address;
  - scripture or fact density;
  - where the reveals sit.
- **Execution:**
  - shot and scene cadence;
  - camera motion vs static;
  - image vs video;
  - caption style;
  - voice;
  - music share;
  - loudness;
  - colour and brightness.
- **Packaging:** title pattern, thumbnail text and composition, duration.

Every claim is linked to the file and time window it comes from. A gap stays UNKNOWN.

## 2. Beat-the-reference scorecard (pre-publication gate)
Each new video is measured side by side with the winner of its format. **Publication is blocked if any item is worse than the winner:**

| Item | Pass condition |
|---|---|
| First spoken word | ≤ winner's, and ≤ 1.5 s |
| Hook promise | stated within the winner's hook window |
| Scene/visual change cadence | inside the winner's band, or closer to the top-quartile band of the daily intelligence |
| Speech | intelligibility WER ≤ 0.10; words/min inside the winner cohort's range |
| Loudness | integrated within −16 to −14 LUFS; voice-forward music share ≤ winner's |
| Captions | legible at mobile size (cap height ≥ 3% of frame height); never overlapping the figure's face |
| Image quality | sharpness ≥ the winner's sampled frames (Laplacian variance on the same proxy) |
| Policy | originality, rights and the advertiser-friendly checklist pass |

After the automatic scorecard comes a frame-by-frame perceptual review (contact sheet). A pass on numbers alone never publishes a video that looks or sounds worse.

## 3. Cinematic when the reference is cinematic, and better
All routes are free and run on the Kaggle GPU:
1. **2.5D parallax (default for every still):** depth-estimated layers move with a virtual camera.
2. **Generated motion shots** with open-weight Wan 2.1 (Apache-2.0) for the highest-impact moments.
3. **Commercially licensed footage**, only with a documented licence and never as reused-content compilations.

Choosing a technique always respects the monetization policy: original value, no reused-content compilations, honest packaging, and AI disclosure where the content is realistic.
