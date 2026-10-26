# Format study: cinematic AI scenes and an on-screen narrator (2026-10-26)

Question (owner, 2026-10-26): replace landscape-plus-narration with (a) cinematic AI scenes that show the story and
(b) an original on-screen narrator who appears in every Short and long, made with Agnes Video Flash via Pavo
(720p, 4-12 s clips, text / first-frame / reference-image modes, up to 12 s input audio). Goal: YPP fast without an
"inauthentic content" finding.

**Method and limits.** Web search only. WebFetch and curl could not reach the pages (DNS failure, then a 403 from the
session proxy for support.google.com, npr.org and 404media.co), so every quote below comes from search-engine
excerpts of the cited page and has not been checked against the full live page. Channel numbers are third-party
snapshots (Social Blade, CreatorDB, vidIQ, press) from the dates given. They are **estimates**, not Studio data.
There is no controlled public study of "AI host vs no host" on YouTube. Where this report recommends something
the evidence does not settle, it says so, and section 6 turns that into a test. In-repo evidence is cited by path.

---

## 1. What the growing Bible/Christian story channels look like (2025-2026)

| Archetype | Example (figure, date, source) | Format | Recurring host? |
|---|---|---|---|
| Cinematic photoreal AI (Veo/Kling style) | **The AI Bible** (Pray.com): >270K subs and top video 1.7M views (404 Media, Jul 2025); ~408K subs, 669 videos, 68.9M views (Socialcounts, 21 Jul 2026); 413K subs, **+4K in 30 days**, 2.6M across platforms (CreatorDB, 30 Sep 2026). One 8-min Revelation video got 750K views in 2 months (NPR, 7 Sep 2025). Top video: "What if The Bible had a movie trailer...?", about 2 min. | Trailers, 8-10 min narrated episodes, Shorts | No host; the company says it uses staff scriptwriters, one of them a pastor (Christian Post via search) |
| Cinematic AI long, one story per video | In-repo winners (`evidence/vidiq/20261025/bible_story_long.json`, vidIQ outliers, 25 Oct 2026): Echoes of Faith "Shadrach, Meshach and Abednego" 782K views, 46.6 min, outlier 576x; Bible Stories "Adam and Eve" 85.7K, 14.3 min, 589x; Bible Stories TV 247 "Noah" 274K, 27.9 min, 212x; Bible Wonders "Cain and Abel" 89.7K, 14.8 min. **5 of 7 carry YouTube's AI label.** | 11-47 min, one story per video, title "<Story>: <human angle> \| Genesis N Bible Story" | None. Bible Wonders uses AI-voiced characters in dramatized dialogue, with no narrator. |
| AI "Bible influencer" POV vlogs (TikTok first) | @holyvlogsz ~450K followers (AAR paper via search, 2025-26); an AI Moses Exodus vlog with >30M views on TikTok (same source); PJ Accetturo's Veo 3 vlogs got "millions" of views, some clips >1M a day (PetaPixel, 3 Jun 2025; ChurchLeaders 2025) | 8-60 s selfie-style clips: a biblical figure talks to camera | The biblical character is the "host" |
| Stylized 3D / animated AI | Bible Movies: 129K subs but only 819.8K total views, 65 videos, 16-min average length (vidIQ page, May 2025). Bible Stories - Movies: ~513K subs, flat in Jul 2026 (Social Blade). | 10-20 min AI-animated stories | No |
| Classic, studio animation with recurring characters | **Superbook** (CBN): ~12M subs, ~3.5B views (CBN pages, 2025-26); BibleProject: >1.2M subs, explainer animation (Crosswalk / CT) | Kids 6-12 (Superbook); adult explainer (BibleProject) | Superbook: yes, Chris, Joy and the robot Gizmo. BibleProject: two hosts' voices. |

