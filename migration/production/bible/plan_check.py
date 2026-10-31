#!/usr/bin/env python3
"""Check a Short's plan (`bible-plan-v2`) before anything is voiced or generated (owner, 2026-10-26, after the mining
of 26/10: open on the conflict spoken by a character, the characters speak their lines lip-synced, the Keeper only at
the close, 170-179 s, the lesson at most a quarter).

A plan is `migration/production/bible/plans/<episode-id>.json`:
  {"version": "bible-plan-v2", "episode": "genesis-07-short", "part": 7, "passage": "Genesis 6:5-13 (KJV, ...)",
   "aspect_ratio": "9:16",
   "narration": [{"kind": "story|scripture|insight|cta", "text": "...", "reference": "Genesis 6:5 (KJV)"?}, ...],
   "shots": [{"id": "s-voice", "kind": "scene", "speaker": "god", "line": "...", "reference": "Genesis 6:13 (KJV)",
              "seconds": 8, "characters": [], "prompt": "..."},
             {"id": "s-tents", "kind": "scene", "lines": [0], "seconds": 6, "prompt": "...",
              "characters": ["eve"] | [], "figures": "anonymous"?, "establishing": true?, "climax": true?},
             {"id": "s-eve", "kind": "scene", "speaker": "eve", "line": "...", "characters": ["eve"], "prompt": "..."},
             {"id": "k-close", "kind": "keeper", "lines": [9], "prompt": "..."}, ...]}

The voice track is the shots' words in order (`sequence`): the narration lines the shots carry (the Keeper's voice,
am_michael) and each speaking shot's own `line` (the speaker's own Kokoro voice, characters.voice) where that shot is.

Rules (DECISIONS.md 2026-10-26 "Shorts v2", PROMPT_GUIDE.md "Keeper + acted scenes"):
- the words: the records publish_episode.short_problems reads (from part 7: 170-179 s estimated, >= 40 % our words,
  one insight of >= 20 words, a close to the full story); every scripture line and every spoken line with a
  `reference` is the KJV word for word (kjv_check).
- the open: the first shot is a scene whose spoken line starts at 0 s: a character's challenge or plea, or God's
  voice. Never the Keeper, never narration first.
- spoken lines: a scene shot may carry `speaker` and `line` (and `reference` when the line is Scripture). A character
  speaker is APPROVED in characters.json, has a `voice`, is in the shot's `characters` (its look word for word), and
  the prompt says it speaks; its line (3.23-11.55 s, Pavo input audio) goes in with its references and lipsync_check judges
  the clip; the clip's length comes from the line (no `seconds`). `speaker: "god"`: Scripture only (a `reference`),
  the shot shows no person (no characters, no figures, no face: light, storm, wind or fire), its `seconds` are the
  Pavo clip's, and the line is mixed as a voice-over (deep voice, no lipsync check). The Keeper never speaks in a
  scene.
- narration shots in order, each carrying consecutive narration lines; every line is carried, in order; consecutive
  scene shots may share the same lines (the composer splits that time between them and cuts every 2-4 s).
- the climax: at least one acted scene is flagged `climax: true`: people on screen (approved characters or anonymous
  figures), never the Keeper, a landscape or God's voice-over sky (E92): the antagonist or spectacle moment is shown,
  never told.
- a line with no `reference` that still quotes the KJV (8 consecutive words) is refused (KJV_UNREFERENCED) and counts
  as Scripture, not our words; a `reference` that is not text is REFERENCE_NOT_TEXT.
- a talking line (the Keeper's, a character's) is 3.23-11.55 s (E95): Pavo keeps our audio only in a 4-12 s clip
  0.25-0.65 s longer than the speech, so episode_build retimes the line to N - 0.45 s (atempo on its words, at most
  +-10 %) and holds the clip's last frame for the gap or the tail. A shot of several lines needs its gaps (never
  stretched) + the shortest words a 4 s clip takes (talk_min). One that neither a 4 s nor a 5 s clip reaches within
  that (one line of ~3.94-4.14 s) at any pace from the normal to the slowest is TALK_LINE_UNREACHABLE (talk_retime,
  the rule the build retimes by): in practice a single talking line has at least 12 words.
- keeper: only after the last climax shot, for the insight and the close (lines of kind insight or cta); he closes
  (the last shot) and takes at most 25 % of the Short. He speaks the lines he carries (Pavo input audio + his
  speaking reference); each Keeper line is 3.23-11.55 s (estimated at the slowest measured Kokoro pace, measured and
  retimed again after the voice, E95), the closing one too (its tail is a held frame). His
  prompt carries his look and one wardrobe variant word for word and says he speaks.
- the lesson (insight + cta lines + every Keeper second) takes at most 25 % of the Short.
- scene: 4-12 s of Pavo video, a prompt in PROMPT_GUIDE's five-part form; each character APPROVED with its look word
  for word in the prompt (characters.py), at most 5 reference images in all. A scene with no character shows
  anonymous people seen only from behind / in silhouette (`figures: "anonymous"`, the prompt says so) or is an
  establishing shot (`establishing: true`), held at most 2 s on screen, all of them together at most 15 %.
- God the Father is never a visible figure: a prompt that names Him must show Him only as light, wind, fire or a
  voice, and never with a body, face, hands, robe or throne.
- the period (E108): every scene prompt states its story's period word for word, the setting and the exclusions
  (PERIOD_SETTING / PERIOD_EXCLUDE for Genesis before the flood), and names nothing the period excludes outside the
  setting and exclusion sentences (SCENE_PERIOD_CONFLICT: city, lane, room, street, tower, lantern...); the period
  is the plan's `period` (a malformed or unknown one is PERIOD_INVALID) or its passage's (a passage across the
  flood is PERIOD_AMBIGUOUS); none is SCENE_PERIOD_MISSING. episode_build.request refuses the same by period_refusal,
  long_plan_check by plan_period_problems.
- no writing (E110): a scene prompt asks for nothing written (scroll, ink, letters, inscription, writing, script,
  text, tablet, parchment, book, page, glyphs, runes, symbols...) outside a negation ("No text", "without
  letters"): SCENE_WRITING. The Keeper's own scroll is his look, not a scene. plan_check, long_plan_check
  (plan_writing_problems) and episode_build.request (writing_refusal) by the same function.
- the ark's look (E113): a scene prompt that names the ark (or a hull, keel, ship, boat, vessel) outside the period
  sentences carries ARK_LOOK and ARK_EXCLUDE word for word (PROPS; ARK_LOOK_NOT_CANONICAL) and, with them and the
  period sentences taken out, names no ship, boat, mast, sail, prow, funnel... (ARK_LOOK_CONFLICT). plan_check,
  long_plan_check (plan_prop_problems) and episode_build.request (prop_refusal) by the same function.
- E123, from part 9 in the ark's stories (ark_period: before-the-flood / the-flood, or Genesis 6-10; a long or a
  thumbnail by its period or passage): the ark is named only by ARK_PHRASE, word
  for word, in positive words; no scene, still or thumbnail prompt says ark, hull, keel, ship, boat, vessel, mast,
  sail, prow, figurehead, funnel, smokestack or "no smoke" (ARK_WORDS: ARK_LOOK_CONFLICT; the negated words of
  ARK_EXCLUDE primed the image model to draw them), and "crate" without the phrase is ARK_LOOK_NOT_CANONICAL. The
  flood's period sentence names no ark. A still shows the ark when its prompt holds the phrase (prop_references).
- image first (owner, 27/10): a scene shot may declare `first_frame` (and `last_frame`), the id of a scene still
  (bible/stills/<id>.json, scene_stills.py). Pavo then animates that still (frames_to_video) and the shot's prompt
  says the motion and camera. Frames go only on a scene with no characters and no input audio (Pavo: frames and
  references are exclusive, frames take no audio): FRAMES_WITH_REFERENCES / FRAMES_WITH_AUDIO / FRAMES_NOT_SCENE /
  FRAME_FIELD_INVALID / FRAME_LAST_WITHOUT_FIRST. The still exists (STILL_MISSING), is APPROVED by Claude's review
  (STILL_NOT_APPROVED), its image is the one approved (STILL_PATH_REFUSED, STILL_SHA256_MISMATCH,
  STILL_PROMPT_CHANGED) at the plan's aspect (STILL_ASPECT_MISMATCH), and its own prompt passes the period, writing
  and ark rules above (STILL_PROMPT_REFUSED). episode_build.request (frame_refusal) refuses by the same function.
- a still whose prompt names a prop (its E123 phrase; for parts 1-8 the ark anywhere) was made with every
  approved reference image of that prop (props.json, props.py; E122), recorded by sha256 in its record:
  STILL_PROP_UNREFERENCED (also while the prop is still DRAFT). scene_stills.py prepare, finalize and approve
  refuse the same by prop_reference_problems.
A character used but not yet APPROVED is a problem; the Keeper while DRAFT is ONE pending row.

A plan that passes is also run through the build's own functions (E106): episode_build.predict (retime, talking
records, shares, length, the compose's cuts and holds on the planned clip lengths) and reference_problems (kept
reference records and images, counted as the request sends them); their refusals come back as "BUILD <code> ...".

usage: plan_check.py PLAN.json [--strict]   prints JSON {problems, pending, estimate}; exit 1 on a problem
                                            (--strict: also on a pending row and on a path episode.yml would refuse,
                                            PLAN_PATH / PLAN_EPISODE_MISMATCH; episode_build runs it strict)
"""
import hashlib
import json
import math
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "migration" / "production" / "characters"))
sys.path.insert(0, str(ROOT / "migration" / "publish"))
import characters as ch  # noqa: E402
import props as prop_refs  # noqa: E402  (E122: a prop's approved reference images)
import kjv_check  # noqa: E402
import publish_episode  # noqa: E402
import reviewer_identity  # noqa: E402
from voice_pace import SHORT_PACE, VOICE_PACE, VOICE_SLOWEST  # noqa: E402  (one measured table, Short and long)

VERSION = "bible-plan-v2"
KINDS = ("story", "scripture", "insight", "cta")
LESSON_KINDS = ("insight", "cta")
EPISODE_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SHOT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
# episode.yml's plan input, character for character (test_refusal_parity checks the workflow holds this pattern)
PLAN_PATH = re.compile(r"^migration/production/bible/plans/([a-z0-9]+(-[a-z0-9]+)*)\.json$")
RATIOS = ("9:16",)                   # Shorts only
# Kokoro pace of the narration (the Keeper, am_michael), words a second: 2.30-2.98 on Genesis 6
# (evidence/pavo/20261025/genesis-06/compose/timeline.json), 2.756 over the 82 lines of genesis-07 to 10, 1.99-3.63 a
# line (evidence/voice/20261026/kokoro-pace.json). Estimates use 2.75 (the 170-179 s band is narrow: the measured length
# decides, episode_build lines); the talking-clip ceilings use the slowest. Every other voice (a character's, God's)
# has its own two measured bounds in voice_pace.py (E104): at 2.75 a 12-word line of Eve's passed here and died at
# the build.
WPS = 2.75
WPS_SLOWEST = 2.25
SLOW_RATIO = WPS_SLOWEST / WPS       # the slowest pace, as a share of the normal one
LINE_GAP = 0.35                      # silence between lines (episode_build.LINE_GAP)
TAIL = 1.2                           # short_engine tail after the last word
KEEPER_AUDIO = (2.0, 12.0)           # Flash input audio, per request
SPEAKER_AUDIO = KEEPER_AUDIO         # a character's line goes to Pavo the same way; God's line fills one clip
KEEPER_SHARE_MAX = 0.25
LESSON_SHARE_MAX = 0.25
SCENE_SECONDS = (4, 12)
ESTABLISHING_HOLD = 2.0
ESTABLISHING_SHARE_MAX = 0.15
MAX_SLOW = 1.3                       # short_engine.MAX_SLOW
PROMPT_CHARS = (60, 1500)
SHOT_SIZE = re.compile(r"(?i)\b(extreme close-up|close-up|close up|medium|wide|full shot|long shot|establishing|"
                       r"over-the-shoulder|low[- ]angle|high[- ]angle|aerial|macro|insert)\b")
CAMERA_MOVE = re.compile(r"(?i)\b(push-in|push in|pull-back|pull back|pull-out|tracking|dolly|crane|pan|tilt|orbit|"
                         r"handheld|static|locked-off|slow zoom|drift)\b")
ANONYMOUS = re.compile(r"(?i)\b(from behind|seen from behind|in silhouette|silhouettes?|backs? to the camera|"
                       r"faces? (?:never )?(?:unseen|hidden|in shadow|not visible|never visible))\b")
DIVINE = re.compile(r"(?i)\b(God|Lord|LORD|Jehovah|Yahweh|the Almighty|the Creator|the Father|the Most High)\b")
DIVINE_MEDIUM = re.compile(r"(?i)\b(light|wind|fire|flame|voice|glow|radiance|sunbeams?|rays?)\b")
DIVINE_FIGURE = re.compile(r"(?i)\b(face|faces|figure|body|hands?|arms?|eyes|beard|robes?|throne|man|person|"
                           r"stands?|standing|sits?|seated|walks?|walking|form of|shape of|appears as)\b")
