# HeroVerse System v2: one loop, six stages, few tools (owner, 2026-10-19)

The channel is a robot that keeps finding the **structures that win right now** and executes them
perfectly. The unit of mining is the **structure**, never a channel. A structure is the complete,
repeatable shape of a video:
- format and length;
- the sequence of beats and their timing;
- the opening;
- the voice;
- the visual and cinematic grammar;
- on-screen text;
- calls to action;
- title and thumbnail.

The format may change whenever mining proves a better structure **in the same line** (English
Christian prayer and devotion) that does not conflict with the channel. No format is frozen.

Every stage, **from the channel configuration to the pinned comment**, is held to the same bar:
- **ultra-professional and measured;**
- **better than the market's current best.** For every measurable attribute, our target is the **best** value among the validated winners, never their median (`strategy/BEAT_THE_REFERENCE_RULE.md`). Where we can measure quality ourselves (sync, loudness, sharpness, caption accuracy, policy), our bar is stricter than any winner shows.

```
 0 CHANNEL CONFIGURATION (once, then kept true by stage 6)
 1 MINE structures ─► 2 MODEL ─► 3 AUTHENTICITY + CRITIQUE ─► 4 SHORTS from the long ─► 5 PUBLISH
        ▲                                                                                      │
        └────────────────────────── 6 LIVE INTELLIGENCE (measure, catalogue, decide) ◄─────────┘
```

## Tools (only these)

| Tool | Used for | Limits |
|---|---|---|
| vidIQ (MCP, read-only, via Claude) | Stages 1 and 6: outliers, watched audits, transcripts, stats, our public videos and analytics | ≤10 calls/day, ≤2,000 credits/cycle (`evidence/vidiq/ledger.json`) |
| Gemini, free tier | Stages 3 and 5: watched review (designated `gemini-3.8-flash` only), audit and critique (support models) | Free daily quota (E26/E29) |
| Kokoro voice, FLUX images (Cloudflare), ffmpeg | Stage 2 execution | Free, hash-pinned |
| YouTube Data API | Stage 5 | Our OAuth |
| GitHub Actions + Dot | Running and building everything | Public repo; Dot works only through cards |

Nothing else is added unless a stage cannot meet its bar without it, and that is proven first.

## 0. Channel configuration (once, then audited by stage 6)

The channel is configured as a top Christian prayer channel, and **every setting that can influence reach or trust is decided from evidence**, never left at its default. Evidence comes from two sources:
- **the official YouTube Help pages**, quoted verbatim (Dot reads them; this environment cannot reach support.google.com);
- **what the validated winners' channels do**, measured with vidIQ.

| Setting | Set by | Rule |
|---|---|---|
| Name, handle, profile picture, banner (sizes per Help) | owner in Studio (the handle cannot be set by the API) | Evidence-based spec in `structures/channel.json` |
| Channel description and keywords; country, default language; trailer for non-subscribers | API (`channels.update` brandingSettings) | From the winners' channels and Help, with no keyword stuffing |
| Home sections and playlists, one per active structure | API (`channelSections`, `playlists`) | Every video goes into its structure's playlist |
| Upload defaults: category, language, licence, comments, description template | Studio, plus the per-video API fields | Category = the most frequent among the validated winners (measured, not assumed) |
| Altered/synthetic disclosure | per video (`containsSyntheticMedia`, already on) | Help: realistic synthetic voice narration requires disclosure |

`structures/channel.json` records each setting's value, its source, and when it was last verified. Stage 6 re-verifies it weekly.

## 1. Mine winning structures (Claude + vidIQ)

1. **Find.** `vidiq_outliers` (long and short, last 3 months, minimum views) for every format in our line, plus
   `vidiq_youtube_search` and `vidiq_similar_videos` around each candidate.
   - **Winners:** breakout score ≥ 50.
   - **Weak contrasts:** videos of the same shape whose views are at or below their channel's norm.