**What the evidence says.**
- **Views.** One complete story per long, told cinematically, is what breaks out now (in-repo outliers, 8x-589x their
  channels). In short form, a character talking to camera (POV vlog) gets the largest single-video reach (30M+).
  It is also the format that draws the "blasphemous" backlash (ChurchLeaders; Crosswalk).
- **Saturation.** The pioneer is slowing: The AI Bible added only about 4K subscribers in 30 days at 413K (estimate,
  CreatorDB, Sep 2026). Several channels with 100K-500K subscribers were flat in mid-2026 (Social Blade). Generic
  cinematic AI alone no longer stands out.
- **Retention and subscriber conversion.** No public data separates these by archetype.
- **Enforcement.** Religious AI channels are among those removed. Kapwing's Nov 2025 report, cited by Tubefilter
  (29 Jan 2026), named "Imperio de Jesus" (~5.8M subs) as removed in the January 2026 slop crackdown. A Bible story
  channel with ~588K subscribers and ~$30K a month in revenue was reportedly fully demonetized for "inauthentic and
  mass-produced content." This comes second-hand (Sean Cannell, Think Media podcast #487; Fliki blog) and is
  **unverified**.

## 2. A recurring narrator/host in faceless channels

**Evidence that a host helps.** It is indirect but consistent.
- Marketing research on spokes-characters: "spokes-character trust is an important mediator of the effects of
  spokes-character features on brand attitude", and the effect is stronger when viewers know the brand less
  (Garretson & Niedrich 2004, *J. of Advertising*, via LSU repository). A new channel is exactly that case.
  Nostalgic-design characters raised brand attitude for unfamiliar characters (APJML 2024).
- On YouTube, the largest Bible channel is character-led: Superbook, with Gizmo, Chris and Joy (~12M subs).
- Vendor claims either way (AI hosts "+25 % RPM" or "-10-20 % watch time"; lensgo.ai, avatarfactory.io, 2026) have
  no named data: **noise**.
- Policy angle (section 3): a recurring presenter who comments is the most visible sign of "original commentary"
  and "not a template". That matters more for eligibility than for views.

**Evidence of risk.** Low-quality AI faces cut trust. One vendor reports "uncanny valley" ads got 2.7x more comments
but 89 % of them negative (oakgen.ai, **unverified**). A guide cites a study where an "AI-generated" label lowered
selection by 23 % (gofaceless.ai, **unverified**). The host must therefore look good at 720p, or appear less often.

**Archetypes for an older US KJV audience plus TikTok.**
| Archetype | Fit | Main risk |
|---|---|---|
| **Elderly scribe / storyteller** (lamp, scrolls, a worn KJV) | Matches KJV gravitas and "grandfather telling the story", and reads as an older-audience brand. A desk and a lamp make a fixed set, which gives consistent reference shots. | Can be read as Moses or Abraham; uncanny lip-sync in close-ups |
| Shepherd by a fire | Warm, biblical imagery, night setting | Biblical-person confusion (David, the shepherds of Luke 2); fire looks the same every episode |
| Child explorer | TikTok-friendly | Pulls the channel toward "made for kids" (no comments, lower ads), off-audience |
| Angelic figure | Strong visuals | Theology: angels are story characters, and an angel "teaching" invites Col 2:18 objections and confusion with the text |
| Cartoon animal | Brandable | Reads as kids' content; clashes with KJV tone and with the photoreal scenes |

## 3. YouTube monetization policy for AI content (2025-2026)

- **Inauthentic content (15 Jul 2025).** The YPP policy page says the former "repetitious content" policy was renamed
  "inauthentic content" and clarified to cover content "that is repetitive or mass-produced". Examples that do not
  qualify include "image slideshows, templated storylines or scrolling text with minimal or no narrative,
  commentary or educational value" and "similar or repetitive content with low educational value, commentary,
  narratives or minimal variation across videos". Under reused content: "content that exclusively features
  readings of other materials you did not originally create". A related help passage: a channel "is still subject to
  potential rejection/suspension from YPP if the content is not clearly original or if we cannot tell that you made
  the content". (support.google.com/youtube/answer/1311392, excerpts via search, accessed 26 Oct 2026.) The policy
  applies at **channel level**.
