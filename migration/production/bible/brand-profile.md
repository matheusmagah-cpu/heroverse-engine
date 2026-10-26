# Brand Profile — HeroVerse (@heroverse74)
<!-- version: 1.0 · last updated: 2026-10-24 · type: personal (faith creator channel)
     Read by the social-media-skills plugin. It points to the directing documents instead of copying them:
     when this file and SERIES.md, PROMPT_GUIDE.md or STANDARD.md disagree, those documents win. -->

## Identity
- **What it is:** a YouTube channel that tells the Bible story by story from the KJV, with Shorts and long videos.
- **Category:** Christian scripture storytelling (English).
- **Channel:** `@heroverse74` (`UCuMF6pJQkyMzaVoAxFL86yA`).

## Positioning
- **What's different:** one micro-story at a time in canonical order from Genesis, exact KJV narration, cinematic
  real-world footage that never sits still, a short original reflection and a one-line prayer.
- **Point of view:** scripture read as written; the story carries the episode.
- **Won't say:** fear-bait, prophecy or end-times claims, health or wealth promises, denominational attacks.

## Audience
- **Who:** English-speaking Christians who want a short daily Bible story they can watch and share.
- **Where:** YouTube Shorts feed (discovery) → long videos (watch hours).
- **Transformation:** an unknown story → the passage known in its KJV words, with a moment of prayer.

## Voice
- **We sound reverent, never preachy; cinematic, never cheap CGI; exact, never paraphrased.**
- **Words we use:** the KJV text itself; "Part N+1 tomorrow: <next story>" at the end of each Short.
- **Words we ban:** invented quotes attributed to scripture, "shocking", "they don't want you to know".
- **Pronunciation guide:** biblical names as in standard English KJV readings.

## Proof
- Numbers come only from `migration/evidence/daily-report/latest.md` (YPP goal: subscribers and public watch hours).
  Never invent a metric.

## Offers & CTAs
- **Primary CTA:** follow the series ("Part N+1 tomorrow").
- **Secondary:** watch the long episode that composes the last 6 Shorts.
- Ads stage and digital product are on hold: no selling.

## Channels
- **Active platform:** YouTube only (Shorts 13:30 and 23:30 UTC; a 14-18 min Bible-story long every 2 days at 10:00 UTC, per `SERIES.md`).
- **Language:** English content; the owner is addressed in Portuguese.

## Operational defaults (tool skills read these)
- **Production rules:** `STANDARD.md` R1-R14, `PROMPT_GUIDE.md` (five-part AI prompt, "Built for 9.5"), frozen QA.
- **AI & synthetic media policy:** AI video only at the hook and the story's peak; no face of God; biblical people
  only from a fixed character sheet; every upload is marked `containsSyntheticMedia: true` (`publish_video.py`).
  No AI avatars, no voice clones, no AI music from paid tools.
- **Tools allowed (zero additional cost):** vidIQ within the daily credit ceiling (ledger
  `migration/evidence/vidiq/ledger.json`), free Cloudflare FLUX and Runway free image credits for stills, Pexels and
  Pixabay stock. Any skill that recommends HeyGen, Synthesia, Suno, Kling, Luma, Opus Clip, Descript, CapCut Pro,
  Canva Pro, ElevenLabs paid tiers or WoopSocial is advice only: do not sign up, buy or connect.
- **Publishing:** only through `approve.yml` → `prepublish_gate.py` → the publish workflows. Never schedule or post
  through WoopSocial or any other scheduler.
- **Accessibility:** captions always on (large for Shorts, about 7 % of frame height); loudness about -14 LUFS.

## Guardrails
- **Compliance:** KJV is public domain; stock clips keep their credits in the description (`package_pilot.py`).
- **Sensitivity:** no modern objects or people in biblical scenes; no images of God.

## Notes
- Current arc: Genesis, episodes 1-18 listed in `SERIES.md`, then on through Genesis 50 and Exodus.