# God's voice-over shot: what carries Him on screen, and the words that would put a person in it
GOD_SHOT_MEDIUM = re.compile(r"(?i)\b(light|storm|clouds?|lightning|thunder|wind|fire|flames?|glow|sunbeams?|rays?|"
                             r"rain|sky)\b")
# (a word list can be written around, so episode_build also runs the face landmarker on the generated clip)
GOD_SHOT_PERSON = re.compile(r"(?i)\b(face|faces|eyes|lips|mouth|man|men|woman|women|person|people|figures?|crowds?|"
                             r"child|children|silhouettes?|hands?|body|bodies|elders?|shepherds?|angels?|kings?|"
                             r"boys?|girls?|his|her|hers|him|robes?|staff|beard(?:ed)?|prophets?|priests?|"
                             r"warriors?|travell?ers?|herders?|family|mother|father|son|daughter)\b")
NO_PEOPLE_TAIL = re.compile(r"(?i)\bno (people|person|faces?|figures?)\b")
SPEAKS = re.compile(r"(?i)\bspeak")
# E98: the lips check found the face and the lips only when the Keeper faced the lens on a still frame
KEEPER_POSE = ("static camera", "looks straight into the camera")
KEEPER_POSE_OFF = re.compile(r"(?i)push-in|pull(?:s|ing)?[ -]back|\bleans?\b|\bbow(?:s|ing)?\b|tracking shot|\borbit")
# a line without a `reference` that quotes the KJV anyway: 8 consecutive words of the KJV (kjv_check's text)
KJV_RUN = 8
# E108 (review of genesis-07 run 40341856955): no scene prompt stated its period, so Pavo filled a lane or a horizon
# with whatever it knows best: a cobbled European street with a man in a long coat and a glass kerosene lantern
# (s-walker), a town of stone with church towers (s-family, s-wind), a stone village with chimneys (s-theft), a
# peaked cap, glass jars. Every scene prompt (God's voice-over and a speaking character's shot are scenes too; the
# Keeper's own campfire is not) states its story's period word for word: the setting and the exclusions. The owner
# asked for both, although PROMPT_GUIDE warns that naming a thing can prime it; the probes of the rewritten shots
# (evidence/pavo/20261026/period/) are the measure. A story's period comes from the plan (`period`: a preset name or
# its own {"setting", "exclude", "avoid"?}) or, when the plan names none, from its passage (STORY_PERIODS); a story with
# neither is SCENE_PERIOD_MISSING, so a later story cannot slip through without one.
PERIOD_SETTING = "The ancient Near East before the flood: only goat-hair tents, open fires and torches on the open plain."
PERIOD_EXCLUDE = "No stone buildings, towers, churches, glass lanterns, modern clothing or roads."
# what the rest of the prompt (the setting and exclusion sentences taken out) may not ask for: words that put a later
# age or a built town on screen. Review of #426: "city of tents", "lane" and "room" are the words that drew the
# street, the town and the house in run 40341856955, so they are refused too; a tent's or goat-hair wall is not a
# built wall; "glass" and "cap" only as the object ("still as glass" and "snow caps" are not refused)
PERIOD_AVOID = (r"streets?", r"roads?", r"cobbl\w*", r"pavements?", r"lanterns?", r"kerosene",
                r"glass (?:lanterns?|lamps?|jars?|bottles?|windows?|panes?|cups?)", r"windows?",
                r"towers?", r"church\w*", r"steeples?", r"spires?", r"chimneys?", r"castles?", r"domes?",
                r"towns?", r"villages?", r"cit(?:y|ies)", r"lanes?", r"buildings?", r"(?:mud-)?bricks?",
                r"(?<!tent )(?<!goat-hair )walls?", r"houses?", r"rooms?", r"tables?",
                r"coats?", r"hats?", r"(?:peaked|flat|baseball|cloth) caps?")
# the flood and the new earth (genesis-09 to 10: the waters, Ararat): the same exclusions. E123: the sentence names no
# ark (its first wording, PERIOD_SETTING_FLOOD_E113, "the great wooden ark", drew an ark into stills that show none, and
# the word pulled the ship prior: evidence/pavo/20261027/genesis-09-ark-probe/)
PERIOD_SETTING_FLOOD_E113 = ("The ancient Near East in the days of the flood: the great wooden ark, the open water, the "
                             "mountains of Ararat and the empty new earth.")
PERIOD_SETTING_FLOOD = ("The ancient Near East in the days of the flood: the open water, the mountains of Ararat and the "
                        "empty new earth.")
# the making of the world and Eden (the arc-01 long, Genesis 1-3): no human work at all
PERIOD_SETTING_EDEN = ("The world at its making and the garden of Eden: untouched wild land, rivers, trees and open "
                       "sky.")
PERIODS = {"eden": {"setting": PERIOD_SETTING_EDEN, "exclude": PERIOD_EXCLUDE, "avoid": list(PERIOD_AVOID)},
           "before-the-flood": {"setting": PERIOD_SETTING, "exclude": PERIOD_EXCLUDE, "avoid": list(PERIOD_AVOID)},
           "the-flood": {"setting": PERIOD_SETTING_FLOOD, "exclude": PERIOD_EXCLUDE, "avoid": list(PERIOD_AVOID)}}
# (book, first chapter, last chapter, period) for a plan with no `period`: Cain's city to the eve of the flood (Genesis
# 6:14-22, the ark commanded, is still before it), then the flood to the covenant of the rainbow (7-9)
STORY_PERIODS = (("Genesis", 1, 3, "eden"), ("Genesis", 4, 6, "before-the-flood"), ("Genesis", 7, 9, "the-flood"))
# E113 (frame review of genesis-08 run 40438106839, evidence/pavo/20261027/genesis-08-r1/review.json): 7 of 29 scene
# shots were rejected because each prompt described the ark in its own words ("a huge wooden frame", "the distant
# hull", "the towering hull", "tall curved wooden ribs") and Pavo drew a Viking longship with a spiked prow, a
# steamship with a smoking funnel, a galleon with a dragon prow, a round vat with a chimney-like post, separate rib
# arcs; genesis-09's probes (evidence/pavo/20261027/genesis-09/) drew a sailing ship, a galleon, a barn, a dome, a
# funnel and a red waterline band the same way. The ark is a prop with a fixed look, like a character's: every scene
# prompt that names it (or a hull, keel, ship, boat or vessel) carries ARK_LOOK and ARK_EXCLUDE word for word, the
# shape taken from the wordings that passed those probes (s-ridge 3, s-board 2, s-scorn 7, s-silent 2: "long, low,
# box-shaped wooden hull", "straight sides of rough planks", "flat square ends", "the same low height from end to
# end"); the shot's own words say only its state (half-built with its ribs, or finished and pitch-black), never its
# shape again. Outside the two sentences a scene prompt names no ship (ARK_AVOID: "a long, low wooden ship with
# gently curved sides" drew curled prows and a deckhouse in genesis-09, and "ship", "boat" or "mast" invite one).
ARK_LOOK = ("The ark is one long, low, box-shaped wooden hull with straight sides of rough planks and flat square ends, "
            "the same low height from end to end.")
ARK_EXCLUDE = ("The ark has no mast, sail, prow, figurehead, funnel or smokestack, no smoke rising from it and no band "
               "along its waterline.")
# E122 (review of #462): the ark is also named without these words ("A huge timber box of rough planks", "a great
# wooden barge", "Noah's great gopher-wood house"); each such name needs the look and the references the same way
ARK_MENTION = (r"arks?", r"hulls?", r"keels?", r"ships?", r"boats?", r"vessels?", r"barges?", r"crafts?",
               r"gopher[- ]?wood", r"(?:wooden|timber|plank) (?:box(?:es)?|houses?|structures?|chests?)")
ARK_AVOID = (r"ships?", r"boats?", r"vessels?", r"barges?", r"galleons?", r"longships?", r"masts?", r"sails?", r"rigging",
             r"prows?", r"figureheads?", r"funnels?", r"smokestacks?", r"(?:gently )?curved sides")
# E113, the one narrow exemption (orchestrator, 2026-10-27): genesis-08's shots whose clips were already approved at
# 9.5 in runs 40438106839/40460764662 keep main's prompt at E113 time (a new prompt is a new request, regenerated:
# rework). A plan may list shot ids in `ark_look_grandfathered` only when it is genesis-08-short and only for these
# shots, each with exactly this prompt (sha256); anything else is ARK_GRANDFATHER_REFUSED and the shot is checked.
ARK_GRANDFATHERED = {"genesis-08-short": {
    "s-voice": "23c0911b05967df9c01a15eb72bfaae456aca1ee236a0807f6dd27a200303a98",
    "s-watchers": "4e0bcd51714662592612f88a5f30adb5bb2d2565a0f5735fc588dde6cea00385",
    "s-laugh": "3be92537de42b76b8fd7ed02b9179a96393796cdc7499b7c84344d5df2b21be6",
    "s-pitch": "bec69ae6a2fe0c6b2695ee4ce2fdafabb2e483acf9feb09b4b4b97fbce9336b1",
    "s-measure": "8e307e215a8dce9c36c8472738f3ee6baa7ad894abbef8031024481a5c6dd315",
    "s-ribs": "81a3f45c59cea9582b75b4c5c254b7be017bd3fc4f30a2a049f0d0542cd0f201",
    "s-beam": "130dfdcd5708d4cc0cdc61d9aa99278a60dfc38a6bbfe978b906fc276fd9399f",
    "s-jeer": "838c315a5613ab4ce5f883ac3f1c0b936b8811809cc89377a11673ae6df2704b",
    "s-scorn": "8ecdcb486035b2fa6b262bcfe84af17fd12323e57b47f3c4698320400ee1f999",
    "s-wedding": "2299c3dc6109b535894a8a372f6db0dc0375aa068662cde6903ef5c056422d96",
    "s-hill": "135efd4a8ca4f7f294f56ab7c12e80c32cf6d51f805a023a340f2f06a5819fa1",
    "s-stones": "68df38a128cc9aa86558e3e437a1195441a17d5613c4e5d2c26be276590a4f60",
    "s-alone": "07c7697091fda0564424ffee2ead87a8a6d0ba549ac1e55ecd5096d1e5a53897",
    "s-covenant": "1f0ef76400b8b3280df8841228d6e82c825c270c233385beaafac01c2e8580ee",
    "s-torches": "df0e0000fbc0843843d62c4c8ddecb5e5ef541745f1e10f284c71c8eee0c31cb",
    "s-finished": "10072ac8e1eba68d02b3982ae679030690d02ad52efc399c5952c1c27f4730c9",
    "s-silent": "a55447837347eaf90133a0403d46dc5f65d6198acffb9c025dbe8c5a1f43e6cf"}}
# E123 (Claude's review of genesis-09 run 2026102704 and the probe evidence/pavo/20261027/genesis-09-ark-probe/): the
# 64 stills made WITH the ark's approved references still drew curved bows, prows, cabins and smoking funnels. With
# ARK_LOOK + ARK_EXCLUDE (V1) 0 of 3 held the box; with the ark described only positively, no negation and none of the
# words ark/hull/ship/boat/vessel, plus the references (V2), 3 of 3 held it (without references, V3, the box shrank to
# a crate or a shed). An image model reads "no mast, sail, prow, funnel or smokestack, no smoke rising" as a list of
# things to draw, and "ark"/"hull" pull its ship prior. From part 9 (ARK_E123_FROM_PART) the ark is named only by
# ARK_PHRASE, word for word (a noun phrase that sits in the shot's own sentence; its first letter may be capital), and
# a scene, still or thumbnail prompt holds none of ARK_WORDS (ARK_LOOK_CONFLICT); "crate" without the phrase is
# ARK_LOOK_NOT_CANONICAL. The phrase is how a still is known to show the ark (prop_references: the references go with
# it, and only with it). Parts 1-8 are published and keep E113's rule.
ARK_PHRASE = ("a giant long rectangular wooden crate of rough planks smeared pitch-black, with a flat plank roof and flat "
              "square ends, as tall at both ends as in the middle")
ARK_WORDS = tuple(dict.fromkeys(ARK_MENTION + ARK_AVOID + (
    r"figureheads?", r"smokestacks?", r"funnels?", r"chimneys?", r"no smoke", r"smoke rising from it", r"waterlines?",
    r"deckhouses?", r"cabins?", r"bowsprits?", r"oars?", r"rudders?",
    # review of #465: the cheap bypasses inside the ark's stories ("bow" never: Genesis 9:13, the rainbow)
    r"galleys?", r"keelless", r"decks?", r"floating (?:box(?:es)?|houses?|structures?)", r"(?:wooden |timber |plank )?enclosures?")))
ARK_E123_FROM_PART = 9
# props: a thing seen in many shots, with one look stated word for word wherever a prompt names it (E113: `look` and
# `exclude`, parts 1-8; E123: `phrase`, the only name it has, and `words`, what no prompt says, from part 9)
PROPS = {"ark": {"look": ARK_LOOK, "exclude": ARK_EXCLUDE, "mentions": list(ARK_MENTION),
                 "avoid": list(ARK_AVOID), "phrase": ARK_PHRASE, "words": list(ARK_WORDS), "noun": r"crates?"}}