- **YouTube's clarification (Rene Ritchie, Jul 2025).** "A minor update"; this content "has already been ineligible
  for monetization for years". The named targets are "channels that post nearly identical narrated slideshows or
  minimally altered story variations". Channels that use AI "remain eligible ... provided the content offers
  significant original commentary, modifications, or educational or entertainment value" (eWeek; Social Samosa;
  Search Engine Journal, Jul 2025). **A KJV reading over generic visuals, repeated in every video, is the named risk
  pattern.**
- **AI slop priority (Neal Mohan, Jan 2026 letter).** "AI will remain a tool for expression, not a replacement"
  (Variety AU, Jan 2026; Tubefilter, 29 Jan 2026).
- **Disclosure.** Creators must disclose content that is realistic or meaningful, with examples including "cloned
  voices" and realistic simulated events (support.google.com/youtube/answer/14328491). The launch post exempts
  "clearly unrealistic content, such as animation or someone riding a unicorn through a fantastical world", along
  with production assistance and inconsequential edits (blog.youtube "disclosing-ai-generated-content", Mar 2024).
  A photoreal host and photoreal biblical scenes count as realistic, so keep the "altered or synthetic" toggle **on**,
  as the repo already does.
- **Voices and avatars.** Synthetic narration is not itself grounds for refusal. The impersonation policy forbids
  "using AI to copy the voice or likeness of an individual" to make it seem owned or authorized by them
  (support.google.com/youtube/answer/2801947). Likeness detection currently matches faces, with audio planned
  (support.google.com/youtube/answer/16440338). An **original** host, not modelled on any real person, avoids
  both.
- **The deadline that matters.** From **1 Feb 2027**, new YPP applicants need 1,000 subscribers plus **8,000** public
  watch hours over 365 days, or **20M** Shorts views over 90 days. Channels already in YPP are not affected
  (YouTube announcement of 10 Aug 2026, via RouteNote, vidIQ blog, SEJ; already tracked in
  `strategy/MARKET_FORECAST_TIME_TO_YPP_20261017.md`). Judge every format change by long-form watch hours before that date.

**What keeps an AI channel eligible, in YouTube's own terms:** original narrative and commentary (our insight
lines, the host's framing), real variation between videos (a different story, shot list and angle each time; not one
template with the names swapped), and visible human authorship (a recurring creative identity, a consistent
voice). A host helps on all three only if what he says changes each episode. A fixed intro and outro is fine, as
DECISIONS.md already notes.

## 4. Visual style for "gourmet" scenes that Agnes/Pavo can deliver

**Style.** Use **painterly-cinematic realism**: photoreal subjects with a fixed grade of warm chiaroscuro, oil-lamp
and dusk light, film grain, and the composition of Old Master paintings (Rembrandt / Caravaggio light).
- This is not pure photoreal epic. Photoreal faces in close-up are where 720p AI fails first, and the field is
  saturated with that look (section 1).
- It is not Pixar 3D. That reads as children's content for an older KJV audience, and the claims that it "boosts
  engagement" are freelancer marketing (Fiverr / alici.ai, 2025-26, unverified).
- A painterly grade hides 720p softness, and Real-ESRGAN already lifts clips to 1440p. It also sets the look apart
  from the Veo-style crowd, and it is a style a consistent reference image can hold. Kurzgesagt is the usual example
  that a **fixed** visual language does the job a face does (gofaceless.ai; easyviral.ai, 2026). Consistency matters
  more than which style is chosen.

**Consistency workflow (vendor guides, 2026: magichour.ai, morphic.com, kittl.com).**
- Build one character sheet per recurring figure (front, three-quarter, profile) and attach it to every shot. Do not
  re-describe the character in each prompt.
