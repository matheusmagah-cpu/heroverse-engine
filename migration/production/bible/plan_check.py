#!/usr/bin/env python3
"""Check a Short's plan (`bible-plan-v1`) before anything is voiced or generated (owner, 2026-10-26: the Keeper
narrates on screen with our words in sync and the story is acted out by the character bible's people).

A plan is `migration/production/bible/plans/<episode-id>.json`:
  {"version": "bible-plan-v1", "episode": "genesis-07-short", "part": 7, "passage": "Genesis 6:5-13 (KJV, ...)",
   "aspect_ratio": "9:16",
   "narration": [{"kind": "story|scripture|insight|cta", "text": "...", "reference": "Genesis 6:5 (KJV)"?}, ...],
   "shots": [{"id": "k-open", "kind": "keeper", "lines": [0], "prompt": "..."},
             {"id": "s-tents", "kind": "scene", "lines": [1], "seconds": 6, "prompt": "...",
              "characters": ["eve"] | [], "figures": "anonymous"?, "establishing": true?}, ...]}

Rules (DECISIONS.md 2026-10-26 "The Keeper narrates every video", PROMPT_GUIDE.md "Keeper + acted scenes"):
- narration: the records publish_episode.short_problems reads (62-90 s estimated, >= 40 % our words, one insight of
  >= 20 words, a close to the full story); every scripture line is the KJV word for word (kjv_check).
- shots in order, each carrying consecutive narration lines; every line is carried, in order; consecutive scene shots
  may share the same lines (the composer splits that time between them and cuts every 2-4 s).
- keeper: the Keeper speaks the lines it carries (Pavo input audio + his approved reference images). Its audio is
  2-12 s (Flash's input-audio limit; estimated here at the slowest measured Kokoro pace, measured again after the
  voice); the last keeper shot also holds the 1.2 s tail and a 0.6 s margin, so its audio is at most 10.2 s.
  The prompt carries his look and one wardrobe variant word for word and says he speaks. The Keeper opens (the
  first shot, from 0 s: the hook) and closes (the last shot), and takes at most 25 % of the Short.
- scene: 4-12 s of Pavo video, a prompt in PROMPT_GUIDE's five-part form; each character APPROVED in characters.json
  with its look word for word in the prompt (characters.py), at most 5 reference images in all; the Keeper never acts
  in a scene. A scene with no character shows anonymous people seen only from behind / in silhouette
  (`figures: "anonymous"`, the prompt says so) or is an establishing shot (`establishing: true`), which is held at
  most 2 s on screen, all of them together at most 15 % of the Short.
- God the Father is never a visible figure: a prompt that names Him must show Him only as light, wind, fire or a
  voice, and never with a body, face, hands, robe or throne.
The Keeper is DRAFT until Claude approves his reference sheet; that is reported as ONE pending row, not a problem.

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

VERSION = "bible-plan-v1"
KINDS = ("story", "scripture", "insight", "cta")
EPISODE_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SHOT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
RATIOS = ("9:16",)                   # Shorts only
# Kokoro am_michael, speed 1.0, measured on Genesis 6 (evidence/pavo/20261025/genesis-06/compose/timeline.json):
# 2.30-2.98 words a second, 2.4 typical. Estimates use the typical pace; the keeper ceiling uses the slowest.
WPS = 2.4
WPS_SLOWEST = 2.25
LINE_GAP = 0.35                      # silence between narration lines (episode_build.LINE_GAP)
TAIL = 1.2                           # short_engine tail after the last word
KEEPER_AUDIO = (2.0, 12.0)           # Flash input audio, per request
KEEPER_LAST_MAX = 12.0 - TAIL - 0.6  # the closing clip also holds the tail and a margin (clips <= 12 s)
KEEPER_SHARE_MAX = 0.25
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


def words(text):
    return len(text.split())


def estimate_seconds(text, wps=WPS):
    return words(text) / wps


def _lines_problem(i, shot, n):
    lines = shot.get("lines")
    if (not isinstance(lines, list) or not lines or not all(type(x) is int for x in lines)
            or lines != list(range(lines[0], lines[0] + len(lines))) or lines[0] < 0 or lines[-1] >= n):
        return f"SHOT_LINES shot {i} {shot.get('id')}: consecutive narration indices 0-{n - 1}"
    return None


def groups(shots):
    """Runs of consecutive shots carrying the same lines: [(first shot index, last shot index, lines)]."""
    out = []
    for i, s in enumerate(shots):
        if out and s["lines"] == out[-1][2]:
            out[-1] = (out[-1][0], i, out[-1][2])
        else:
            out.append((i, i, s["lines"]))
    return out


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
    for k, line in enumerate(narration):
        if not isinstance(line, dict) or line.get("kind") not in KINDS or not str(line.get("text", "")).strip():
            problems.append(f"NARRATION_LINE {k} (kind {'/'.join(KINDS)} and text)")
            continue
        if line["kind"] == "scripture":
            if not line.get("reference"):
                problems.append(f"SCRIPTURE_REFERENCE_MISSING line {k}")
            else:
                bad = kjv_check.problem(line["reference"], line["text"])
                if bad:
                    problems.append(f"KJV line {k}: {bad}")
    if problems and any(p.startswith("NARRATION_LINE") for p in problems):
        return {"problems": problems, "pending": pending, "estimate": {}}

    n = len(narration)
    est = [estimate_seconds(x["text"]) for x in narration]
    total = sum(est) + LINE_GAP * (n - 1) + TAIL
    problems += [f"SHORT {p}" for p in publish_episode.short_problems(
        {"format": "short", "part": plan.get("part", 0), "seconds": round(total, 1), "narration": narration})]

    shots = plan.get("shots")
    if not isinstance(shots, list) or not shots:
        return {"problems": problems + ["SHOTS_MISSING"], "pending": pending, "estimate": {"seconds": round(total, 1)}}
    seen, bad_lines = set(), False
    for i, s in enumerate(shots):
        if not isinstance(s, dict) or s.get("kind") not in ("keeper", "scene"):
            problems.append(f"SHOT_KIND shot {i} (keeper or scene)")
            bad_lines = True
            continue
        if not isinstance(s.get("id"), str) or not SHOT_ID.fullmatch(s["id"]) or s["id"] in seen:
            problems.append(f"SHOT_ID shot {i} (unique, a-z 0-9 -)")
        seen.add(s.get("id"))
        lp = _lines_problem(i, s, n)
        if lp:
            problems.append(lp)
            bad_lines = True
    if bad_lines:
        return {"problems": problems, "pending": pending, "estimate": {"seconds": round(total, 1)}}

    runs = groups(shots)
    expect = 0
    for a, b, lines in runs:
        if lines[0] != expect:
            problems.append(f"LINES_OUT_OF_ORDER shot {a} {shots[a]['id']} (next line is {expect})")
        expect = lines[-1] + 1
        kinds = {shots[j]["kind"] for j in range(a, b + 1)}
        if "keeper" in kinds and b > a:
            problems.append(f"KEEPER_LINES_SHARED shot {a} {shots[a]['id']} (a keeper shot speaks its own lines)")
    if expect != n:
        problems.append(f"LINES_NOT_CARRIED from line {expect}")
    if shots[0]["kind"] != "keeper" or shots[0]["lines"][0] != 0:
        problems.append("KEEPER_MUST_OPEN (the first shot is the Keeper speaking the hook from 0 s)")
    if shots[-1]["kind"] != "keeper":
        problems.append("KEEPER_MUST_CLOSE (the last shot is the Keeper)")

    keeper = chars.get("keeper")
    keeper_seconds, establishing_seconds, keeper_used = 0.0, 0.0, False
    for i, s in enumerate(shots):
        problems += prompt_problems(i, s)
        lines = s["lines"]
        span_words = " ".join(narration[k]["text"] for k in lines)
        span = sum(est[k] for k in lines) + LINE_GAP * (len(lines) - 1)
        if s["kind"] == "keeper":
            keeper_used = True
            keeper_seconds += span
            slowest = words(span_words) / WPS_SLOWEST + LINE_GAP * (len(lines) - 1)
            limit = KEEPER_LAST_MAX if i == len(shots) - 1 else KEEPER_AUDIO[1]
            if slowest > limit:
                problems.append(f"KEEPER_LINE_TOO_LONG shot {i} {s['id']} (~{slowest:.1f} s at the slowest pace; "
                                f"Pavo input audio <= {limit:.1f} s)")
            if span < KEEPER_AUDIO[0]:
                problems.append(f"KEEPER_LINE_TOO_SHORT shot {i} {s['id']} (input audio >= 2 s)")
            if s.get("characters") not in (None, ["keeper"]) or s.get("seconds") is not None:
                problems.append(f"KEEPER_SHOT_FIELDS shot {i} {s['id']} (characters and seconds come from the line)")
            if not keeper:
                problems.append("CHARACTER_UNKNOWN keeper (characters.json)")
                continue
            if keeper["look"] not in s.get("prompt", ""):
                problems.append(f"CHARACTER_LOOK_CHANGED shot {i}: keeper (the prompt must carry its look word for word)")
            if not any(w in s.get("prompt", "") for w in keeper.get("wardrobe", {}).values()):
                problems.append(f"KEEPER_WARDROBE shot {i} {s['id']} (one wardrobe variant word for word: same room)")
            if not re.search(r"(?i)\bspeak", s.get("prompt", "")):
                problems.append(f"KEEPER_NOT_SPEAKING shot {i} {s['id']} (say that he speaks to the camera)")
            continue
        cids = s.get("characters", [])
        if not isinstance(cids, list) or not all(isinstance(c, str) for c in cids):
            problems.append(f"SHOT_CHARACTERS shot {i} {s['id']}")
            continue
        if "keeper" in cids:
            problems.append(f"KEEPER_IN_SCENE shot {i} {s['id']} (the Keeper narrates; he never acts in the story)")
        problems += ch.problems([{"prompt": s.get("prompt", ""), "characters": [c for c in cids if c != "keeper"]}],
                                chars)
        refs = sum(len(chars.get(c, {}).get("refs") or []) for c in cids if c != "keeper")
        if refs > ch.MAX_REFS:
            problems.append(f"REFERENCES_OVER_{ch.MAX_REFS} shot {i} {s['id']} ({refs} approved images)")
        if type(s.get("seconds")) is not int or not SCENE_SECONDS[0] <= s["seconds"] <= SCENE_SECONDS[1]:
            problems.append(f"SCENE_SECONDS shot {i} {s['id']} (4-12)")
        if not cids:
            if s.get("establishing") is True:
                establishing_seconds += ESTABLISHING_HOLD
            elif s.get("figures") == "anonymous":
                if not ANONYMOUS.search(s.get("prompt", "")):
                    problems.append(f"FIGURES_NOT_ANONYMOUS shot {i} {s['id']} (seen from behind or in silhouette)")
            else:
                problems.append(f"SCENE_WITHOUT_CHARACTERS shot {i} {s['id']} (act it out with the bible's people, "
                                "anonymous figures from behind, or mark a <= 2 s establishing shot)")
        elif s.get("establishing"):
            problems.append(f"ESTABLISHING_WITH_CHARACTERS shot {i} {s['id']}")

    # Enough footage for every run of scenes (establishing shots hold 2 s; a clip may be slowed MAX_SLOW at most)
    for a, b, lines in runs:
        if shots[a]["kind"] != "scene":
            continue
        span = sum(est[k] for k in lines) + LINE_GAP * len(lines)
        members = [shots[j] for j in range(a, b + 1)]
        if all(m.get("establishing") for m in members) and span > ESTABLISHING_HOLD * len(members) + 0.5:
            problems.append(f"ESTABLISHING_ONLY shot {a} {shots[a]['id']} (~{span:.1f} s of words over landscape)")
        footage = sum(ESTABLISHING_HOLD if m.get("establishing") else m.get("seconds") or 0 for m in members)
        if footage * MAX_SLOW < span:
            problems.append(f"SCENE_FOOTAGE_SHORT shot {a} {shots[a]['id']} ({footage} s of clips for ~{span:.1f} s)")
    share = keeper_seconds / total if total else 0
    if share > KEEPER_SHARE_MAX:
        problems.append(f"KEEPER_SHARE {share:.2f} > {KEEPER_SHARE_MAX} (estimated)")
    est_share = establishing_seconds / total if total else 0
    if est_share > ESTABLISHING_SHARE_MAX:
        problems.append(f"ESTABLISHING_SHARE {est_share:.2f} > {ESTABLISHING_SHARE_MAX}")
    if keeper_used and keeper and (keeper.get("status") != "APPROVED" or not keeper.get("refs")):
        pending.append(f"CHARACTER_PENDING keeper ({keeper.get('status')}): Claude reviews his reference sheet and "
                       "sets APPROVED with kept refs, by PR, before episode.yml can generate")
    estimate = {"seconds": round(total, 1), "keeper_share": round(share, 3),
                "establishing_share": round(est_share, 3), "lines": n, "shots": len(shots),
                "words": sum(words(x["text"]) for x in narration)}
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