# review of #465: the ark's words belong to the ark's stories. Elsewhere Jonah's ship, the fishermen's boat, Moses' ark of
# bulrushes, a clay vessel or a crate of figs are what they say; inside them, the 9.5 frame review stays the last guard
# against a synonym no list holds.
ARK_PERIODS = ("before-the-flood", "the-flood")
ARK_CHAPTERS = ("Genesis", 6, 10)


def ark_period(plan):
    """Whether a plan (a Short, a long, a thumbnail's {"period"}) tells an ark story: its `period` is one of
    ARK_PERIODS, or its passage resolves to one of them (STORY_PERIODS) or reaches Genesis 6-10."""
    if not isinstance(plan, dict):
        return False
    given = plan.get("period")
    if isinstance(given, str):
        return given in ARK_PERIODS
    found = passage_chapters(plan.get("passage"))
    if found:
        book, first, last = found
        if book == ARK_CHAPTERS[0] and first <= ARK_CHAPTERS[2] and last >= ARK_CHAPTERS[1]:
            return True
        names = {next((n for b, lo, hi, n in STORY_PERIODS if b == book and lo <= c <= hi), None)
                 for c in range(first, last + 1)}
        return bool(names & set(ARK_PERIODS))
    return False


def ark_e113(plan):
    """Parts 1-8 (published Shorts, an int `part` below ARK_E123_FROM_PART) keep E113's rule."""
    part = plan.get("part") if isinstance(plan, dict) else None
    return type(part) is int and part < ARK_E123_FROM_PART


def ark_e123(plan):
    """E123: whether a plan's prompts follow the positive wording (ARK_PHRASE, no ARK_WORDS): an ark story (ark_period)
    that is not a published Short; a thumbnail's or a long's plan without a part too, scoped by its period."""
    return isinstance(plan, dict) and not ark_e113(plan) and ark_period(plan)


def has_phrase(prompt, phrase):
    """The prop's canonical phrase in a prompt, word for word (its first letter in either case)."""
    return isinstance(prompt, str) and (phrase in prompt or phrase[:1].upper() + phrase[1:] in prompt)
# "Genesis 6:5-13" (chapter 6), "Genesis 6:14-7:5" (6 to 7), "Genesis 6-8", "Genesis 7"; the end chapter matters (a
# passage may cross the flood)
PASSAGE = re.compile(r"^\s*((?:[1-3] )?[A-Z][a-z]+(?: of [A-Z][a-z]+)?)\s+(\d+)(:\d+)?"
                     r"(?:\s*[-\u2013]\s*(\d+)(:\d+)?)?")


def passage_chapters(passage):
    """(book, first chapter, last chapter) of a passage, or None."""
    m = PASSAGE.match(passage or "")
    if not m:
        return None
    first = int(m.group(2))
    if m.group(4) is None:
        last = first
    elif m.group(3) and not m.group(5):   # 6:5-13: a verse range inside chapter 6
        last = first
    else:                                  # 6:14-7:5 or 6-8
        last = int(m.group(4))
    return m.group(1), first, max(first, last)
# E95 (measured 2026-10-26, evidence/pavo/20261026/keeper-audio-binding.json): Pavo keeps our input audio only when
# the clip it is asked for is at most ~0.65 s longer than the speech; at 1.6 s or more it makes its own track. A talking
# clip is ceil(speech) seconds (4-12), the speech 0.25-0.65 s shorter than it: episode_build retimes a line that misses
# that window to N - 0.45 s (atempo, pitch kept, at most +-10 %); the gap or tail after it is the clip's last frame held.
TALK_CLIP = (4, 12)                  # Pavo clip seconds
TALK_PAD = (0.25, 0.65)              # clip seconds - speech seconds that keep our audio
TALK_PAD_TARGET = round((TALK_PAD[0] + TALK_PAD[1]) / 2, 3)   # 0.45 s: a retimed line is N - 0.45 s
TALK_RETIME_MAX = 0.10               # atempo changes a talking shot's words by at most +-10 % (never its gaps)
TALK_HOLD_MAX = 1.3                  # a talking clip's last frame held at most this long (the gap or the tail)
TALK_CLIP_MAX = float(TALK_CLIP[1])
# the one talking ceiling, plan (at the slowest pace) and build (measured, retimed under it) alike, the closing Keeper
# too: his tail is a held last frame (E95), not clip time
TALK_LINE_MAX = TALK_CLIP[1] - TALK_PAD_TARGET                              # 11.55 s
TALK_MIN = (TALK_CLIP[0] - TALK_PAD_TARGET) / (1 + TALK_RETIME_MAX)         # 3.23 s: one line retimed into a 4 s
#                                                                             clip (a shot of several: talk_min)
# Plan B (owner, 2026-10-26, PROMPT_GUIDE "Keeper voice-over"): an opt-in `"voiceover": true` Keeper shot shows him on
# screen with his mouth closed while his line plays from the voice track, so no one appears to speak with a still mouth
# and there is no lip sync to miss. Its prompt says his lips stay closed and names no speech; lipsync_check
# --still-mouth confirms the clip (MOUTH_TALKING). The default Keeper shot still talks, lip-synced.
VO_SILENT = (re.compile(r"(?i)\blips (?:stay |remain |kept |pressed )?closed\b"), re.compile(r"(?i)\bsilent\b"))
VO_SPEECH = re.compile(r"(?i)\b(speak\w*|spoke|talk\w*|says|saying|said|tells?|telling|whisper\w*|sings?|singing|"
                       r"chant\w*|recit\w*|narrates|narrating|words|audio|lip[- ]?sync\w*|"
                       r"lips (?:moving|move|moves|part|parts|parting|open\w*)|mouth (?:moving|moves|move|open\w*)|"
                       r"opens? his mouth|open mouth)\b")
# the still-mouth check needs his face in 80 % of the frames, as the lips check does: in the direct closed-mouth clips
# (evidence/pavo/20261026/keeper-vo/calibration.json) the face was found only when he faced the lens; looking down
# into the fire (2 % and 17 % of frames), "raises his eyes from the fire" (18 %) and "his eyes sad and kind ... the
# flames flicker beside him" (0.68, 0.60) lost it, so a voice-over Keeper holds the talking pose too (KEEPER_POSE words)
# and no phrasing that turns his eyes or head off the lens (review of #423)
_LOOK = r"(?:looks?|looking|gazes?|gazing|glances?|glancing|stares?|staring|peers?|peering)"
_OFF_LENS = r"(?:the |his )?(?:camp)?(?:fire|flames?|embers?|coals?|scroll|ground|hands?|sky|stars|sand|side)"
VO_GAZE_OFF = re.compile(
    rf"(?i)\b{_LOOK} (?:down|away|aside|up|off|sideways)\b|\b{_LOOK} (?:in)?to {_OFF_LENS}\b|\b{_LOOK} at {_OFF_LENS}\b|"
    rf"\beyes (?:on|to|toward|towards) {_OFF_LENS}\b|\beyes (?:\w+ )?from {_OFF_LENS}\b|"
    r"\blower(?:s|ing|ed)? his (?:eyes|gaze|head)\b|\b(?:eyes|gaze|head) (?:lowered|downcast|cast down|bowed|down)\b|"
    r"\bhead (?:tilted|turned|bent)\b|\bturns? (?:his head|away|aside)\b|\bdowncast\b|\bprofile\b|"
    r"\bfrom the side\b|\bthree-quarter\b|\breads?(?:ing)? (?:the |his )?scroll\b|\beyes (?:closed|shut)\b|"
    r"\bcloses his eyes\b")
VO_LINE_MAX = TALK_CLIP[1] * MAX_SLOW   # gap before + line + gap or tail after on one 12 s clip, slowed at most MAX_SLOW
VO_LINE_MIN = KEEPER_AUDIO[0]           # the floor lines_step holds a Keeper line to (2.0 s), voice-over or not
_KJV_TEXT = []


def words(text):
    return len(text.split())


def pace(item):
    """Words a second of the voice that speaks this line, at its fastest: the narration (the Keeper's) at WPS, a
    speaker's line at its voice's fastest measured run in a Short (SHORT_PACE, else VOICE_PACE; WPS until measured,
    and a talking line is then VOICE_PACE_UNMEASURED)."""
    who = item.get("speaker")
    return WPS if who in (None, ch.NARRATOR) else SHORT_PACE.get(who, VOICE_PACE.get(who, WPS))


def slowest_pace(item):
    """The same voice at its slowest: WPS_SLOWEST for the narration, VOICE_SLOWEST for a speaker (E104)."""
    who = item.get("speaker")
    return WPS_SLOWEST if who in (None, ch.NARRATOR) else VOICE_SLOWEST.get(who, WPS_SLOWEST)


def _plain(text):
    return re.findall(r"[a-z]+", text.lower().replace("’", "'").replace("'", ""))


def _kjv_problem(reference, text):
    try:
        return kjv_check.problem(reference, text)
    except ValueError as exc:   # an unparsable reference ("REFERENCE_UNPARSED ...")
        return str(exc)


def kjv_quote(text, run=KJV_RUN):
    """The KJV verse a line quotes without saying so: (reference, words) of the first verse holding `run` consecutive
    words of the line, else None (case and punctuation ignored)."""
    if not _KJV_TEXT:
        verses = kjv_check.verses()
        bible = [x for t in verses.values() for x in _plain(t)]
        _KJV_TEXT.append(" " + " ".join(bible) + " ")
        _KJV_TEXT.append(verses)
        _KJV_TEXT.append({hash(" ".join(bible[k:k + KJV_RUN])) for k in range(len(bible) - KJV_RUN + 1)})
    w = _plain(text)
    for k in range(len(w) - run + 1):
        gram = " " + " ".join(w[k:k + run]) + " "
        if (run != KJV_RUN or hash(gram.strip()) in _KJV_TEXT[2]) and gram in _KJV_TEXT[0]:
            for (book, c, v), t in _KJV_TEXT[1].items():
                if gram in " " + " ".join(_plain(t)) + " ":
                    return f"{book.title()} {c}:{v} (KJV)", gram.strip()
            return "a passage across verses", gram.strip()
    return None


def speaking(shot):
    return isinstance(shot, dict) and shot.get("speaker") is not None


def _lines_problem(i, shot, n):
    lines = shot.get("lines")
    if (not isinstance(lines, list) or not lines or not all(type(x) is int for x in lines)
            or lines != list(range(lines[0], lines[0] + len(lines))) or lines[0] < 0 or lines[-1] >= n):
        return f"SHOT_LINES shot {i} {shot.get('id')}: consecutive narration indices 0-{n - 1}"
    return None


def sequence(plan):
    """The voice track in order: (items, carried). items are the narration lines the shots carry (`line`: its
    narration index) and each speaking shot's own line (`speaker`, `shot`), in the order the shots come; carried[i]
    are the item indices shot i carries. A spoken line with a `reference` is Scripture, else our words (story)."""
    items, where, carried = [], {}, []
    for s in plan["shots"]:
        if speaking(s):
            item = {"kind": "scripture" if s.get("reference") else "story", "text": s["line"], "speaker": s["speaker"],
                    "shot": s["id"]}
            if s.get("reference"):
                item["reference"] = s["reference"]
            items.append(item)
            carried.append([len(items) - 1])
            continue
        idx = []
        for k in s["lines"]:
            if k not in where:
                where[k] = len(items)
                items.append(dict(plan["narration"][k], line=k))
            idx.append(where[k])
        carried.append(idx)
    return items, carried


def groups(shots, carried=None):
    """Runs of consecutive shots carrying the same words: [(first shot index, last shot index, item indices)].
    Without `carried`, by the shots' narration `lines` (a speaking shot is always a run of its own)."""
    out = []
    for i, s in enumerate(shots):
        key = carried[i] if carried is not None else (None if speaking(s) else s["lines"])
        if out and key is not None and key == out[-1][2] and not speaking(shots[out[-1][0]]) and not speaking(s):
            out[-1] = (out[-1][0], i, out[-1][2])
        else:
            out.append((i, i, key))
    return out


def talk_need(seconds):
    """Clip seconds a talking line is generated at (E95): ceil(speech), at least 4. The gap or the tail after it is
    the clip's last frame held in the compose, never clip time Pavo would fill with its own audio."""
    return max(TALK_CLIP[0], math.ceil(seconds - 1e-6))


def talk_fits(seconds):
    """Pavo keeps our input audio: the clip is 0.25-0.65 s longer than the speech (TALK_PAD)."""
    pad = talk_need(seconds) - seconds
    return TALK_PAD[0] - 1e-6 <= pad <= TALK_PAD[1] + 1e-6


def talk_min(gaps=0.0):
    """The shortest talking shot a 4 s clip takes: its gaps (never stretched) + the shortest words atempo stretches
    into N - 0.45 s within TALK_RETIME_MAX (TALK_MIN for one line)."""
    return gaps + (TALK_CLIP[0] - TALK_PAD_TARGET - gaps) / (1 + TALK_RETIME_MAX)