- Keep the prompt template fixed and change only action and setting.
- Prefer short, cuttable shots; drift grows with clip length, and "no model in mid-2026 achieves perfect
  consistency". For Agnes, that means 4-6 s shots in reference-image or first-frame mode, with the first frame being a
  FLUX still made from the sheet. Use 12 s clips only for the host's talking lines.

**Shot grammar for a Short.**
- 0-1.5 s: the peak image in motion, a VFX moment (fire from heaven, the deep parting, the flood rising), plus the
  spoken hook.
- Then cut every 2-4 s, alternating wide (scale), medium (action) and an insert (hands, an object, an eye).
- Every shot moves: a slow push-in, an orbit, a crane or a tracking shot. Nothing static.
- One VFX beat per 15-20 s.
- The host is on screen at most about 25 % of the time, in 3-8 s cut-ins at the hook handoff, the insight and the
  close.
- Only `cut` between scenes (owner's rule).

**What to avoid.**
- Never depict God the Father as a person. Show him as light, wind, fire or voice, with the KJV words on screen.
- Jesus is not needed in Genesis arcs. Decide on reverent, distant, non-speaking depiction before the Gospels.
- No irreverent "influencer" treatment of biblical figures. Accetturo himself said some evangelicals are "QUITE
  SENSITIVE" (ChurchLeaders, 2025).
- No close-up lip-sync on biblical characters (uncanny risk).
- Cherubim and angels in light or silhouette.
- No text baked into AI frames.
- Nudity in Eden (Gen 2:25) only by framing: foliage, backs, wide shots.

## 5. Script structure for Shorts and longs

Grounded in the in-repo winners (titles and structure in `bible_story_long.json`; Bible Wonders speaks at 2 s and
closes on a moral), The AI Bible's top "movie trailer" video (a trailer framing as the hook), the POV vlogs' direct
address (the reach driver on TikTok), and YouTube's Shorts signal of viewers choosing to watch rather than swipe
(the "viewed vs swiped away" metric, vidIQ blog 2026; subscribr.ai).

**Short (62-90 s, part N of 4).**
1. **0-2 s, hook.** The peak in motion plus one line in one of four forms: *consequence-first* ("He killed his
   brother, and God asked him one question."), *contradiction* ("The first lie in the Bible was only four words
   long."), *you-address* ("You've heard this story wrong."), or *stakes* ("One man. One boat. Every living thing.").
2. **2-6 s, host handoff.** The host to camera: "I'm [name]. Part 2 of Cain and Abel." This gives series continuity
   and a recognizable face.
3. **6-50 s, the moment.** The KJV lines with our retelling around them (40 % or more of the words ours). A pattern
   interrupt every 8-12 s: the host cuts in, a KJV line card, a VFX beat, or a sudden quiet.
4. **50-70 s, insight.** The host gives one thing most readers miss: a tension in the text, or a word in the KJV that
   means more than it seems. This is the "original commentary" anchor.
5. **Close, open loop plus CTA.** "But that's not the strangest part: tomorrow, part 3." Once the long exists: "The
   whole story is on the channel." The related video is set to the long.

**Long (14-18 min).**
- **0:00-0:30:** cold open on the arc's peak, using the Short's hook shot.
- **0:30-1:00:** the host greets, gives a roadmap ("four moments, and the one detail that changes how you read
  it").
- **Chapters:** one per Short, with chapter titles equal to the Short titles. Each chapter starts with a host re-hook
  on camera (8-12 s) and ends on an open loop. A re-hook at least every 3.5 min (R13).
- **Close:** the host's reflection, the prayer, then "next story" (the next arc's first Short).

---

## 6. Recommendation

1. **Format.** Keep the arc funnel (4 Shorts lead to 1 long) and change the picture. Shorts become AI scenes that show
   the action, cut every 2-4 s, with an original host in 2-4 cut-ins. Longs get the host as presenter, opening the
   video and every chapter. The licensed-footage share stays as the frozen story QA requires; the host and AI scenes
   replace the landscapes, not the gates.
2. **Host: "the Keeper", an elderly scribe-storyteller.** He is invented, not a biblical or real person, and never
   called a prophet, priest, rabbi or angel. Plain ancient robe in one signature color, a leather satchel, a
   lamp-lit stone room, a worn KJV on the desk. Distinct from Moses: no staff, a short beard, his own props. He
   never speaks as God and never claims revelation; he says "the Scripture says".
   - Why: it fits the older KJV audience, the set is consistent enough for reference images, it is a direct-address
     format like the POV vlogs that drive TikTok reach but without impersonating Scripture figures, and it is the
     clearest "original commentary / creative identity" signal under the July 2025 policy.
   - Risks: 720p lip-sync looking uncanny (keep him in medium shot, 3-8 s, voice from the same George / am_michael
     line), and drift (one sheet, fixed template).
   - Agnes lip-sync from input audio is **presumed, not yet verified**: test it before committing.
3. **Style.** Painterly-cinematic realism with one fixed grade and Old-Master light. Faces mostly medium or wide.
   God as light and voice. A VFX beat every 15-20 s. Disclosure toggle on.
4. **Script.** The 0-2 s peak hook (four forms), host handoff, the moment, the insight, then open loop and CTA to the
   long. In the long: cold open, roadmap, a host re-hook per chapter, reflection, prayer, next story. Different words
   each time: no template lines beyond the greeting.
5. **First week: what to measure.** A test, not a rollout.
   - 4 arc Shorts with the host vs the last 4 without, matched on slot.
   - Short metrics: viewed-vs-swiped (vs our own baseline; the 75-80 % benchmark is third-party), average % viewed
     and the 3 s drop, subscribers per 1,000 views, and clicks from Short to long (related video, first comment).
   - Long metrics: retention at 0:30 and at the first host chapter re-hook, average view duration, watch hours per
     day (the binding constraint before 1 Feb 2027).
   - Comments that mention the host (sentiment), clips rejected for drift or uncanny faces, and Pavo credits and
     time per Short.
   - Keep the host if subscribers per 1,000 views and Short-to-long clicks are not worse and the comments are not
     negative. Otherwise move him to the longs only.

## Sources (accessed 2026-10-26 via web search; publication date in brackets)
- YouTube channel monetization policies: https://support.google.com/youtube/answer/1311392 [live page; inauthentic-content update 15 Jul 2025]
- YouTube Shorts monetization policies: https://support.google.com/youtube/answer/12504220 [live page]
- Disclosing altered or synthetic content: https://support.google.com/youtube/answer/14328491 [live page]
- YouTube blog, disclosure launch: https://blog.youtube/news-and-events/disclosing-ai-generated-content [Mar 2024]
- Impersonation policy: https://support.google.com/youtube/answer/2801947 [live page]
- Likeness detection: https://support.google.com/youtube/answer/16440338 [live page]
- YPP 2027 changes, YouTube blog: https://blog.youtube/news-and-events/youtube-partner-program-updates-2027-new-opportunities-earn/ [Aug 2026]; RouteNote: https://routenote.com/radar/youtube-monetization-requirements-2027-new-ypp-rules-double-watch-hours-and-shorts-views/ [2026]; vidIQ: https://vidiq.com/blog/post/youtube-partner-program-changes-2027/ [2026]
- eWeek, "AI is fine as long as it's authentic": https://www.eweek.com/news/youtube-responds-to-ai-concerns/ [Jul 2025]
- Social Samosa, YouTube clarifies: https://www.socialsamosa.com/news-2/youtube-clarifies-monetisation-policy-targeting-inauthentic-content-9493155 [Jul 2025]
- Search Engine Journal: https://www.searchenginejournal.com/youtube-clarifies-monetization-update-targeting-spam-not-reaction-channels/550123/ [Jul 2025]
- Plagiarism Today: https://www.plagiarismtoday.com/2025/07/08/youtube-targets-inauthentic-content/ [8 Jul 2025]
- Tubefilter, slop channel bans: https://tubefilter.com/2026/01/29/youtube-ai-slop-channel-crackdown-bans/ [29 Jan 2026]
- Variety AU, Mohan letter: https://au.variety.com/2026/digital/news/youtube-channels-using-ai-tools-reduce-slop-neal-mohan-letter-32190/ [Jan 2026]
- NPR, "Fantasy or faith?": https://npr.org/2025/09/07/nx-s1-5518263/ai-bible-christianity-content [7 Sep 2025]
- 404 Media, "Why do Christians love AI slop": https://www.404media.co/why-do-christians-love-ai-slop/ [Jul 2025]
- CreatorDB, The AI Bible: https://creatordb.app/creatorstats/theaibibleofficial/ [data 30 Sep 2026]
- Socialcounts, The AI Bible: https://socialcounts.org/youtube-live-subscriber-count/UCvlfCpmecGhPDDLPj3ktDUA [snapshot 21 Jul 2026]
- Social Blade, Bible Stories - Movies: https://socialblade.com/youtube/handle/biblestories.official [Jul 2026]
- vidIQ stats, Bible Movies: https://vidiq.com/youtube-stats/channel/UCL4aytJXRQCAXyLZrs9k7rg [May 2025]
- PetaPixel, Bible influencer videos: https://petapixel.com/2025/06/03/viral-ai-videos-bring-bible-figures-to-life-as-influencers [3 Jun 2025]
- ChurchLeaders, AI Bible influencers: https://churchleaders.com/news/512480-ai-bible-characters-stories-vlogs-viral.html [2025]
- Crosswalk, Christians split: https://www.crosswalk.com/headlines/contributors/michael-foust/christians-split-over-viral-ai-videos-that-put-bible-characters-on-tiktok.html [2025]
- Know Your Meme, AI Bible influencer videos: https://knowyourmeme.com/memes/ai-bible-influencer-videos-ai-bible-stories [2025]
- AAR paper on @holyvlogsz: https://papers.aarweb.org/node/113407 [2025-26]
- Chrostowski, J. of Religious Education: https://edoc.ku.de/id/eprint/36817/1/Chrostowski-2026-Journal_of_Religious_Education.pdf [2026]
- CBN Superbook: https://www.cbn.com/Superbook [live page]
- Garretson & Niedrich, spokes-characters: https://repository.lsu.edu/marketing_pubs/39 [2004]
- Think Media podcast #487 (demonetized Bible channel): https://pod.wave.co/podcast/the-think-media-podcast/487-youtube-is-demonetizing-channels-what-you-need-to-know [2025-26]; Fliki: https://fliki.ai/blog/youtube-ai-demonetization [2026]
- Character consistency guides: https://magichour.ai/blog/how-to-keep-characters-consistent-in-ai-video ; https://morphic.com/resources/how-to/character-consistency-in-ai-video [2026]
- Stock vs AI visuals (disclosure-label study cited): https://www.gofaceless.ai/blog/stock-footage-vs-ai-visuals-faceless-videos [2026]
- Uncanny valley claim: https://oakgen.ai/blog/uncanny-valley-ai-marketing [2026, unverified]
- Shorts algorithm and viewed-vs-swiped: https://vidiq.com/blog/post/youtube-shorts-algorithm/ ; https://subscribr.ai/youtube-strategy/youtube-shorts-analytics-metrics-viral [2025-26]
- In-repo: `migration/evidence/vidiq/20261025/bible_story_long.json`, `migration/strategy/DECISIONS.md`, `migration/production/bible/SERIES.md`
