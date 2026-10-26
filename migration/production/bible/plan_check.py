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
A character used but not yet APPROVED is a problem; the Keeper while DRAFT is ONE pending row.

usage: plan_check.py PLAN.json [--strict]   prints JSON {problems, pending, estimate}; exit 1 on a problem
                                            (--strict: also on a pending row; episode_build runs it strict)
"""
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
import kjv_check  # noqa: E402
import publish_episode  # noqa: E402
from voice_pace import SHORT_PACE, VOICE_PACE, VOICE_SLOWEST  # noqa: E402  (one measured table, Short and long)

VERSION = "bible-plan-v2"
KINDS = ("story", "scripture", "insight", "cta")
LESSON_KINDS = ("insight", "cta")
EPISODE_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SHOT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
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


def talking(shot):
    """A shot whose clip carries its own words with the speaker's lips on them (Pavo input audio, lipsync_check):
    the Keeper, or a scene where a character speaks. God's line is a voice-over: not a talking clip."""
    return shot["kind"] == "keeper" or (speaking(shot) and shot["speaker"] != ch.GOD)


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
    problems, pending = [], []
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
    return _check_shots(plan, chars, narration, shots, problems, pending)


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
    if not SPEAKS.search(s.get("prompt", "")):
        problems.append(f"KEEPER_NOT_SPEAKING shot {i} {s['id']} (say that he speaks to the camera)")
    prompt_lc = s.get("prompt", "").lower()
    if not all(w in prompt_lc for w in KEEPER_POSE) or KEEPER_POSE_OFF.search(prompt_lc):
        problems.append(f"KEEPER_POSE shot {i} {s['id']} (a talking Keeper faces the lens on a static camera: "
                        f"{' and '.join(repr(w) for w in KEEPER_POSE)}, no push-in, pull-back, tracking, orbit, lean or bow; those "
                        "lost the face or the lips, E98)")
    return problems


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
    for i, s in enumerate(shots):
        problems += prompt_problems(i, s)
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
            if slowest > TALK_LINE_MAX:
                problems.append(f"KEEPER_LINE_TOO_LONG shot {i} {s['id']} (~{slowest:.1f} s at the slowest pace; "
                                f"Pavo input audio <= {TALK_LINE_MAX:.2f} s)")
            if span < talk_min(gaps):
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
        if talking(shots[a]):
            continue
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
    if keeper_used and keeper and (keeper.get("status") != "APPROVED" or not keeper.get("refs")):
        pending.append(f"CHARACTER_PENDING keeper ({keeper.get('status')}): Claude reviews his reference sheet and "
                       "sets APPROVED with kept refs, by PR, before episode.yml can generate")
    estimate = {"seconds": round(total, 1), "keeper_share": round(share, 3), "lesson_share": round(lesson_share, 3),
                "establishing_share": round(est_share, 3), "lines": len(items), "shots": len(shots),
                "spoken_lines": sum(1 for x in items if x.get("speaker")),
                "words": sum(words(x["text"]) for x in items)}
    return {"problems": problems, "pending": pending, "estimate": estimate}


def main(argv):
    args = [a for a in argv[1:] if a != "--strict"]
    if len(args) != 1:
        raise SystemExit(__doc__)
    result = check(json.loads(Path(args[0]).read_text()))
    print(json.dumps(dict(plan=args[0], **result), indent=1))
    if result["problems"] or ("--strict" in argv and result["pending"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