def _reach(gaps):
    """The words lengths some clip reaches (talk_retime is not None), as intervals: each clip's +-TALK_RETIME_MAX
    stretch of the words into N - 0.45 s, and the speech that fits it untouched under TALK_LINE_MAX."""
    out = []
    for n in range(TALK_CLIP[0], TALK_CLIP[1] + 1):
        target = n - TALK_PAD_TARGET - gaps
        if target > 0:
            out.append((target / (1 + TALK_RETIME_MAX), target / (1 - TALK_RETIME_MAX)))
        a, b = n - TALK_PAD[1] - gaps, min(n - TALK_PAD[0], TALK_LINE_MAX) - gaps
        if b > max(a, 0):
            out.append((max(a, 0), b))
    return sorted(out)


def talk_reach_gap(low, high, gaps=0.0):
    """The first words length in [low, high] (s) that no clip reaches, else None. plan_check judges a talking shot's
    words from the normal pace (WPS) to the slowest (WPS_SLOWEST), since the build retimes the measured length."""
    x, covered = low, False
    for a, b in _reach(gaps):
        if b + 1e-9 < x:
            continue
        if a - 1e-9 > x:
            break
        x, covered = max(x, b), True
        if x >= high:
            return None
    return x if covered else low


def talk_retime(words, gaps=0.0):
    """(target, stretch) for a talking shot whose words last `words` s with `gaps` s of fixed silence between its
    lines, or None when no clip reaches it: itself (stretch 1) when it fits a 4-12 s clip under TALK_LINE_MAX, else
    N - 0.45 s for the clip length N whose stretch of the words (target - gaps) / words is nearest 1, within
    +-TALK_RETIME_MAX. The words alone are stretched (atempo 1 / stretch): the gaps stay. plan_check refuses an
    estimate it returns None for (TALK_LINE_UNREACHABLE); episode_build lines retimes by it (TALK_LINE_RETIME_OVER)."""
    speech = words + gaps
    if talk_fits(speech) and speech <= TALK_LINE_MAX + 1e-9:
        return round(speech, 3), 1.0
    targets = [n - TALK_PAD_TARGET for n in range(TALK_CLIP[0], TALK_CLIP[1] + 1) if n - TALK_PAD_TARGET > gaps]
    if words <= 0 or not targets:
        return None
    best = min(targets, key=lambda t: abs((t - gaps) / words - 1))
    stretch = (best - gaps) / words
    return (round(best, 3), stretch) if abs(stretch - 1) <= TALK_RETIME_MAX + 1e-9 else None


def voiceover(shot):
    """Plan B (owner, 2026-10-26): a Keeper shot flagged `"voiceover": true` shows him silent, mouth closed, while his
    line plays from the voice track (no input audio, no retime, no lipsync; lipsync_check --still-mouth instead)."""
    return isinstance(shot, dict) and shot.get("kind") == "keeper" and shot.get("voiceover") is True


def vo_cover(shots, i, long=False):
    """(before, after): the seconds a voice-over Keeper clip covers around its line, by episode_build.compose_shots'
    own run logic (review of #423: plan_check, lines_step, shot_seconds and the compose share this one helper). A
    talking shot before it ends on its last word (it covers the gap only when the next shot talks too), so the clip
    covers that gap; after scenes or a voice-over shot it starts on its first word. It ends where the next line starts
    (the gap), or with the closing tail when it is the last shot. A long (E130, long_build.compose_long_shots) cuts
    every run from its first word to the next run's, at LONG_LINE_GAP: nothing before, the gap or tail after."""
    if long:
        import long_plan_check
        return 0.0, (TAIL if i == len(shots) - 1 else long_plan_check.LONG_LINE_GAP)
    before = LINE_GAP if i > 0 and talking(shots[i - 1]) else 0.0
    after = TAIL if i == len(shots) - 1 else LINE_GAP
    return before, after


def vo_covered(seconds, shots, i, long=False):
    """The time a voice-over Keeper clip covers: the gap before, his line's `seconds` and the gap or tail after."""
    before, after = vo_cover(shots, i, long)
    return before + seconds + after


def vo_clip_seconds(covered):
    """Clip seconds of a voice-over Keeper shot for the time it covers (vo_covered): ceil, 4-12 s; the compose slows
    a clip at most MAX_SLOW to cover more (VO_LINE_MAX)."""
    return int(min(TALK_CLIP[1], max(TALK_CLIP[0], math.ceil(covered - 1e-6))))


def talking(shot):
    """A shot whose clip carries its own words with the speaker's lips on them (Pavo input audio, lipsync_check):
    the Keeper (unless his shot is a voice-over, plan B), or a scene where a character speaks. God's line is a
    voice-over: not a talking clip."""
    return (shot["kind"] == "keeper" and not voiceover(shot)) or (speaking(shot) and shot["speaker"] != ch.GOD)


def god_problem(prompt):
    if not DIVINE.search(prompt):
        return None
    if DIVINE_FIGURE.search(prompt) or not DIVINE_MEDIUM.search(prompt):
        return "GOD_AS_A_FIGURE (God only as light, wind, fire or voice; never a body, face, hands, robe or throne)"
    return None


def prompt_problems(i, shot):
    p = shot.get("prompt")
    if not isinstance(p, str) or not PROMPT_CHARS[0] <= len(p) <= PROMPT_CHARS[1]:
        return [f"PROMPT_LENGTH shot {i} {shot.get('id')} ({PROMPT_CHARS[0]}-{PROMPT_CHARS[1]} characters)"]
    out = []
    # five parts (PROMPT_GUIDE): cinematography (shot size + ONE camera move), subject, action, context, style
    if not SHOT_SIZE.search(p) or not CAMERA_MOVE.search(p):
        out.append(f"PROMPT_NO_CINEMATOGRAPHY shot {i} {shot['id']} (shot size and one camera move first)")
    if len([s for s in re.split(r"(?<=[.!?])\s+", p) if s.strip()]) < 4:
        out.append(f"PROMPT_NOT_FIVE_PARTS shot {i} {shot['id']} (cinematography. subject + action. context. style.)")
    god = god_problem(p)
    if god:
        out.append(f"{god} shot {i} {shot['id']}")
    return out


def _given_period(given):
    """The plan's own `period`: (period, None) or (None, the reason it is refused)."""
    if isinstance(given, str):
        if given in PERIODS:
            return PERIODS[given], None
        return None, f"unknown preset {given!r}; one of {sorted(PERIODS)} or its own setting and exclusions"
    if not isinstance(given, dict):
        return None, f"a preset name or {{setting, exclude, avoid?}}, not {type(given).__name__}"
    for k in ("setting", "exclude"):
        if not isinstance(given.get(k), str) or not given[k].strip():
            return None, f"`{k}` is missing or empty"
    avoid = given.get("avoid", list(PERIOD_AVOID))   # no `avoid`: the shared list, never none
    if not isinstance(avoid, list) or not avoid or not all(isinstance(a, str) and a for a in avoid):
        return None, "`avoid` is a non-empty list of regular expressions"
    for a in avoid:
        try:
            re.compile(rf"(?i)\b(?:{a})\b")
        except re.error as exc:
            return None, f"`avoid` {a!r} is not a regular expression ({exc})"
    return {"setting": given["setting"].strip(), "exclude": given["exclude"].strip(), "avoid": avoid}, None


def resolve_period(plan):
    """E108: (period, problem). The period {"setting", "exclude", "avoid"} comes from the plan's `period` (a PERIODS
    name or its own wording; a malformed or unknown one is PERIOD_INVALID, never passed over for the passage) or,
    when the plan names none, from every chapter of its passage (STORY_PERIODS): chapters in two periods, or partly
    in none, are PERIOD_AMBIGUOUS until the plan sets `period`; none is SCENE_PERIOD_MISSING (missing_period, the
    one message)."""
    if "period" in plan:
        per, why = _given_period(plan["period"])
        return (per, None) if per else (None, f"PERIOD_INVALID (the plan's `period`: {why}; E108)")
    passage = plan.get("passage") or ""
    found = passage_chapters(passage)
    if found:
        book, first, last = found
        names = {next((n for b, lo, hi, n in STORY_PERIODS if b == book and lo <= c <= hi), None)
                 for c in range(first, last + 1)}
        if len(names) > 1:
            return None, (f"PERIOD_AMBIGUOUS ({passage} spans {sorted(str(n) for n in names)}: set the plan's "
                          "`period`; E108)")
        if names != {None}:
            return PERIODS[names.pop()], None
    return None, missing_period(plan)


def missing_period(plan):
    """The one SCENE_PERIOD_MISSING message for a story with no period (plan_check, long_plan_check, the build)."""
    return (f"SCENE_PERIOD_MISSING (no period for {plan.get('passage') or 'this story'}: the plan's `period` names one "
            f"of {sorted(PERIODS)} or gives its own setting and exclusions; E108)")


def period(plan):
    """The story's period, or None (resolve_period says why)."""
    return resolve_period(plan)[0]


def period_problems(i, shot, per):
    """E108: a scene prompt states its period word for word (setting and exclusions) and, with both sentences taken
    out, names nothing the period excludes. [] for a Keeper shot (his own campfire, his own look) and a window."""
    if shot.get("kind") != "scene" or not isinstance(shot.get("prompt"), str) or per is None:
        return []
    sid, p = shot.get("id"), shot["prompt"]
    out = []
    missing = [w for w in (per["setting"], per["exclude"]) if w not in p]
    if missing:
        out.append(f"SCENE_PERIOD_MISSING shot {i} {sid} (the prompt states, word for word: "
                   + " ".join(f"'{w}'" for w in missing) + ")")
    rest = p.replace(per["exclude"], " ").replace(per["setting"], " ")
    hits = sorted({m.group(0).lower() for a in per.get("avoid") or PERIOD_AVOID
                   for m in re.finditer(rf"(?i)\b(?:{a})\b", rest)})
    if hits:
        out.append(f"SCENE_PERIOD_CONFLICT shot {i} {sid} (names what the period excludes: {', '.join(hits)})")
    return out


# E110 (review of genesis-07 run 40357197063): s-scroll asked for "an old scroll ... the ink lines catching the light"
# beside "No text", and Pavo drew lines of legible Arabic-looking script: AI text on screen and a later age's writing in
# the days before the flood. A prompt that asks for writing gets writing, whatever its exclusions say, so a scene prompt
# may not ask for it. Negated mentions ("No text, no logos.", "without letters") are what the prompt keeps out. The
# Keeper's rolled scroll is his approved look (CHARACTER_LOOK_CHANGED keeps it word for word), not a scene; a carved
# idol is not writing.
WRITING = (r"scrolls?", r"ink", r"inked", r"letters?", r"lettering", r"inscri\w+", r"(?:hand)?writing", r"written",
           r"writes?", r"wrote", r"scripts?", r"texts?", r"tablets?", r"parchments?", r"papyr\w+", r"manuscripts?",
           r"books?", r"pages?", r"calligraph\w*", r"glyphs?", r"hieroglyph\w*", r"runes?", r"alphabets?",
           r"symbols?", r"signs? (?:board|post)s?", r"signboards?", r"notes?")
WRITING_RE = re.compile(rf"(?i)\b(?:{'|'.join(WRITING)})\b")
# a negation keeps the next words out: "No people, no text", "without any letters", "never a written word"
WRITING_NEGATED = re.compile(rf"(?i)\b(?:no|without|never)\s+(?:(?:any|a|an|legible|visible|written|carved|"
                             rf"painted)\s+)*(?:{'|'.join(WRITING)})\b")


def writing_problems(i, shot):
    """E110: a scene prompt that asks for writing (outside a negation) is SCENE_WRITING. [] for a Keeper shot."""
    if shot.get("kind") != "scene" or not isinstance(shot.get("prompt"), str):
        return []
    rest = WRITING_NEGATED.sub(" ", shot["prompt"])
    hits = sorted({m.group(0).lower() for m in WRITING_RE.finditer(rest)})
    if not hits:
        return []
    return [f"SCENE_WRITING shot {i} {shot.get('id')} (asks for writing, which Pavo draws as AI text: "
            f"{', '.join(hits)}; show the line without anything written)"]


def plan_writing_problems(shots):
    """E110, shared by plan_check and long_plan_check: every scene prompt's own SCENE_WRITING."""
    return [p for i, s in enumerate(shots) if isinstance(s, dict) for p in writing_problems(i, s)]


def plan_period_problems(plan, shots):
    """E108, shared by plan_check and long_plan_check: the plan-level period refusal (once) when any shot is a
    scene, else every scene prompt's own."""
    if not any(isinstance(s, dict) and s.get("kind") == "scene" for s in shots):
        return []
    per, problem = resolve_period(plan)
    if problem:
        return [problem]
    return [p for i, s in enumerate(shots) if isinstance(s, dict) for p in period_problems(i, s, per)]