2. **Group by structure.** Group by shape, not by channel: length band, beat sequence, visual grammar.
3. **Audit every video in the group** with the same prompt (`AUDIT_PROMPT`, in `production/long_review.py` after #178):
   - `vidiq_video_watch` for long videos, `vidiq_watch_shortform_content` for Shorts;
   - `vidiq_video_transcript` for exact pace, word counts and the beat text. Only the counts are stored, never third-party text.
4. **Measure every attribute** into the structure record (`structures/<id>.json`). Each attribute is labelled:
   - **driver**: in ≥ 70 % of winners and ≤ 30 % of weak contrasts;
   - **hygiene**: in ≥ 70 % of both;
   - **anti**: in ≥ 50 % of weak contrasts and ≤ 20 % of winners;
   - **free**: varies. Free attributes are where our videos vary, which the authenticity rules need.
5. **Validation (no channel lock).** A structure is `validated` only with:
   - ≥ 6 winners from ≥ 4 distinct channels;
   - no channel providing more than a third of the winners;
   - ≥ 3 weak contrasts;
   - every driver confirmed by a measured count (an estimate does not count; a model's estimate is refuted by a count, as with the 2026-10-19 pace).

   Until then it is a `candidate` and can only be piloted, never scaled.
6. **Conflict check** before a new structure enters production:
   - same language and faith line;
   - same audience (`vidiq_similar_channels` overlap);
   - no policy risk;
   - it does not make the channel incoherent.

## 2. Model (Dot builds, Claude reviews)

A validated structure becomes three things:
- **The script.** Every driver and hygiene beat, our own words, KJV Scripture only. `script_check.py` holds the structure's rules.
- **The execution spec.** Render parameters per structure: scene length, motion, caption style, cards, CTA timing, sound, Shorts windows.
- **The QA criteria for that structure version**, frozen before its first render. They are deterministic, every row blocks, and nothing is loosened after results.

Execution is judged on technical, professional, cinematographic and policy grounds:
1. the frozen QA;
2. the signal scan;
3. the designated watched review;
4. the audit against the winners' audits;
5. the owner for the first sample of every new structure.

## 3. Authenticity, originality and critique (YouTube monetization)

YouTube policy (Help Center, YPP monetization policies):
- **Inauthentic content** (renamed 2025-07-15) is mass-produced or repetitive content: made from a template with little to no variation across videos, or easily replicable at scale. It applies to the **whole channel**. "Image slideshows or scrolling text with little narrative or commentary value" is an official example.
- **Reused content** is other people's content without significant original commentary, modification, or educational or entertainment value.

Every video passes all of these, or it is not published:
- **Original text.** The script's 8-word shingles overlap < 5 % with every reference transcript mined. Only shingle hashes are stored, never the text.
- **No template.** Against our last 10 videos: a different opening line, a different Scripture set, a different image set, and a title that differs in more than its keywords. Script shingle overlap < 15 % with any of them. Free attributes vary.
- **Narrative value.** ≥ 35 % of the spoken words are original reflection or teaching, not Scripture quotation or set formulas. The structure gives it a story or a teaching arc, so it is never a slideshow with narration.
- **Critique.** A support-model pass reads the script and the audit against the two policies above and against our content rules:
  - no fear-bait;
  - no fabricated prophecy;
  - no health or wealth promise;
  - no borrowed identity.

  Any finding blocks until it is fixed.
- **Disclosure.** Realistic synthetic people or events are disclosed as altered or synthetic content; scenery-only videos say so in the record.

## 4. Shorts from the long video

The Short is cut from the long video's own narration and pictures. It starts and ends on full sentences, uses the long video's structure rules for Shorts (#173), and links back to the long video.

## 5. Publish: the complete package

The long video is published by `approve.yml` → `prepublish_gate.py` → `publish.yml`, and the Shorts by `publish-shorts.yml`. Every hard row blocks, and ERROR is retried, never passed.

**The publication package is part of the structure** and is mined like the video itself: the winners' titles, thumbnails, descriptions, hashtags, tags, chapters, first and pinned comments, end screens, publish hour and playlist use.

Each video ships the full package, and `preflight.py` checks every measurable item:
- **title**: the structure's measured pattern; ≤ 100 characters (Help); the promise matches the first 30 s;
- **thumbnail**: 1280×720, under the Help size limit; the structure's measured pattern (#173 item 5); a clear subject and readable text at small size;
- **description**:
  - the promise in its first lines;
  - **chapters** (Help rules: start at 0:00, at least 3, each ≥ 10 s);
  - the Scripture references;
  - one call to action;
  - **≤ 3 hashtags**, which show above the title;
  - ≤ 5,000 characters;
- **tags**: ≤ 500 characters, taken from vidIQ keyword research, never stuffed;
- **captions**: our exact narration SRT (already sent), never auto-captions;
- **first comment**: posted by the channel through the API (`commentThreads.insert`), with the structure's measured CTA. **Pinning it is manual**: the API cannot pin, so the owner pins it, or it is listed for the owner on publication day;
- **end screen and cards**: the API cannot set them. They come from the channel's default end-screen template, set once in Studio by the owner, pointing to the structure's playlist and to subscribe;
- **playlist**: the structure's playlist;
- **publish hour**: the structure's measured best window for the audience;
- **disclosure**: on.

Every item and its source are written into the package. An item without evidence is marked `UNMEASURED` and listed for stage 1. It is never guessed.

## 6. Live intelligence: back to stage 1 (Claude + vidIQ)

- **Our videos.** At 48 h and at 7 days after publication: `vidiq_video_watch` on our public video with `AUDIT_PROMPT`, plus real analytics (views, retention, CTR, subscribers). Each video is catalogued against its structure's expectation as **good**, **bad** or **neutral**, with the attribute that explains it. Every change cites a measured cause.
- **The market.** Every day, within the vidIQ limits: new outliers, then new or changed structures, then the catalogue (`structures/`). Structures move:
  - `candidate` → `validated` → `active`;
  - `active` → `retired` when our own results or the market turn against them.
- **Decisions** follow `strategy/DECISIONS.md` (90 % evidence for strategy). Defects and compliance are always fixed.

## Loop discipline

- Every stage writes its evidence to the repo. A stage that cannot meet its bar stops the loop **at that stage** and says why. Nothing is skipped and nothing is loosened.
- The loop never waits on one structure: while one is in production, the next ones are being mined.