def prop_problems(i, shot, per=None, plan=None):
    """E123: with a plan from part 9 (ark_e123), prop_problems_e123. E113: a scene prompt that names a prop (PROPS: the ark, a hull, keel, ship, boat or vessel), outside the period
    sentences, carries the prop's look and exclusion sentences word for word (ARK_LOOK_NOT_CANONICAL; one of the two
    alone is refused too); with those and the period sentences taken out, it names nothing the prop's look rules out
    (ARK_LOOK_CONFLICT: ship, boat, mast, prow, funnel...). [] for a Keeper shot."""
    if shot.get("kind") != "scene" or not isinstance(shot.get("prompt"), str):
        return []
    if plan is not None and not ark_e113(plan):   # from part 9: E123 in the ark's stories, nothing elsewhere
        return prop_problems_e123(i, shot) if ark_e123(plan) else []
    sid, p = shot.get("id"), shot["prompt"]
    rest = p
    for w in [per or {}, {"setting": PERIOD_SETTING_FLOOD_E113}] + list(PERIODS.values()):   # "the great wooden ark"
        for k in ("exclude", "setting"):
            if isinstance(w.get(k), str) and w[k]:
                rest = rest.replace(w[k], " ")
    out = []
    for name, prop in PROPS.items():
        tag = name.upper()
        bare = rest.replace(prop["look"], " ").replace(prop["exclude"], " ")
        named = sorted({m.group(0).lower() for a in prop["mentions"] for m in re.finditer(rf"(?i)\b(?:{a})\b", bare)})
        missing = [w for w in (prop["look"], prop["exclude"]) if w not in p]
        if missing and (named or len(missing) == 1):
            out.append(f"{tag}_LOOK_NOT_CANONICAL shot {i} {sid} (names the {name} ({', '.join(named) or 'half its look'}"
                       "): the prompt states, word for word: " + " ".join(f"'{w}'" for w in missing) + "; E113)")
        hits = sorted({m.group(0).lower() for a in prop["avoid"] for m in re.finditer(rf"(?i)\b(?:{a})\b", bare)})
        if hits:
            out.append(f"{tag}_LOOK_CONFLICT shot {i} {sid} (names what the {name}'s look rules out: {', '.join(hits)}; "
                       "the shot says only its state, the look sentence gives its shape; E113)")
    return out


def prop_problems_e123(i, shot):
    """E123: a scene (still, thumbnail) prompt names the prop only by its phrase, word for word, and says none of its
    ship-prior or negated words anywhere, the period sentences included (ARK_LOOK_CONFLICT); its noun ("crate")
    without the phrase is ARK_LOOK_NOT_CANONICAL. [] for a Keeper shot."""
    if shot.get("kind") != "scene" or not isinstance(shot.get("prompt"), str):
        return []
    sid, p, out = shot.get("id"), shot["prompt"], []
    for name, prop in PROPS.items():
        tag = name.upper()
        hits = sorted({m.group(0).lower() for a in prop["words"] for m in re.finditer(rf"(?i)\b(?:{a})\b", p)})
        if hits:
            out.append(f"{tag}_LOOK_CONFLICT shot {i} {sid} (says what pulls a ship or primes what it negates: "
                       f"{', '.join(hits)}; name the {name} only as '{prop['phrase']}', in positive words; E123)")
        if not has_phrase(p, prop["phrase"]) and re.search(rf"(?i)\b(?:{prop['noun']})\b", p):
            out.append(f"{tag}_LOOK_NOT_CANONICAL shot {i} {sid} (names the {name} without its phrase, word for word: "
                       f"'{prop['phrase']}'; E123)")
    return out


def ark_grandfathered(plan, shots):
    """E113: (the shot ids exempt from the ark's look, the ARK_GRANDFATHER_REFUSED problems). Only genesis-08-short's
    listed shots (ARK_GRANDFATHERED) with exactly their prompt at E113 time; the field anywhere else is refused."""
    given = plan.get("ark_look_grandfathered") if isinstance(plan, dict) else None
    if given is None:
        return set(), []
    allowed = ARK_GRANDFATHERED.get(plan.get("episode"))
    if not allowed:
        return set(), [f"ARK_GRANDFATHER_REFUSED (`ark_look_grandfathered` is allowed only in "
                       f"{sorted(ARK_GRANDFATHERED)}, not {plan.get('episode')}; E113)"]
    if not isinstance(given, list) or not all(isinstance(x, str) for x in given):
        return set(), ["ARK_GRANDFATHER_REFUSED (`ark_look_grandfathered` is a list of shot ids; E113)"]
    prompts = {s.get("id"): s.get("prompt") for s in shots if isinstance(s, dict)}
    ok, out = set(), []
    for sid in given:
        prompt = prompts.get(sid)
        if sid not in allowed:
            out.append(f"ARK_GRANDFATHER_REFUSED {sid} (not a shot approved before E113; E113)")
        elif not isinstance(prompt, str) or hashlib.sha256(prompt.encode()).hexdigest() != allowed[sid]:
            out.append(f"ARK_GRANDFATHER_REFUSED {sid} (its prompt is not the one approved before E113; E113)")
        else:
            ok.add(sid)
    return ok, out


# E122: from this part on a scene shot that names a prop is made from an approved still (first_frame), the still made
# with the prop's approved references: text-to-video alone drifts the ark's shape as text-to-image did. Parts 1-8 are
# published or scheduled and stay as they are.
PROP_STILL_FROM_PART = 9


def _named_outside_period(prompt, per=None, mentions=True):
    """The prop names a prompt holds outside the period sentences (the flood's setting names "the great wooden ark"
    in every shot of the period; that sentence alone does not make a shot show the ark)."""
    rest = prompt
    for w in [per or {}, {"setting": PERIOD_SETTING_FLOOD_E113}] + list(PERIODS.values()):
        for k in ("exclude", "setting"):
            if isinstance(w.get(k), str) and w[k]:
                rest = rest.replace(w[k], " ")
    return [name for name, prop in PROPS.items()
            if has_phrase(rest, prop["phrase"]) or (mentions and any(re.search(rf"(?i)\b(?:{a})\b", rest)
                                                                     for a in prop["mentions"]))]


def prop_shot_problems(i, shot, plan, per=None):
    """E122: from part PROP_STILL_FROM_PART on, a scene shot whose prompt names a prop (outside the period sentences)
    starts from an approved still (`first_frame`, whose own check, frame_problems, asks for the prop's references):
    PROP_SHOT_WITHOUT_STILL. A shot with characters cannot take a still (frames and references are exclusive), so its
    words leave the prop out."""
    part = plan.get("part") if isinstance(plan, dict) else None
    if type(part) is not int or part < PROP_STILL_FROM_PART or shot.get("kind") != "scene" \
            or not isinstance(shot.get("prompt"), str) or shot.get("first_frame"):
        return []
    named = _named_outside_period(shot["prompt"], per, mentions=ark_period(plan))
    if not named:
        return []
    how = ("a character shot cannot take a still (Pavo: frames and references are exclusive): leave the "
           f"{', '.join(named)} out of its words" if shot.get("characters") else
           "give it `first_frame`, a still made with the prop's approved references")
    return [f"PROP_SHOT_WITHOUT_STILL shot {i} {shot.get('id')} (names the {', '.join(named)} with no still: {how}; "
            "E122)"]


def plan_prop_problems(plan, shots):
    """E113, shared by plan_check and long_plan_check: every scene prompt's own prop problems, but for the shots
    ark_grandfathered exempts (and its refusals); E122: from part 9, a scene naming a prop starts from its still."""
    per = period(plan) if isinstance(plan, dict) else None
    exempt, out = ark_grandfathered(plan, shots)
    return out + [p for i, s in enumerate(shots) if isinstance(s, dict) and s.get("id") not in exempt
                  for p in prop_problems(i, s, per, plan) + prop_shot_problems(i, s, plan, per)]


STILLS_DIR = HERE / "stills"          # scene stills: <id>.json records, candidates/ (scene_stills.py)
STILL_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
STILL_ID_MAX = 80
FRAME_FIELDS = ("first_frame", "last_frame")


def still_record(still_id, stills_dir=None):
    """A scene still's record (bible/stills/<id>.json), or None."""
    if not isinstance(still_id, str) or not STILL_ID.fullmatch(still_id) or len(still_id) > STILL_ID_MAX:
        return None
    path = Path(stills_dir or STILLS_DIR) / f"{still_id}.json"
    return json.loads(path.read_text()) if path.is_file() else None


def still_prompt_problems(label, prompt, plan):
    """A still's own prompt under the scene rules (E108 period, E110 writing, E113 ark): what a frame shows is what
    Pavo animates, so the still states the period and the ark's look word for word like any scene prompt. A still of a
    Keeper shot (the owner's arc-01 exception, plan B) is judged as the Keeper's own prompt is: he sits outside the
    story's time, at his campfire (prompt_problems), never under the scene's period."""
    sid = str(label).partition("/")[0]
    if isinstance(plan, dict) and any(s.get("id") == sid and s.get("kind") == "keeper" for s in plan.get("shots") or []):
        return [p for p in prompt_problems(0, {"id": label, "prompt": prompt})
                if not p.startswith("PROMPT_NO_CINEMATOGRAPHY")]   # a still has a framing, not a camera move
    pseudo = {"kind": "scene", "id": label, "prompt": prompt}
    found = []
    per, problem = resolve_period(plan)
    if problem:
        found.append(problem)
    else:
        found += period_problems(0, pseudo, per)
    found += writing_problems(0, pseudo) + prop_problems(0, pseudo, per, plan if isinstance(plan, dict) else {})
    return found


def prop_references(prompt, props=None, plan=None):
    """E122: (the approved reference images a still must be made with, the problems). A prompt that names a prop
    (PROPS `mentions`, anywhere: the flood's setting sentence names "the great wooden ark", and Pavo draws it) needs
    every approved reference of that prop (props.json, props.py); a prop not APPROVED yet is a problem. Text alone did
    not hold the ark's shape (genesis-09: a tower, a barn, a ship's bow under the same two sentences)."""
    refs, out = [], []
    for name, spec in PROPS.items():
        # E123: the phrase is the ark (from part 9 nothing else may name it: with a plan past part 8 only the phrase
        # counts, so Jonah's ship takes no ark reference); E113's names still count for parts 1-8 and without a plan
        phrase_only = plan is not None and not ark_e113(plan)
        if not has_phrase(prompt, spec["phrase"]) and (phrase_only or not isinstance(prompt, str) or not any(
                re.search(rf"(?i)\b(?:{a})\b", prompt) for a in spec["mentions"])):
            continue
        got, why = prop_refs.approved_refs(name, props)
        if why:
            out.append(f"names the {name}: {why}")
        refs += got
    return refs, out


def reference_digest(references):
    """E122: the digest an approval binds a still's references with (record and sha256 of each, in order)."""
    rows = [{"record": r.get("record"), "sha256": r.get("sha256")} for r in references or [] if isinstance(r, dict)]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


PAVO_IMAGE_MODEL = "agnes-image"


def pavo_proof_problems(pavo, count):
    """E122: the Pavo read-back that proves COUNT reference images went with the still: the generate call's own
    answer (model agnes-image, conversation_id, input_images == COUNT) and the job read back by pavo_image_job (the
    same conversation_id, status completed). A sidecar that only declares `references` proves nothing."""
    g = (pavo or {}).get("generate") or {}
    j = (pavo or {}).get("job") or {}
    if g.get("model") != PAVO_IMAGE_MODEL or not g.get("conversation_id") or g.get("input_images") != count \
            or j.get("conversation_id") != g.get("conversation_id") or j.get("status") != "completed":
        return [f"no Pavo read-back proving {count} reference image(s) were sent (pavo.generate: model "
                f"{PAVO_IMAGE_MODEL}, conversation_id, input_images {count}; pavo.job: the same conversation_id, "
                f"status completed); got generate {g.get('model')}/{g.get('input_images')}, job {j.get('status')}"]
    return []


def prop_reference_problems(prompt, references, props=None, pavo=None, plan=None):
    """E122: what keeps a still (its prompt, the references it was made with: [{record, sha256}], the Pavo read-back)
    from showing a prop's one look: the prop is not APPROVED, the references are not exactly its approved ones (by
    sha256), or Pavo's own answer does not show that many input images. [] when it names none."""
    need, out = prop_references(prompt, props, plan)
    if out or not need:
        return out
    sent = [r.get("sha256") for r in references or [] if isinstance(r, dict)]
    if sorted(sent) != sorted(r["sha256"] for r in need):
        out.append(f"made without exactly the approved reference images {[r['record'] for r in need]} "
                   f"(sent {sorted(x for x in sent if x)})")
        return out
    return pavo_proof_problems(pavo, len(need))


# E237 (owner 31/10, "utilizar a pública"): a scene still may be a public-domain or openly licensed picture
# (public_sources.py). Pages, files and the APIs read for the licence are https on these hosts only.
PUBLIC_PAGE_HOSTS = frozenset({"commons.wikimedia.org", "www.metmuseum.org", "www.loc.gov", "www.nga.gov",
                               "www.rijksmuseum.nl"})
PUBLIC_FILE_HOSTS = frozenset({"upload.wikimedia.org", "images.metmuseum.org", "tile.loc.gov", "api.nga.gov",
                               "media.nga.gov", "iiif.micr.io"})
PUBLIC_API_HOSTS = frozenset({"commons.wikimedia.org", "collectionapi.metmuseum.org", "www.loc.gov", "api.nga.gov",
                              "data.rijksmuseum.nl"})
PUBLIC_LICENCE = re.compile(r"^(Public Domain|CC0|CC-BY-[0-9]\.[0-9]|CC-BY-SA-[0-9]\.[0-9])$")
# what the reviewer checks at full resolution before a public still is approved
PUBLIC_REVIEW_CHECKS = ("period", "writing", "god", "characters")
# the crop's long side: a FLUX still's own (1024), so a public still is never upscaled further than a generated one
PUBLIC_CROP_LONG_MIN = 1024


def normalize_licence(machine, short=""):
    """A licence as published (Commons extmetadata `License` / `LicenseShortName`) -> Public Domain, CC0, CC-BY-x or
    CC-BY-SA-x, or None (NC, ND, GFDL-only, unknown: refused)."""
    for raw in (machine, short):
        t = re.sub(r"[\s_]+", "-", str(raw or "").strip().lower())
        if not t:
            continue
        if re.search(r"(^|-)(nc|nd)(-|$)", t):
            return None
        if t in ("pd", "public-domain") or t.startswith("pd-") or t.startswith("public-domain"):
            return "Public Domain"
        if t in ("cc0", "cc-zero", "cc0-1.0", "cc-0"):
            return "CC0"
        m = re.fullmatch(r"cc-by(-sa)?-([0-9]\.[0-9])", t)
        if m:
            return f"CC-BY{'-SA' if m.group(1) else ''}-{m.group(2)}"
    return None


def public_problems(public, aspect="9:16"):
    """E237: what keeps a public picture's record from carrying a still: hosts, licence (allowlist), attribution for
    CC-BY / CC-BY-SA, the exact bytes' sha256, the original's size and a crop inside it at ASPECT and resolution."""
    p = public if isinstance(public, dict) else {}
    out = []
    import urllib.parse
    for key, hosts in (("source_page", PUBLIC_PAGE_HOSTS), ("file_url", PUBLIC_FILE_HOSTS)):
        u = urllib.parse.urlsplit(str(p.get(key) or ""))
        if u.scheme != "https" or (u.hostname or "") not in hosts:
            out.append(f"PUBLIC_HOST_REFUSED {key} {p.get(key)!r} (https on {sorted(hosts)})")
    lic = p.get("licence")
    if not isinstance(lic, str) or not PUBLIC_LICENCE.fullmatch(lic):
        out.append(f"PUBLIC_LICENCE_REFUSED {lic!r} (Public Domain, CC0, CC-BY or CC-BY-SA; never NC, ND or unknown)")
    elif lic.startswith("CC-BY") and not (isinstance(p.get("attribution"), str) and p.get("author")
                                          and str(p["author"]) in p["attribution"] and lic in p["attribution"]):
        out.append(f"PUBLIC_ATTRIBUTION_MISSING {lic} (its attribution names the author and the licence)")
    if p.get("licence_source") not in ("commons-extmetadata", "met-collectionapi") or not p.get("author") \
            or not p.get("retrieved_at"):
        out.append("PUBLIC_RECORD_INCOMPLETE (licence_source read from the source's API, author, retrieved_at)")
    if not re.fullmatch(r"[0-9a-f]{64}", str(p.get("sha256") or "")):
        out.append("PUBLIC_RECORD_INCOMPLETE (the downloaded bytes' sha256)")
    dims, box = p.get("dimensions"), p.get("crop")
    ints = lambda v, n: isinstance(v, list) and len(v) == n and all(  # noqa: E731
        isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in v)
    if not ints(dims, 2) or not ints(box, 4) or box[2] <= 0 or box[3] <= 0 \
            or box[0] + box[2] > dims[0] or box[1] + box[3] > dims[1]:
        out.append(f"PUBLIC_CROP_INVALID {box} (a box [x, y, w, h] inside the original {dims})")
    else:
        aw, ah = (int(v) for v in aspect.split(":"))
        if abs(box[2] / box[3] - aw / ah) > 0.01:
            out.append(f"STILL_ASPECT_MISMATCH crop {box} is not {aspect}")
        if max(box[2], box[3]) < PUBLIC_CROP_LONG_MIN:
            out.append(f"PUBLIC_RESOLUTION_LOW crop {box[2]}x{box[3]} (long side >= {PUBLIC_CROP_LONG_MIN})")
    return out


def public_review_problems(review):
    """E237: the reviewer's full-resolution review of a public still names every check and what it saw."""
    r = review if isinstance(review, dict) else {}
    out = []
    missing = [c for c in PUBLIC_REVIEW_CHECKS if c not in (r.get("checked") or [])]
    if missing:
        out.append(f"PUBLIC_REVIEW_INCOMPLETE {missing} (period accuracy; no legible writing, watermark or signature "
                   "text; God never a figure; characters consistent or anonymous)")
    if not isinstance(r.get("note"), str) or not r["note"].strip():
        out.append("PUBLIC_REVIEW_NOTE_MISSING (what the full-resolution review saw)")
    if not re.fullmatch(r"[0-9a-f]{64}", str(r.get("reviewed_sha256") or "")):
        out.append("PUBLIC_REVIEW_INCOMPLETE (the sha256 of the image reviewed)")
    return out


def public_still_problems(rec, aspect="9:16"):
    """E237: an APPROVED public still: its record and its review, the review of exactly the approved image."""
    approved = (rec or {}).get("approved") or {}
    out = public_problems(rec.get("public"), aspect) + public_review_problems(approved.get("review"))
    if (approved.get("review") or {}).get("reviewed_sha256") != rec.get("sha256"):
        out.append("PUBLIC_REVIEW_INCOMPLETE (the review is not of the approved image)")
    return out


def _image_size(path):
    """(width, height) of a PNG or JPEG, read from its header (no imaging library at plan time)."""
    data = Path(path).read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    i = 2
    while data[:2] == b"\xff\xd8" and i + 9 < len(data):
        if data[i] != 0xFF:
            break
        marker, size = data[i + 1], int.from_bytes(data[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
        i += 2 + size
    return None


def frame_problems(i, shot, plan, stills_dir=None):
    """Image first (owner, 27/10): a scene shot's `first_frame` / `last_frame` name APPROVED scene stills whose image
    is the approved one, at the plan's aspect, and whose prompt passes the scene rules. Shared by plan_check (and the
    preflight, which runs it) and episode_build.request (frame_refusal)."""
    given = [f for f in FRAME_FIELDS if f in shot]
    if not given:
        return []
    sid, out = shot.get("id"), []
    if shot.get("kind") != "scene":
        out.append(f"FRAMES_NOT_SCENE shot {i} {sid} (a still is the first frame of a scene shot, never the Keeper's)")
    bad = [f for f in given if not isinstance(shot[f], str) or not STILL_ID.fullmatch(shot[f])
           or len(shot[f]) > STILL_ID_MAX]
    if bad:
        out.append(f"FRAME_FIELD_INVALID shot {i} {sid} ({', '.join(bad)}: a scene still id, a-z 0-9 -)")
    if "last_frame" in shot and "first_frame" not in shot:
        out.append(f"FRAME_LAST_WITHOUT_FIRST shot {i} {sid} (a last frame needs a first frame, as Pavo does)")
    if shot.get("characters"):
        out.append(f"FRAMES_WITH_REFERENCES shot {i} {sid} (Pavo takes frames or character references, never both: "
                   "a still-first shot shows no approved character)")
    if talking(shot):
        out.append(f"FRAMES_WITH_AUDIO shot {i} {sid} (Pavo's frames_to_video takes no input audio: a talking shot "
                   "is generated from references)")
    if out:
        return out
    aspect = plan.get("aspect_ratio", "9:16")
    for f in given:
        still = shot[f]
        rec = still_record(still, stills_dir)
        if rec is None:
            out.append(f"STILL_MISSING shot {i} {sid} ({f} {still}: no bible/stills/{still}.json; write its prompt, "
                       "then scene-stills.yml)")
            continue
        if isinstance(rec.get("prompt"), str):
            out += [f"STILL_PROMPT_REFUSED shot {i} {sid} ({f} {still}: {p})"
                    for p in still_prompt_problems(f"{sid}/{still}", rec["prompt"], plan)]
        else:
            out.append(f"STILL_PROMPT_REFUSED shot {i} {sid} ({f} {still}: no prompt in its record)")
        if rec.get("status") != "APPROVED":
            out.append(f"STILL_NOT_APPROVED shot {i} {sid} ({f} {still} is {rec.get('status')}: Claude reviews its "
                       "candidates and approves one with scene_stills.py approve, by PR)")
            continue
        if not reviewer_identity.valid(rec.get("approved") or {}):
            out.append(f"STILL_NOT_APPROVED shot {i} {sid} ({f} {still}: unknown reviewer identity)")
        src = (ROOT / str(rec.get("repo_path") or "")).resolve()
        if not rec.get("repo_path") or ROOT.resolve() not in src.parents or not src.is_file() \
                or src.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            out.append(f"STILL_PATH_REFUSED shot {i} {sid} ({f} {still}: a PNG/JPEG inside the repository)")
            continue
        if "public" in rec:   # E237: a public picture keeps its licence, attribution and full review
            out += [f"STILL_PUBLIC_REFUSED shot {i} {sid} ({f} {still}: {p})"
                    for p in public_still_problems(rec, aspect)]
        out += [f"STILL_PROP_UNREFERENCED shot {i} {sid} ({f} {still}: {p}; E122)"
                for p in prop_reference_problems(rec.get("prompt"), rec.get("references"), pavo=rec.get("pavo"),
                                                 plan=plan)]
        if (rec.get("approved") or {}).get("references_sha256") != reference_digest(rec.get("references")):
            out.append(f"STILL_PROMPT_CHANGED shot {i} {sid} ({f} {still}: its references are not the ones its image "
                       "was approved with; E122)")
        if hashlib.sha256(src.read_bytes()).hexdigest() != rec.get("sha256"):
            out.append(f"STILL_SHA256_MISMATCH shot {i} {sid} ({f} {still}: the image is not the one approved)")
        approved = rec.get("approved") or {}
        if not isinstance(rec.get("prompt"), str) or \
                hashlib.sha256(rec["prompt"].encode()).hexdigest() != approved.get("prompt_sha256"):
            out.append(f"STILL_PROMPT_CHANGED shot {i} {sid} ({f} {still}: its prompt is not the one its image was "
                       "approved with)")
        size = _image_size(src)
        w, h = (int(x) for x in aspect.split(":"))
        if not size or abs(size[0] / size[1] - w / h) > 0.01:
            out.append(f"STILL_ASPECT_MISMATCH shot {i} {sid} ({f} {still}: {size} is not {aspect})")
    return out


def frame_paths(shot, stills_dir=None):
    """(first, last) repository paths of a shot's approved stills ("" when it has none): what the request sends."""
    out = []
    for f in FRAME_FIELDS:
        rec = still_record(shot.get(f), stills_dir) if shot.get(f) else None
        out.append(rec["repo_path"] if rec and rec.get("repo_path") else "")
    return tuple(out)


def _speaker_problems(i, s, chars, span, span_slowest):
    """A speaking scene: who speaks, in which voice, and how long the line is."""
    out, sid, who = [], s["id"], s["speaker"]
    if not isinstance(s.get("line"), str) or not s["line"].strip():
        return [f"SPEAKER_LINE_MISSING shot {i} {sid}"]
    if span_slowest > TALK_LINE_MAX:
        out.append(f"SPEAKER_LINE_TOO_LONG shot {i} {sid} (~{span_slowest:.1f} s at the slowest pace; <= {TALK_LINE_MAX:.2f} s: "
                   "the line and Pavo's 0.45 s fit one 12 s clip, E95)")
    low = SPEAKER_AUDIO[0] if who == ch.GOD else TALK_MIN
    if span < low:
        out.append(f"SPEAKER_LINE_TOO_SHORT shot {i} {sid} (>= {low:.2f} s{'' if who == ch.GOD else ': a talking line fills a 4 s clip, E95'})")
    if who == ch.NARRATOR:
        return out + [f"SPEAKER_KEEPER shot {i} {sid} (the Keeper speaks only in his own shots, at the close)"]
    if who == ch.GOD:
        if not s.get("reference"):
            out.append(f"GOD_LINE_NOT_SCRIPTURE shot {i} {sid} (God says only the KJV words, with a reference)")
        prompt = NO_PEOPLE_TAIL.sub("", s.get("prompt", ""))
        if s.get("characters") or s.get("figures") or GOD_SHOT_PERSON.search(prompt):
            out.append(f"GOD_SHOT_WITH_A_PERSON shot {i} {sid} (God speaks over light, storm, wind or fire; no one "
                       "on screen)")
        if not GOD_SHOT_MEDIUM.search(prompt):
            out.append(f"GOD_SHOT_NO_MEDIUM shot {i} {sid} (light, storm, wind or fire carries His voice)")
        return out
    c = chars.get(who) if isinstance(who, str) else None
    if not c:
        return out + [f"SPEAKER_UNKNOWN shot {i} {sid}: {who} (an APPROVED characters.json id, or god)"]
    if c.get("status") != "APPROVED":
        out.append(f"SPEAKER_NOT_APPROVED shot {i} {sid}: {who} ({c.get('status')})")
    if not ch.voice(who, chars):
        out.append(f"SPEAKER_NO_VOICE shot {i} {sid}: {who} (characters.json `voice`)")
    elif who not in VOICE_PACE:
        out.append(f"VOICE_PACE_UNMEASURED shot {i} {sid}: {who} (measure its Kokoro voice into voice_pace.py before "
                   "its first talking line)")
    if who not in (s.get("characters") or []):
        out.append(f"SPEAKER_NOT_IN_SHOT shot {i} {sid}: {who} (in `characters`, its look in the prompt)")
    if s.get("seconds") is not None:
        out.append(f"SPEAKER_SHOT_FIELDS shot {i} {sid} (the clip's length comes from the line)")
    if not SPEAKS.search(s.get("prompt", "")):
        out.append(f"SPEAKER_NOT_SPEAKING shot {i} {sid} (say that {who} speaks, lips moving with every word)")
    return out


def check(plan, chars=None):
    """{"problems": [...], "pending": [...], "estimate": {...}} for a plan."""
    chars = chars if chars is not None else ch.registry()
    import shot_sources
    problems, pending = shot_sources.source_policy_problems(plan), []
    if plan.get("version") != VERSION:
        problems.append(f"PLAN_VERSION (need {VERSION})")
    if not isinstance(plan.get("episode"), str) or not EPISODE_ID.fullmatch(plan["episode"]):
        problems.append("EPISODE_ID")
    if type(plan.get("part")) is not int or plan["part"] < 1:
        problems.append("PART")
    if plan.get("aspect_ratio", "9:16") not in RATIOS:
        problems.append("ASPECT_RATIO (Shorts are 9:16)")
    narration = plan.get("narration")
    if not isinstance(narration, list) or not narration:
        return {"problems": problems + ["NARRATION_MISSING"], "pending": pending, "estimate": {}}
    problems += narration_problems(narration)
    if problems and any(p.startswith("NARRATION_LINE") for p in problems):
        return {"problems": problems, "pending": pending, "estimate": {}}

    n = len(narration)
    shots = plan.get("shots")
    if not isinstance(shots, list) or not shots:
        return {"problems": problems + ["SHOTS_MISSING"], "pending": pending, "estimate": {}}
    shape, bad_lines = shot_shape_problems(shots, n)
    problems += shape
    if bad_lines:
        return {"problems": problems, "pending": pending, "estimate": {}}
    problems += audio_route_problems(plan, shots)
    return _check_shots(plan, chars, narration, shots, problems, pending)


def audio_route_problems(plan, shots):
    """A Short's effective audio route must remain Kokoro until native speech has a Short criteria contract.
    E153: the engine can inherit native speech from criteria, not only an explicit audio_route flag."""
    import pavo_native as pn
    route = plan.get("audio_route")
    if route not in (None, pn.KOKORO, pn.NATIVE):
        return [f"AUDIO_ROUTE_UNKNOWN {route!r} ({pn.KOKORO} or {pn.NATIVE})"]
    if not pn.native_plan(plan):
        return []
    # review of #476: refused for a Short until a Short criteria file with the speech-check rows exists (a new
    # frozen file, owner); the engine path is the long's (story QA v4)
    return ["AUDIO_ROUTE_SHORT_UNSUPPORTED (Pavo's own speech needs a frozen Short criteria file with the speech "
            "checks; the long has story QA v4)"]


def narration_problems(narration, kinds=KINDS):
    """Each narration line: a known kind and text; Scripture with its reference, the KJV word for word; no unreferenced
    KJV quotation (shared with long_plan_check, the long's plan)."""
    problems = []
    for k, line in enumerate(narration):
        if not isinstance(line, dict) or line.get("kind") not in kinds or not str(line.get("text", "")).strip():
            problems.append(f"NARRATION_LINE {k} (kind {'/'.join(kinds)} and text)")
            continue
        if line.get("reference") is not None and not isinstance(line["reference"], str):
            problems.append(f"REFERENCE_NOT_TEXT line {k} (a reference such as \"Genesis 6:5 (KJV)\")")
            continue
        if line["kind"] == "scripture":
            if not line.get("reference"):
                problems.append(f"SCRIPTURE_REFERENCE_MISSING line {k}")
            else:
                bad = _kjv_problem(line["reference"], line["text"])
                if bad:
                    problems.append(f"KJV line {k}: {bad}")
        else:
            quoted = kjv_quote(line["text"])
            if quoted:
                problems.append(f"KJV_UNREFERENCED line {k} (quotes {quoted[0]}: \"{quoted[1]}\"; make it kind "
                                "scripture with its reference, KJV word for word)")
    return problems


def shot_shape_problems(shots, n):
    """(problems, bad_lines): each shot a keeper or scene with a unique id; a speaking scene carries its own line (KJV
    word for word when it has a reference), every other shot consecutive narration indices (shared with
    long_plan_check). bad_lines: the voice track cannot be laid out, so nothing after this is checked."""
    problems = []
    seen, bad_lines = set(), False
    for i, s in enumerate(shots):
        if not isinstance(s, dict) or s.get("kind") not in ("keeper", "scene"):
            problems.append(f"SHOT_KIND shot {i} (keeper or scene)")
            bad_lines = True
            continue
        if not isinstance(s.get("id"), str) or not SHOT_ID.fullmatch(s["id"]) or s["id"] in seen:
            problems.append(f"SHOT_ID shot {i} (unique, a-z 0-9 -)")
        seen.add(s.get("id"))
        if "voiceover" in s and (s["kind"] != "keeper" or type(s["voiceover"]) is not bool):
            problems.append(f"VOICEOVER_FIELD shot {i} {s.get('id')} (`voiceover`: true or false, on a keeper shot "
                            "only)")
        if speaking(s):
            if s["kind"] != "scene" or s.get("lines") not in (None, []):
                problems.append(f"SPEAKER_SHOT_KIND shot {i} {s.get('id')} (a scene that carries its own `line`, "
                                "no narration lines)")
                bad_lines = True
            elif not isinstance(s.get("line"), str) or not s["line"].strip():
                problems.append(f"SPEAKER_LINE_MISSING shot {i} {s.get('id')}")
                bad_lines = True
            elif s.get("reference") is not None and not isinstance(s["reference"], str):
                problems.append(f"REFERENCE_NOT_TEXT shot {i} {s.get('id')} (a reference such as \"Genesis 6:13 "
                                "(KJV)\")")
                bad_lines = True
            elif s.get("reference"):
                bad = _kjv_problem(s["reference"], s["line"])
                if bad:
                    problems.append(f"KJV shot {i} {s['id']}: {bad}")
            else:
                quoted = kjv_quote(s["line"])
                if quoted:
                    problems.append(f"KJV_UNREFERENCED shot {i} {s['id']} (the line quotes {quoted[0]}: "
                                    f"\"{quoted[1]}\"; give it its `reference`, KJV word for word)")
            continue
        lp = _lines_problem(i, s, n)
        if lp:
            problems.append(lp)
            bad_lines = True
    return problems, bad_lines


def keeper_prompt_problems(i, s, keeper):
    """A Keeper shot's prompt: his look and one wardrobe variant word for word, he speaks, and he faces the lens on a
    static camera (E98) (shared with long_plan_check)."""
    problems = []
    if keeper["look"] not in s.get("prompt", ""):
        problems.append(f"CHARACTER_LOOK_CHANGED shot {i}: keeper (the prompt must carry its look word for word)")
    if not any(w in s.get("prompt", "") for w in keeper.get("wardrobe", {}).values()):
        problems.append(f"KEEPER_WARDROBE shot {i} {s['id']} (one wardrobe variant word for word: same room)")
    if voiceover(s):
        return problems + vo_prompt_problems(i, s)
    if not SPEAKS.search(s.get("prompt", "")):
        problems.append(f"KEEPER_NOT_SPEAKING shot {i} {s['id']} (say that he speaks to the camera)")
    prompt_lc = s.get("prompt", "").lower()
    if not all(w in prompt_lc for w in KEEPER_POSE) or KEEPER_POSE_OFF.search(prompt_lc):
        problems.append(f"KEEPER_POSE shot {i} {s['id']} (a talking Keeper faces the lens on a static camera: "
                        f"{' and '.join(repr(w) for w in KEEPER_POSE)}, no push-in, pull-back, tracking, orbit, lean or bow; those "
                        "lost the face or the lips, E98)")
    return problems


def vo_prompt_problems(i, s):
    """Plan B: a voice-over Keeper's prompt says his lips stay closed ("his lips closed, silent") and names no speech
    (speaks, talking, says, lips moving...), so Pavo makes no talking mouth under a line he does not lip-sync; and he
    faces the lens on a static camera (KEEPER_POSE words, no look down into the fire), so the still-mouth check finds
    his face."""
    p = s.get("prompt", "")
    out, speech = [], VO_SPEECH.search(p)
    if not all(r.search(p) for r in VO_SILENT) or speech:
        why = f"names speech: {speech.group(0)!r}" if speech else "say \"his lips closed, silent\""
        out.append(f"KEEPER_VO_PROMPT shot {i} {s['id']} (a voice-over Keeper is silent on screen, mouth closed; {why})")
    low, off = p.lower(), VO_GAZE_OFF.search(p) or KEEPER_POSE_OFF.search(p.lower())
    if not all(w in low for w in KEEPER_POSE) or off:
        why = f"not {off.group(0)!r}" if off else " and ".join(repr(w) for w in KEEPER_POSE)
        out.append(f"KEEPER_VO_POSE shot {i} {s['id']} (he faces the lens on a static camera so the still-mouth check "
                   f"finds his face; {why})")
    return out


def talk_reach_problems(i, s, span, slowest, gaps):
    """review of #408/#412: between a 4 s and a 5 s clip (one line: 3.94-4.14 s) the 10 % retime reaches neither, so
    episode_build lines would refuse it (TALK_LINE_RETIME_OVER) after the plan had passed; judged at every pace from
    the normal to the slowest, since the build retimes the measured length (shared with long_plan_check)."""
    if talking(s) and talk_min(gaps) <= span and slowest <= TALK_LINE_MAX:
        miss = talk_reach_gap(span - gaps, slowest - gaps, gaps)
        if miss is not None:
            return [f"TALK_LINE_UNREACHABLE shot {i} {s['id']} (~{span:.2f}-{slowest:.2f} s from the "
                    f"normal to the slowest pace: at ~{miss + gaps:.2f} s no {TALK_CLIP[0]}-{TALK_CLIP[1]} s "
                    f"clip is within +-{TALK_RETIME_MAX:.0%} of its words; a few words more or fewer)"]
    return []


def lines_order_problems(shots, n):
    """The narration lines carried in order, each once, every one of them; a keeper shot speaks its own lines (shared
    with long_plan_check)."""
    problems, expect = [], 0
    for a, b, lines in groups(shots):
        if lines is None:
            continue
        if lines[0] != expect:
            problems.append(f"LINES_OUT_OF_ORDER shot {a} {shots[a]['id']} (next line is {expect})")
        expect = lines[-1] + 1
        if b > a and any(shots[j]["kind"] == "keeper" for j in range(a, b + 1)):
            problems.append(f"KEEPER_LINES_SHARED shot {a} {shots[a]['id']} (a keeper shot speaks its own lines)")
    if expect != n:
        problems.append(f"LINES_NOT_CARRIED from line {expect}")
    return problems


def character_problems(i, cids, prompt, chars, drafts=None):
    """Each character a characters.json entry with a `look`, APPROVED, its look word for word in the prompt (the same
    rules and words as characters.problems). drafts: a set that collects DRAFT ids as pending rows (the long), and
    then an APPROVED character with no kept references is CHARACTER_NO_REFS; without it a DRAFT one is
    CHARACTER_NOT_APPROVED (the Short). Shared with long_plan_check."""
    out = []
    for cid in cids:
        if cid == ch.NARRATOR:
            continue
        c = chars.get(cid)
        if not c:
            out.append(f"CHARACTER_UNKNOWN shot {i}: {cid} (add it to characters.json first)")
        elif not isinstance(c.get("look"), str) or not c["look"].strip():
            out.append(f"CHARACTER_NO_LOOK shot {i}: {cid} (characters.json `look`: the fixed words every prompt "
                       "carries)")
        elif c.get("status") == "APPROVED" or (drafts is not None and c.get("status") == "DRAFT"):
            if c["look"] not in prompt:
                out.append(f"CHARACTER_LOOK_CHANGED shot {i}: {cid} (the prompt must carry its look word for word)")
            elif c.get("status") == "DRAFT":
                drafts.add(cid)
            elif drafts is not None and not c.get("refs"):
                out.append(f"CHARACTER_NO_REFS shot {i}: {cid} (APPROVED with no kept reference image: the same face "
                           "cannot go in; keep its reviewed refs)")
        else:
            out.append(f"CHARACTER_NOT_APPROVED shot {i}: {cid} ({c.get('status')}; review its reference sheet)")
    return out


def scene_seconds_problems(i, s):
    """A scene clip (not a talking one) is 4-12 s of Pavo video."""
    if type(s.get("seconds")) is not int or not SCENE_SECONDS[0] <= s["seconds"] <= SCENE_SECONDS[1]:
        return [f"SCENE_SECONDS shot {i} {s['id']} (4-12)"]
    return []


def figures_problems(i, s, cids):
    """A scene with no character: anonymous figures seen from behind or in silhouette, or an establishing shot; an
    establishing shot shows no character (shared with long_plan_check)."""
    if cids:
        return [f"ESTABLISHING_WITH_CHARACTERS shot {i} {s['id']}"] if s.get("establishing") else []
    if s.get("establishing") is True:
        return []
    if s.get("figures") == "anonymous":
        if not ANONYMOUS.search(s.get("prompt", "")):
            return [f"FIGURES_NOT_ANONYMOUS shot {i} {s['id']} (seen from behind or in silhouette)"]
        return []
    return [f"SCENE_WITHOUT_CHARACTERS shot {i} {s['id']} (act it out with the bible's people, anonymous figures from "
            "behind, or mark an establishing shot)"]


def establishing_only(members, span, hold_cap=ESTABLISHING_HOLD):
    """Words carried by establishing shots alone, longer than they may hold (the Short: 2 s each; the long, whose
    holds are 4-7 s: any words at all, hold_cap 0)."""
    return all(m.get("establishing") for m in members) and span > hold_cap * len(members) + 0.5


def _check_shots(plan, chars, narration, shots, problems, pending):
    problems += lines_order_problems(shots, len(narration))

    items, carried = sequence(plan)
    est = [words(x["text"]) / pace(x) for x in items]
    total = sum(est) + LINE_GAP * (len(items) - 1) + TAIL
    # a line that quotes the KJV is Scripture for the >= 40 % share of our own words, whatever its kind says
    problems += [f"SHORT {p}" for p in publish_episode.short_problems(
        {"format": "short", "part": plan.get("part", 0), "seconds": round(total, 1),
         "narration": [{"kind": "scripture" if x["kind"] != "scripture" and kjv_quote(x["text"]) else x["kind"],
                        "text": x["text"]} for x in items]})]

    # the open: a spoken line from 0 s, never the Keeper
    if shots[0]["kind"] == "keeper":
        problems.append("KEEPER_OPENS (the first shot is a scene: the conflict spoken by a character or God's voice)")
    elif not speaking(shots[0]):
        problems.append("OPEN_NOT_SPOKEN (the first shot carries a spoken line from 0 s: a character's challenge or "
                        "plea, or God's voice)")
    if shots[-1]["kind"] != "keeper":
        problems.append("KEEPER_MUST_CLOSE (the last shot is the Keeper)")
    climax = [i for i, s in enumerate(shots) if s.get("climax") is True]
    if not climax:
        problems.append("CLIMAX_MISSING (flag the acted antagonist or spectacle moment `climax: true`)")
    for i in climax:
        s = shots[i]
        people = bool(s.get("characters")) or s.get("figures") == "anonymous"
        god_voice = speaking(s) and s["speaker"] == ch.GOD
        if s["kind"] != "scene" or s.get("establishing") or god_voice or not people:
            problems.append(f"CLIMAX_NOT_ACTED shot {i} {s['id']} (the climax is acted: approved characters or "
                            "anonymous figures on screen; not the Keeper, a landscape or God's voice-over sky; E92)")
    last_climax = max(climax) if climax else len(shots)

    keeper = chars.get(ch.NARRATOR)
    keeper_seconds, establishing_seconds, keeper_used = 0.0, 0.0, False
    lesson = set()
    first_prompt = {}
    problems += plan_period_problems(plan, shots)
    problems += plan_writing_problems(shots)
    problems += plan_prop_problems(plan, shots)
    for i, s in enumerate(shots):
        problems += prompt_problems(i, s)
        problems += frame_problems(i, s, plan)
        # E106 (owner: "production has to come out at 9.5 already"): the review's pacing_and_visual_variety item,
        # made a plan rule: one prompt is one picture, so the same prompt twice shows the same shot twice
        if isinstance(s.get("prompt"), str):
            if s["prompt"] in first_prompt:
                problems.append(f"PROMPT_REPEATED shot {i} {s['id']} (the same prompt as {first_prompt[s['prompt']]}: "
                                "the same picture twice; change the shot size, the action or the angle)")
            first_prompt.setdefault(s["prompt"], s["id"])
        idx = carried[i]
        gaps = LINE_GAP * (len(idx) - 1)
        span = sum(est[k] for k in idx) + gaps
        slowest = sum(words(items[k]["text"]) / slowest_pace(items[k]) for k in idx) + gaps
        problems += talk_reach_problems(i, s, span, slowest, gaps)
        if s["kind"] == "keeper":
            keeper_used = True
            keeper_seconds += span
            lesson.update(idx)
            if i < last_climax:
                problems.append(f"KEEPER_BEFORE_CLIMAX shot {i} {s['id']} (the Keeper comes only after the climax)")
            if any(items[k]["kind"] not in LESSON_KINDS for k in idx):
                problems.append(f"KEEPER_LINE_KIND shot {i} {s['id']} (the Keeper speaks only the insight and the "
                                "close)")
            if voiceover(s):
                covered = vo_covered(slowest, shots, i)
                if covered > VO_LINE_MAX + 1e-9:
                    problems.append(f"KEEPER_LINE_TOO_LONG shot {i} {s['id']} (~{covered:.1f} s with the gap before and "
                                    f"the gap or tail after, at the slowest pace; one {TALK_CLIP[1]} s clip slowed at "
                                    f"most {MAX_SLOW} covers {VO_LINE_MAX:.1f} s)")
                if span < VO_LINE_MIN:
                    problems.append(f"KEEPER_LINE_TOO_SHORT shot {i} {s['id']} (~{span:.1f} s; a Keeper line is at least "
                                    f"{VO_LINE_MIN:.1f} s, as episode_build lines holds it)")
                if keeper and not keeper.get("talk_refs"):
                    problems.append(f"KEEPER_VO_NO_TALK_REF shot {i} {s['id']} (a voice-over Keeper is generated from his "
                                    "`talk_refs` frame; the front view lost his face 4 of 4, keeper-vo/calibration.json)")
            elif slowest > TALK_LINE_MAX:
                problems.append(f"KEEPER_LINE_TOO_LONG shot {i} {s['id']} (~{slowest:.1f} s at the slowest pace; "
                                f"Pavo input audio <= {TALK_LINE_MAX:.2f} s)")
            if not voiceover(s) and span < talk_min(gaps):
                problems.append(f"KEEPER_LINE_TOO_SHORT shot {i} {s['id']} (input audio >= {talk_min(gaps):.2f} s: it "
                                "fills a 4 s clip, its gaps never stretched, E95)")
            if s.get("characters") not in (None, [ch.NARRATOR]) or s.get("seconds") is not None:
                problems.append(f"KEEPER_SHOT_FIELDS shot {i} {s['id']} (characters and seconds come from the line)")
            if not keeper:
                problems.append("CHARACTER_UNKNOWN keeper (characters.json)")
                continue
            problems += keeper_prompt_problems(i, s, keeper)
            continue
        lesson.update(k for k in idx if items[k]["kind"] in LESSON_KINDS)
        cids = s.get("characters", [])
        if not isinstance(cids, list) or not all(isinstance(c, str) for c in cids):
            problems.append(f"SHOT_CHARACTERS shot {i} {s['id']}")
            continue
        if ch.NARRATOR in cids:
            problems.append(f"KEEPER_IN_SCENE shot {i} {s['id']} (the Keeper narrates; he never acts in the story)")
        if speaking(s):
            problems += _speaker_problems(i, s, chars, span, slowest)
        problems += character_problems(i, cids, s.get("prompt", ""), chars)
        refs = sum(len(chars.get(c, {}).get("refs") or []) for c in cids if c != ch.NARRATOR)
        if refs > ch.MAX_REFS:
            problems.append(f"REFERENCES_OVER_{ch.MAX_REFS} shot {i} {s['id']} ({refs} approved images)")
        if talking(s):
            continue   # its clip's length comes from its line
        problems += scene_seconds_problems(i, s)
        if speaking(s):
            continue   # God's voice-over shot: no one on screen (checked above)
        if not cids and s.get("establishing") is True:
            establishing_seconds += ESTABLISHING_HOLD
        problems += figures_problems(i, s, cids)

    # Enough footage for every run of scenes (establishing shots hold 2 s; a clip may be slowed MAX_SLOW at most)
    for a, b, idx in groups(shots, carried):
        if talking(shots[a]) or voiceover(shots[a]):
            continue   # a voice-over Keeper's clip length comes from his line (vo_clip_seconds)
        span = sum(est[k] for k in idx) + LINE_GAP * len(idx)
        members = [shots[j] for j in range(a, b + 1)]
        if establishing_only(members, span):
            problems.append(f"ESTABLISHING_ONLY shot {a} {shots[a]['id']} (~{span:.1f} s of words over landscape)")
        footage = sum(ESTABLISHING_HOLD if m.get("establishing") else m.get("seconds") or 0 for m in members)
        if footage * MAX_SLOW < span:
            problems.append(f"SCENE_FOOTAGE_SHORT shot {a} {shots[a]['id']} ({footage} s of clips for ~{span:.1f} s)")
    share = keeper_seconds / total if total else 0
    if share > KEEPER_SHARE_MAX:
        problems.append(f"KEEPER_SHARE {share:.2f} > {KEEPER_SHARE_MAX} (estimated)")
    lesson_share = (sum(est[k] for k in lesson) + LINE_GAP * max(len(lesson) - 1, 0)) / total if total else 0
    if lesson_share > LESSON_SHARE_MAX:
        problems.append(f"LESSON_SHARE {lesson_share:.2f} > {LESSON_SHARE_MAX} (insight + cta + Keeper, estimated)")
    est_share = establishing_seconds / total if total else 0
    if est_share > ESTABLISHING_SHARE_MAX:
        problems.append(f"ESTABLISHING_SHARE {est_share:.2f} > {ESTABLISHING_SHARE_MAX}")
    if all(p.split()[0] in ("SPEAKER_NOT_APPROVED", "CHARACTER_NOT_APPROVED") for p in problems):
        # E106: the build's own refusals, predicted here (also while a character awaits approval) with the build's
        # own functions: episode_build.predict (retime, talking records, shares, length, compose cuts and holds) on
        # this estimate, and reference_problems (the kept reference records and images, counted as the request
        # sends them). A plan that passes is not refused later by lines, refs or compose for a reason it holds.
        import episode_build
        problems += [f"BUILD {p}" for p in episode_build.predict(plan, est)[0]]
        problems += [f"BUILD {p}" for p in episode_build.reference_problems(plan, chars)]
    if keeper_used and keeper and (keeper.get("status") != "APPROVED" or not keeper.get("refs")):
        pending.append(f"CHARACTER_PENDING keeper ({keeper.get('status')}): Claude reviews his reference sheet and "
                       "sets APPROVED with kept refs, by PR, before episode.yml can generate")
    estimate = {"seconds": round(total, 1), "keeper_share": round(share, 3), "lesson_share": round(lesson_share, 3),
                "establishing_share": round(est_share, 3), "lines": len(items), "shots": len(shots),
                "spoken_lines": sum(1 for x in items if x.get("speaker")),
                "words": sum(words(x["text"]) for x in items)}
    return {"problems": problems, "pending": pending, "estimate": estimate}


def path_problems(path, plan):
    """E106: episode.yml takes a plan only at plans/<episode>.json with that same `episode` (PLAN_PATH_REFUSED,
    PLAN_EPISODE_MISMATCH in its first step); checked here so a plan is never dispatched to be refused there."""
    try:
        name = Path(path).resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        name = str(path)
    m = PLAN_PATH.fullmatch(name)
    if not m:
        return [f"PLAN_PATH {name} (episode.yml takes migration/production/bible/plans/<episode-id>.json)"]
    if plan.get("episode") != m.group(1):
        return [f"PLAN_EPISODE_MISMATCH {name} (`episode` must be {m.group(1)})"]
    return []


def main(argv):
    args = [a for a in argv[1:] if a != "--strict"]
    if len(args) != 1:
        raise SystemExit(__doc__)
    plan = json.loads(Path(args[0]).read_text())
    result = check(plan)
    if "--strict" in argv:   # strict = ready to dispatch: the path episode.yml will take (a draft may live anywhere)
        result["problems"] = path_problems(args[0], plan) + result["problems"]
    print(json.dumps(dict(plan=args[0], **result), indent=1))
    if result["problems"] or ("--strict" in argv and result["pending"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
