#!/usr/bin/env python3
"""Check a Bible-story long's shot plan (`bible-long-plan-v1`) before anything is voiced or generated (owner,
2026-10-26: "adjust the long videos ... apply the mined structure and model it to our format: the Keeper narrating,
and the Bible characters the same whenever they repeat across stories"). Design: LONG_DESIGN.md.

A long plan is `migration/production/bible/plans/<arc>-long.json`; it is the Short's plan (`bible-plan-v2`, the same
shots, speakers, God's voice-over and Keeper shots, checked by the same plan_check functions) laid out over the long's
beat map, plus the long's own fields:
  {"version": "bible-long-plan-v1", "long": "arc-01-long", "arc": "arc-01", "pilot": "pilot-015",
   "aspect_ratio": "16:9", "burned_captions": false,
   "chapters": [{"id": "c1", "short": "genesis-01-short", "title": "<the Short's title>"}, ...],
   "narration": [{"kind": "story|scripture|promise|insight|cta", "text": "...", "reference"?, "rehook"?: true}],
   "shots": [{"id", "kind": "scene|keeper", "beat": "cold_open|keeper_promise|chapter|payoff|keeper_insight|
              keeper_close", "chapter"?: "c1", "conflict"?: true, "climax"?: true, "rehook"?: true (a spoken line),
              "window_of"?: "<an earlier scene id>" (a second window of that clip: no prompt, seconds or characters),
              ... every bible-plan-v2 shot field}]}

Every number comes from one place: the structure's `script.gate` (structures/bible-story-long.json, the block
script_check.structure_problems reads for the long's script) and the frozen story QA the long is measured against
(qa_criteria_story_v3.json, sha256 pinned here). Rules, each mapped to its source:
- the estimate: each line at its voice's measured Kokoro pace (VOICE_PACE), LONG_LINE_GAP 0.6 s between lines.
- gate.aspect_ratio 16:9 (ASPECT_RATIO); gate.burned_captions false (BURNED_CAPTIONS); gate.length_min 14-18 min
  on the estimate (LONG_LENGTH); one chapter per Short of the arc, in arcs.json order (else ARC_SHORTS, an owner row).
- cold open (gate.cold_open_s 30, keeper_in_cold_open false): the first shot is a scene whose spoken line starts at
  0 s (OPEN_NOT_SPOKEN), a character or God speaks the conflict inside 30 s (`conflict: true`, COLD_OPEN_CONFLICT),
  no Keeper shot starts inside it (KEEPER_IN_COLD_OPEN), its words end by 30 s whatever follows (COLD_OPEN_LENGTH)
  on an open question (COLD_OPEN_NO_QUESTION); the build holds its last frame until the Keeper at exactly 30 s, at
  most COLD_OPEN_HOLD_MAX (COLD_OPEN_SHORT).
- keeper promise: Keeper shots only, <= gate.keeper_promise_max_s (KEEPER_PROMISE_LENGTH), right after the cold open.
- re-hooks: >= gate.rehooks_min lines with `rehook: true` (REHOOKS); every chapter but the last ends on one
  (CHAPTER_END_NO_REHOOK); never more than gate.rehook_gap_max_s from the promise to a re-hook, between two, or from
  the last to the climax (REHOOK_GAP).
- climax: exactly one shot `climax: true` (CLIMAX_COUNT) in a chapter, acted with people on screen (CLIMAX_NOT_ACTED,
  E92), on the key KJV line spoken by the hero or God (that shot or the one before it speaks a referenced line:
  CLIMAX_NO_KJV_LINE), starting at gate.climax_at 0.6-0.85 of the runtime (CLIMAX_POSITION); then the payoff
  (PAYOFF_MISSING, PAYOFF_BEFORE_CLIMAX).
- keeper insight <= gate.keeper_insight_max_s with >= 20 words of insight (KEEPER_INSIGHT_LENGTH, INSIGHT_SHORT);
  keeper close <= gate.keeper_close_max_s, the last shot, a comment question and the next story (KEEPER_CLOSE_LENGTH,
  KEEPER_MUST_CLOSE, CLOSE_NO_QUESTION, CLOSE_NO_NEXT); Keeper shots only in those beats and the promise; Keeper
  share <= gate.keeper_share_max of the runtime (KEEPER_SHARE).
- slow stretches: no run of shots without a person on screen, and no one voice run, longer than
  gate.slow_stretch_max_s (SLOW_STRETCH).
- characters: every character an entry of characters.json with its look word for word (CHARACTER_UNKNOWN,
  CHARACTER_LOOK_CHANGED), the same entry as in the Shorts; a character named in a prompt is listed in that shot's
  `characters`, so its references go in (CHARACTER_NOT_LISTED); a DRAFT character is ONE pending row each
  (CHARACTER_PENDING) until Claude approves its sheet by PR.
- the frozen QA (story v3, owner 2026-10-26 "Sim, régua nova"): every cut a 4-7 s hold (grammar.scene_seconds:
  HOLD_UNDER_QA / HOLD_OVER_QA, a talking line at its slowest pace), "you" within 8 s (HOOK_SECOND_PERSON), 115-165
  words a minute (WORDS_PER_MINUTE_EST), speech presence >= 0.85 (SPEECH_PRESENCE_EST); its three acted-long rows:
  the first shot is the acted cold-open conflict (the cold-open checks), figures are approved characters only
  (CHARACTER_* above; a DRAFT one stays pending), and 100 % Pavo with every talking clip judged by lipsync_check, so a
  talking speaker needs a human face (TALKING_WITHOUT_A_FACE: the serpent is silent). Against an older version (v2:
  no figure, >= 40 % real footage, <= 55 % AI, a title card first) those rows are pending owner rows
  (QA_CONFLICT_*), never decided by this check.
- everything a Short's plan_check enforces on a shot: the KJV word for word, God only a voice over a shot with no
  person, a character speaker APPROVED with its own voice, talking lines 3.23-11.55 s and reachable (E95), the Keeper's
  look, wardrobe and pose (E98), five-part prompts (the Keeper's shots too), <= 5 references, anonymous figures or
  establishing shots, through plan_check's shared helpers; plus CHARACTER_NO_LOOK, CHARACTER_NO_REFS / KEEPER_NO_REFS
  (APPROVED with no kept reference), TALKING_WITHOUT_A_FACE (any QA), REHOOK_ON_SILENT_SHOT, ESTABLISHING_ONLY and
  LONG_ID (= f"{arc}-long").

usage: long_plan_check.py PLAN.json [--strict]   prints JSON {problems, pending, estimate}; exit 1 on a problem
                                                 (--strict: also on a pending row)
"""
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "migration" / "production"))
import plan_check as pc  # noqa: E402
from voice_pace import VOICE_PACE, VOICE_SLOWEST  # noqa: E402  (shared with plan_check)
import script_check  # noqa: E402  (story_gate: the one reader of the structure's gate)

ch = pc.ch
VERSION = "bible-long-plan-v1"
STRUCTURE = script_check.STRUCTURE
QA = ROOT / "migration" / "production" / "qa_criteria_story_v3.json"
QA_SHA256 = "746e772d8024a93ef95cbf0f226568cf972e5611b59a430322312605f8e7badc"   # frozen 2026-10-26 (owner)
FACELESS = ("its",)         # characters.json pronoun of a speaker with no human face (lipsync_check cannot judge it)
ARCS = HERE / "arcs.json"
# the build holds the cold open's last frame (under the music) until the Keeper starts at gate.cold_open_s; more than
# this of held frame is dead air: the cold open is too short (COLD_OPEN_SHORT)
COLD_OPEN_HOLD_MAX = 3.0
KINDS = pc.KINDS + ("promise",)
BEATS = ("cold_open", "keeper_promise", "chapter", "payoff", "keeper_insight", "keeper_close")
BEAT_KINDS = {"cold_open": ("story", "scripture"), "keeper_promise": ("promise",), "chapter": ("story", "scripture"),
              "payoff": ("story", "scripture"), "keeper_insight": ("insight",), "keeper_close": ("cta",)}
KEEPER_ONLY = ("keeper_promise", "keeper_close")
SECOND_PERSON = ("you", "your", "you're")     # qa_pilot.hook_second_person
INSIGHT_MIN_WORDS = pc.publish_episode.INSIGHT_MIN_WORDS
NEXT = re.compile(r"(?i)\bnext\b")
# Measured Pavo wall time a generation on episode.yml (sequential submit + poll, 2026-10-26, genesis-07-short): run
# 40263488773 8,062 s for 28 scene submissions (288 s each); 40278642295 5 scenes + 3 talking in 2,469 s;
# 40285879529 and 40297987571 3 talking each in 1,101 s and 1,096 s (366 s each, lipsync_check included).
PAVO_SCENE_S = 288
PAVO_TALK_S = 366
# Kokoro pace by voice (voice_pace.VOICE_PACE, the table plan_check uses too): every line, the narrator's included, at
# its voice's measured pace (the narrator am_michael 2.874 words/s over the arc-1 long). A character speaks ~35 % faster
# than the narrator. Another voice: plan_check.WPS until measured (a talking line is then VOICE_PACE_UNMEASURED).
SLOW_RATIO = pc.SLOW_RATIO                    # the slowest pace, as a share of the normal one (2.25 / 2.75)
# the long breathes between lines: at the Short's 0.35 s the measured arc-1 voice ran 164.5 words a minute, at the
# QA's 165 ceiling; 0.6 s brings it to ~158 (pilot_render's v4 long widened its sentence gap for the same row). The
# long's build lays its lines with this gap (LONG_DESIGN.md slice 3).
LONG_LINE_GAP = 0.6
# pavo_footage.py: Real-ESRGAN to 2560x1440 on a runner, 543 s for a 6 s clip (story QA: 1440p, never a plain resize)
UPSCALE_S_PER_CLIP_S = 543 / 6


def pace(item):
    """Words a second of the voice that speaks this line (the narration is the Keeper's)."""
    return VOICE_PACE.get(item.get("speaker") or ch.NARRATOR, pc.WPS)


def slowest_pace(item):
    """The same voice at its slowest: a speaker's VOICE_SLOWEST (its measured slow bound, E104), the narration's pace
    slowed by SLOW_RATIO."""
    who = item.get("speaker") or ch.NARRATOR
    return VOICE_SLOWEST[who] if who in VOICE_SLOWEST else pace(item) * SLOW_RATIO


def gate():
    return script_check.story_gate()


def qa(path=QA):
    return json.loads(Path(path).read_text())


def arcs(path=ARCS):
    return {a["id"]: a for a in json.loads(Path(path).read_text())["arcs"]}


def _token(name):
    """The word a prompt names a character by: 'The serpent' -> serpent, 'The Keeper (series narrator)' -> keeper."""
    name = re.sub(r"\(.*?\)", "", name or "").strip()
    return re.sub(r"(?i)^the\s+", "", name).lower() or None


def _people(s, shots_by_id):
    src = shots_by_id.get(s.get("window_of")) or s
    if s["kind"] == "keeper":
        return True
    if pc.speaking(src) and src["speaker"] == ch.GOD:
        return False
    return bool(src.get("characters")) or src.get("figures") == "anonymous"


def check(plan, chars=None, gate_values=None, criteria=None, arc_table=None):
    """{"problems": [...], "pending": [...], "estimate": {...}} for a long plan. gate_values: the structure's
    script.gate (default gate()); criteria: the frozen story QA (default qa()); arc_table: arcs.json by id (default
    arcs())."""
    chars = chars if chars is not None else ch.registry()
    g = gate_values if gate_values is not None else gate()
    q = criteria if criteria is not None else qa()
    arc_map = arc_table if arc_table is not None else arcs()
    problems, pending = [], []

    # the long as a whole
    if plan.get("version") != VERSION:
        problems.append(f"PLAN_VERSION (need {VERSION})")
    if plan.get("long") != f"{plan.get('arc')}-long":
        problems.append(f"LONG_ID {plan.get('long')} (the arc's id + \"-long\": {plan.get('arc')}-long)")
    if plan.get("aspect_ratio") != g["aspect_ratio"]:
        problems.append(f"ASPECT_RATIO {plan.get('aspect_ratio')} (a long is {g['aspect_ratio']})")
    if plan.get("burned_captions") is not g["burned_captions"]:
        problems.append("BURNED_CAPTIONS (the long carries an uploaded .srt track, none burned in: burned_captions "
                        "false, story QA v2/v3)")
    # E108 (review of #426): the period rule of the Short, the same shared helper: every scene prompt states its
    # story's period word for word and names nothing it excludes
    if isinstance(plan.get("shots"), list):
        problems += pc.plan_period_problems(plan, plan["shots"])
        # E110: and no scene prompt asks for writing (the same shared helper)
        problems += pc.plan_writing_problems(plan["shots"])
    arc = arc_map.get(plan.get("arc"))
    chapters = plan.get("chapters")
    if not arc:
        problems.append(f"ARC_UNKNOWN {plan.get('arc')} (an arcs.json id)")
    elif (arc.get("long") or {}).get("pilot") not in (None, plan.get("pilot")):
        problems.append(f"PILOT_MISMATCH {plan.get('pilot')} (arcs.json {arc['id']} long pilot "
                        f"{arc['long']['pilot']})")
    if (not isinstance(chapters, list) or not chapters
            or not all(isinstance(c, dict) and c.get("id") and c.get("short") and c.get("title") for c in chapters)
            or len({c["id"] for c in chapters}) != len(chapters)):
        return {"problems": problems + ["CHAPTERS (each {id, short, title}, unique ids)"], "pending": pending,
                "estimate": {}}
    if arc and [c["short"] for c in chapters] != arc["shorts"]:
        pending.append(f"ARC_SHORTS chapters {[c['short'] for c in chapters]} vs arcs.json {arc['id']} "
                       f"{arc['shorts']} (one chapter per Short of the arc: the owner sets the arc, arcs.json by PR)")
    chapter_index = {c["id"]: k for k, c in enumerate(chapters)}

    narration = plan.get("narration")
    if not isinstance(narration, list) or not narration:
        return {"problems": problems + ["NARRATION_MISSING"], "pending": pending, "estimate": {}}
    problems += pc.narration_problems(narration, KINDS)
    if any(p.startswith("NARRATION_LINE") for p in problems):
        return {"problems": problems, "pending": pending, "estimate": {}}
    shots = plan.get("shots")
    if not isinstance(shots, list) or not shots:
        return {"problems": problems + ["SHOTS_MISSING"], "pending": pending, "estimate": {}}
    shape, bad = pc.shot_shape_problems(shots, len(narration))
    problems += shape
    if bad:
        return {"problems": problems, "pending": pending, "estimate": {}}
    problems += pc.lines_order_problems(shots, len(narration))

    # the voice track and its timeline (the Short's estimate: WPS, LINE_GAP between lines, TAIL after the last)
    items, carried = pc.sequence(plan)
    for i, s in enumerate(shots):
        if pc.speaking(s) and s.get("rehook"):
            items[carried[i][0]]["rehook"] = True
    est = [pc.words(x["text"]) / pace(x) for x in items]
    start, t = [], 0.0
    for e in est:
        start.append(t)
        t += e + LONG_LINE_GAP
    total = sum(est) + LONG_LINE_GAP * (len(items) - 1) + pc.TAIL
    # the cold open ends where the first line after it starts; the Keeper never starts before cold_open_s, so the
    # build holds the cold open's last frame (under the music) until then (COLD_OPEN_HOLD_MAX at most)
    cold = g["cold_open_s"]
    after = next((i for i, s in enumerate(shots) if s.get("beat") != "cold_open"), None)
    cold_voice = start[carried[after][0]] if after is not None else total
    cold_hold = 0.0
    if after is not None and shots[0].get("beat") == "cold_open" and cold_voice < cold:
        cold_hold = cold - cold_voice
        k0 = carried[after][0]
        start = start[:k0] + [x + cold_hold for x in start[k0:]]
        total += cold_hold
    begin, hold = [0.0] * len(shots), [0.0] * len(shots)
    for a, b, idx in pc.groups(shots, carried):
        t0 = start[idx[0]]
        t1 = start[idx[-1] + 1] if idx[-1] + 1 < len(items) else total
        for j in range(a, b + 1):
            hold[j] = (t1 - t0) / (b - a + 1)
            begin[j] = t0 + (j - a) * hold[j]
    end = [begin[i] + hold[i] for i in range(len(shots))]

    # every shot
    by_id = {s["id"]: s for s in shots}
    index = {s["id"]: i for i, s in enumerate(shots)}
    named = {cid: re.compile(rf"(?i)\b{re.escape(tok)}\b") for cid, tok in
             ((cid, _token(c.get("name"))) for cid, c in chars.items()) if tok and cid != ch.NARRATOR}
    lo, hi = q["grammar"]["scene_seconds"]
    keeper = chars.get(ch.NARRATOR)
    drafts, beat_at, chap_at = set(), 0, 0
    windows = {}
    for i, s in enumerate(shots):
        sid, beat = s["id"], s.get("beat")
        if beat not in BEATS:
            problems.append(f"SHOT_BEAT shot {i} {sid} ({'/'.join(BEATS)})")
            continue
        if BEATS.index(beat) < beat_at:
            problems.append(f"BEAT_ORDER shot {i} {sid} ({beat} after {BEATS[beat_at]})")
        beat_at = max(beat_at, BEATS.index(beat))
        if s.get("rehook") and not pc.speaking(s):
            problems.append(f"REHOOK_ON_SILENT_SHOT shot {i} {sid} (a re-hook is a line: put rehook: true on the "
                            "narration line, or on a speaking shot)")
        if beat in ("chapter", "payoff"):
            if s.get("chapter") not in chapter_index:
                problems.append(f"SHOT_CHAPTER shot {i} {sid} (one of {list(chapter_index)})")
            elif chapter_index[s["chapter"]] < chap_at:
                problems.append(f"CHAPTER_ORDER shot {i} {sid}")
            else:
                chap_at = chapter_index[s["chapter"]]
        elif s.get("chapter") is not None:
            problems.append(f"SHOT_CHAPTER shot {i} {sid} (only chapter and payoff shots name a chapter)")
        idx = carried[i]
        if any(items[k]["kind"] not in BEAT_KINDS[beat] for k in idx):
            problems.append(f"LINE_KIND_BEAT shot {i} {sid} ({beat} carries {'/'.join(BEAT_KINDS[beat])} lines)")
        gaps = LONG_LINE_GAP * (len(idx) - 1)
        span = sum(est[k] for k in idx) + gaps
        slowest = sum(pc.words(items[k]["text"]) / slowest_pace(items[k]) for k in idx) + gaps
        problems += pc.talk_reach_problems(i, s, span, slowest, gaps)
        # the frozen QA's hold band; a talking line is judged at its slowest pace too (its clip is retimed to it)
        h_max = hold[i] + (slowest - span if pc.talking(s) else 0.0)
        if hold[i] < lo - 1e-6:
            problems.append(f"HOLD_UNDER_QA shot {i} {sid} (~{hold[i]:.1f} s on screen; story QA holds {lo:g}-{hi:g} s)")
        if i < len(shots) - 1 and h_max > hi + 1e-6:
            problems.append(f"HOLD_OVER_QA shot {i} {sid} (~{hold[i]:.1f}-{h_max:.1f} s on screen; story QA holds "
                            f"{lo:g}-{hi:g} s: split it into more cuts or shorter lines)")
        if s["kind"] == "keeper":
            if s.get("voiceover") is True:
                # the voice-over Keeper (plan B, PR #423) is built and checked for the Short only (episode_build,
                # lipsync_check --still-mouth); the long has no such path yet
                problems.append(f"LONG_VOICEOVER_UNSUPPORTED shot {i} {sid} (a voice-over Keeper exists for the Short "
                                "only; the long's Keeper talks until a long voice-over path is built and tested)")
            if beat not in ("keeper_promise", "keeper_insight", "keeper_close"):
                problems.append(f"KEEPER_OUT_OF_BEAT shot {i} {sid} (the Keeper: promise, insight and close only)")
            if slowest > pc.TALK_LINE_MAX:
                problems.append(f"KEEPER_LINE_TOO_LONG shot {i} {sid} (~{slowest:.1f} s at the slowest pace)")
            if span < pc.talk_min(gaps):
                problems.append(f"KEEPER_LINE_TOO_SHORT shot {i} {sid} (>= {pc.talk_min(gaps):.2f} s, E95)")
            if s.get("characters") not in (None, [ch.NARRATOR]) or s.get("seconds") is not None:
                problems.append(f"KEEPER_SHOT_FIELDS shot {i} {sid} (characters and seconds come from the line)")
            problems += pc.prompt_problems(i, s)
            if not keeper:
                problems.append("CHARACTER_UNKNOWN keeper (characters.json)")
                continue
            if not isinstance(keeper.get("look"), str) or not keeper["look"].strip():
                problems.append(f"CHARACTER_NO_LOOK shot {i}: keeper (characters.json `look`)")
                continue
            if keeper.get("status") == "APPROVED" and not keeper.get("refs"):
                problems.append(f"KEEPER_NO_REFS shot {i} {sid} (APPROVED with no kept reference image: his face and "
                                "his talking frame cannot go in; keep his reviewed refs)")
            elif keeper.get("status") != "APPROVED":
                drafts.add(ch.NARRATOR)
            problems += pc.keeper_prompt_problems(i, s, keeper)
            continue
        if beat in KEEPER_ONLY:
            problems.append(f"KEEPER_BEAT_SCENE shot {i} {sid} (the {beat} is the Keeper on screen)")
        if s.get("window_of") is not None:
            src = by_id.get(s["window_of"])
            j = index[src["id"]] if src else -1
            if not src or j >= i or src["kind"] != "scene" or src.get("window_of") or pc.speaking(src):
                problems.append(f"WINDOW_OF shot {i} {sid} (an earlier scene that is not a window or a speaking shot)")
                continue
            if any(k in s for k in ("prompt", "seconds", "characters", "speaker")):
                problems.append(f"WINDOW_FIELDS shot {i} {sid} (a window reuses its clip: no prompt, seconds, "
                                "characters or speaker)")
            if by_id.get(shots[i - 1].get("window_of")) is src or shots[i - 1] is src:
                problems.append(f"WINDOW_ADJACENT shot {i} {sid} (a second window of {src['id']} right after it is "
                                "not a cut)")
            windows.setdefault(src["id"], []).append(i)
            continue
        problems += pc.prompt_problems(i, s)
        cids = s.get("characters", [])
        if not isinstance(cids, list) or not all(isinstance(c, str) for c in cids):
            problems.append(f"SHOT_CHARACTERS shot {i} {sid}")
            continue
        if ch.NARRATOR in cids:
            problems.append(f"KEEPER_IN_SCENE shot {i} {sid} (the Keeper narrates; he never acts in the story)")
        if pc.speaking(s):
            who = chars.get(s["speaker"]) or {}
            for p in pc._speaker_problems(i, s, chars, span, slowest):
                if p.startswith("SPEAKER_NOT_APPROVED") and who.get("status") == "DRAFT":
                    drafts.add(s["speaker"])
                else:
                    problems.append(p)
            if pc.talking(s) and who.get("pronoun") in FACELESS:
                problems.append(f"TALKING_WITHOUT_A_FACE shot {i} {sid}: {s['speaker']} (every talking clip passes "
                                "lipsync_check, which reads a human face and lips; let the Keeper narrate its words)")
        prompt = s.get("prompt", "")
        problems += pc.character_problems(i, cids, prompt, chars, drafts)
        for cid, name_re in named.items():
            if cid not in cids and name_re.search(prompt):
                problems.append(f"CHARACTER_NOT_LISTED shot {i} {sid}: {cid} (named in the prompt: list it in "
                                "`characters`, its look and references go in)")
        refs = sum(len(chars.get(c, {}).get("refs") or []) for c in cids if c != ch.NARRATOR)
        if refs > ch.MAX_REFS:
            problems.append(f"REFERENCES_OVER_{ch.MAX_REFS} shot {i} {sid} ({refs} approved images)")
        if pc.talking(s):
            continue
        problems += pc.scene_seconds_problems(i, s)
        if pc.speaking(s):
            continue
        problems += pc.figures_problems(i, s, cids)

    # footage: a clip covers its holds and its windows' (distinct parts, slowed MAX_SLOW at most)
    for i, s in enumerate(shots):
        if s["kind"] != "scene" or s.get("window_of") is not None or pc.talking(s):
            continue
        shown = hold[i] + sum(hold[j] for j in windows.get(s["id"], []))
        if isinstance(s.get("seconds"), int) and s["seconds"] * pc.MAX_SLOW + 1e-6 < shown:
            problems.append(f"FOOTAGE_SHORT shot {i} {s['id']} ({s['seconds']} s of clip for ~{shown:.1f} s on screen)")

    for x, y, idx in pc.groups(shots, carried):
        members = [by_id.get(shots[j].get("window_of")) or shots[j] for j in range(x, y + 1)]
        if not pc.talking(shots[x]) and not pc.speaking(shots[x]) and pc.establishing_only(members, end[y] - begin[x], 0):
            problems.append(f"ESTABLISHING_ONLY shot {x} {shots[x]['id']} (~{end[y] - begin[x]:.1f} s of words over "
                            "landscape alone: a person on screen in every voice run)")

    def beat_shots(name):
        return [i for i, s in enumerate(shots) if s.get("beat") == name]

    def beat_seconds(name):
        return sum(hold[i] for i in beat_shots(name))

    # cold open
    if shots[0].get("beat") != "cold_open":
        problems.append("COLD_OPEN_MISSING (the long opens on its cold open)")
    if shots[0]["kind"] == "keeper" or (not g["keeper_in_cold_open"] and any(
            s["kind"] == "keeper" and begin[i] < cold - 1e-6 for i, s in enumerate(shots))):
        problems.append(f"KEEPER_IN_COLD_OPEN (never the Keeper in the first {cold} s)")
    if not pc.speaking(shots[0]):
        problems.append("OPEN_NOT_SPOKEN (the first shot carries a spoken line from 0 s: a character or God)")
    if not any(s.get("conflict") is True and pc.speaking(s) and s["speaker"] != ch.NARRATOR and begin[i] < cold
               for i, s in enumerate(shots)):
        problems.append(f"COLD_OPEN_CONFLICT (a character or God speaks the conflict inside {cold} s: conflict + "
                        "speaker)")
    co = beat_shots("cold_open")
    kp = beat_shots("keeper_promise")
    if co and cold_voice > cold + 1e-6:
        problems.append(f"COLD_OPEN_LENGTH ~{cold_voice:.1f} s > {cold} s (the structure's cold open)")
    if co and cold_hold > COLD_OPEN_HOLD_MAX + 1e-6:
        problems.append(f"COLD_OPEN_SHORT ~{cold_voice:.1f} s (its last frame would hold {cold_hold:.1f} s before "
                        f"the Keeper at {cold} s; at most {COLD_OPEN_HOLD_MAX:g} s)")
    if co and "?" not in items[carried[co[-1]][-1]]["text"]:
        problems.append("COLD_OPEN_NO_QUESTION (the cold open ends on an open question)")

    # the Keeper's promise, insight and close
    if not kp:
        problems.append("KEEPER_PROMISE_MISSING (the Keeper on screen after the cold open)")
    elif beat_seconds("keeper_promise") > g["keeper_promise_max_s"] + 1e-6:
        problems.append(f"KEEPER_PROMISE_LENGTH ~{beat_seconds('keeper_promise'):.1f} s > {g['keeper_promise_max_s']}")
    ki = beat_shots("keeper_insight")
    if not any(shots[i]["kind"] == "keeper" for i in ki):
        problems.append("KEEPER_INSIGHT_MISSING (the Keeper's one insight from the text)")
    if beat_seconds("keeper_insight") > g["keeper_insight_max_s"] + 1e-6:
        problems.append(f"KEEPER_INSIGHT_LENGTH ~{beat_seconds('keeper_insight'):.1f} s > {g['keeper_insight_max_s']}")
    insight_words = sum(pc.words(items[k]["text"]) for i in ki for k in carried[i] if items[k]["kind"] == "insight")
    if ki and insight_words < INSIGHT_MIN_WORDS:
        problems.append(f"INSIGHT_SHORT {insight_words} words (>= {INSIGHT_MIN_WORDS} of our own reading)")
    kc = beat_shots("keeper_close")
    if shots[-1]["kind"] != "keeper" or shots[-1].get("beat") != "keeper_close":
        problems.append("KEEPER_MUST_CLOSE (the last shot is the Keeper's close)")
    if beat_seconds("keeper_close") > g["keeper_close_max_s"] + 1e-6:
        problems.append(f"KEEPER_CLOSE_LENGTH ~{beat_seconds('keeper_close'):.1f} s > {g['keeper_close_max_s']}")
    close_text = " ".join(items[k]["text"] for i in kc for k in carried[i])
    if kc and "?" not in close_text:
        problems.append("CLOSE_NO_QUESTION (a comment question)")
    if kc and not NEXT.search(close_text):
        problems.append("CLOSE_NO_NEXT (the next story by name)")
    keeper_seconds = sum(hold[i] for i, s in enumerate(shots) if s["kind"] == "keeper")
    share = keeper_seconds / total
    if share > g["keeper_share_max"] + 1e-9:
        problems.append(f"KEEPER_SHARE {share:.2f} > {g['keeper_share_max']} (estimated)")

    # chapters and re-hooks
    for c in chapters:
        if not any(s.get("chapter") == c["id"] for s in shots):
            problems.append(f"CHAPTER_EMPTY {c['id']} ({c['short']})")
    for c in chapters[:-1]:
        mine = [i for i, s in enumerate(shots) if s.get("chapter") == c["id"]]
        if mine and not items[carried[mine[-1]][-1]].get("rehook"):
            problems.append(f"CHAPTER_END_NO_REHOOK {c['id']} (its last line is a question or a cliffhanger, "
                            "rehook: true)")
    rehooks = [start[k] for k, x in enumerate(items) if x.get("rehook")]
    if len(rehooks) < g["rehooks_min"]:
        problems.append(f"REHOOKS {len(rehooks)} < {g['rehooks_min']}")
    climax = [i for i, s in enumerate(shots) if s.get("climax") is True]
    anchors = sorted([end[kp[-1]] if kp else 0.0] + [r for r in rehooks if not kp or r >= end[kp[-1]]]
                     + ([begin[climax[0]]] if len(climax) == 1 else []))
    gap = max((b - a for a, b in zip(anchors, anchors[1:])), default=0.0)
    if gap > g["rehook_gap_max_s"] + 1e-6:
        problems.append(f"REHOOK_GAP ~{gap:.0f} s without a re-hook (<= {g['rehook_gap_max_s']} s)")

    # the climax and the payoff
    a, b = g["climax_at"]
    if len(climax) != 1:
        problems.append(f"CLIMAX_COUNT {len(climax)} (exactly one shot climax: true)")
    for i in climax:
        s = shots[i]
        src = by_id.get(s.get("window_of")) or s
        if (s.get("beat") != "chapter" or s["kind"] != "scene" or src.get("establishing")
                or (pc.speaking(src) and src["speaker"] == ch.GOD) or not _people(s, by_id)):
            problems.append(f"CLIMAX_NOT_ACTED shot {i} {s['id']} (a chapter scene with people on screen: not the "
                            "Keeper, a landscape or God's voice-over sky; E92)")
        said = [x for x in (s, shots[i - 1] if i else None) if x and pc.speaking(x) and x.get("reference")]
        if not said:
            problems.append(f"CLIMAX_NO_KJV_LINE shot {i} {s['id']} (the hero or God speaks the key KJV line at the "
                            "turn: this shot or the one before it)")
    if len(climax) == 1 and not a <= begin[climax[0]] / total <= b:
        problems.append(f"CLIMAX_POSITION {begin[climax[0]] / total:.2f} outside {a}-{b} of the runtime")
    pay = beat_shots("payoff")
    if not pay:
        problems.append("PAYOFF_MISSING (the outcome shown in one sequence after the climax)")
    elif climax and min(pay) < climax[0]:
        problems.append("PAYOFF_BEFORE_CLIMAX")

    # slow stretches: shots with no one on screen, or one voice run, longer than the limit
    slow, run = g["slow_stretch_max_s"], 0.0
    for i, s in enumerate(shots):
        run = run + hold[i] if not _people(s, by_id) else 0.0
        if run > slow + 1e-6:
            problems.append(f"SLOW_STRETCH shot {i} {s['id']} (~{run:.0f} s with no one on screen; <= {slow} s)")
            break
    for x, y, idx in pc.groups(shots, carried):
        if end[y] - begin[x] > slow + 1e-6 and not pc.speaking(shots[x]):
            problems.append(f"SLOW_STRETCH shot {x} {shots[x]['id']} (one voice run of ~{end[y] - begin[x]:.0f} s; "
                            f"<= {slow} s)")
            break
    est_seconds = sum(hold[i] for i, s in enumerate(shots) if s.get("establishing"))
    if est_seconds / total > pc.ESTABLISHING_SHARE_MAX:
        problems.append(f"ESTABLISHING_SHARE {est_seconds / total:.2f} > {pc.ESTABLISHING_SHARE_MAX}")

    # the frozen QA's speech rows on the estimate
    sp = q["speech"]
    first = []
    for k, x in enumerate(items):
        for n, w in enumerate(x["text"].split()):
            if start[k] + n / pace(x) <= sp["hook_second_person_within_seconds"]:
                first.append(w.lower().strip(".,!?;:\"'"))
    if not any(w in SECOND_PERSON for w in first):
        problems.append(f"HOOK_SECOND_PERSON (you/your inside {sp['hook_second_person_within_seconds']} s, story QA)")
    n_words = sum(pc.words(x["text"]) for x in items)
    wpm = n_words / (total / 60)
    w0, w1 = sp["accepted_words_per_minute"]
    if not w0 <= wpm <= w1:
        problems.append(f"WORDS_PER_MINUTE_EST {wpm:.0f} outside {w0}-{w1} (story QA)")
    presence = sum(est) / total
    if presence < sp["speech_presence_min"]:
        problems.append(f"SPEECH_PRESENCE_EST {presence:.3f} < {sp['speech_presence_min']} (story QA)")
    lo_m, hi_m = g["length_min"]
    if not lo_m <= total / 60 <= hi_m:
        problems.append(f"LONG_LENGTH {total / 60:.1f} min outside {lo_m}-{hi_m} (bible-story-long gate)")

    # the frozen QA's acted-long rows: v3 checks them; an older version's are the owner's (pending), never decided here
    gr = q["grammar"]
    figures = sum(hold[i] for i, s in enumerate(shots) if _people(s, by_id)) / total
    if gr.get("figure_present_fraction_max") is not None and figures > gr["figure_present_fraction_max"]:
        pending.append(f"QA_CONFLICT_FIGURES {figures:.2f} of the picture shows people > story QA "
                       f"figure_present_fraction_max {gr['figure_present_fraction_max']} (acted characters and the "
                       "Keeper on screen: owner decision, a new frozen QA version)")
    if gr.get("footage_picture_share_min", 0) > 0:
        pending.append(f"QA_CONFLICT_REAL_FOOTAGE 0.00 real licensed footage < story QA footage_picture_share_min "
                       f"{gr['footage_picture_share_min']} (every shot is Pavo: owner decision)")
    if gr.get("ai_video_picture_share_max", 1.0) < 1.0:
        pending.append(f"QA_CONFLICT_AI_SHARE 1.00 AI video > story QA ai_video_picture_share_max "
                       f"{gr['ai_video_picture_share_max']} (owner decision)")
    if gr.get("title_card_seconds"):
        pending.append(f"QA_CONFLICT_TITLE_CARD (story QA wants a {gr['title_card_seconds'][0]:g}-"
                       f"{gr['title_card_seconds'][1]:g} s title card as the first hold; the structure opens acted "
                       "and spoken at 0 s: owner decision)")
    for cid in sorted(drafts):
        pending.append(f"CHARACTER_PENDING {cid} ({(chars.get(cid) or {}).get('status')}): Claude reviews its "
                       "reference sheet and sets APPROVED with kept refs, by PR, before any generation")

    gens = [s for s in shots if s.get("window_of") is None]
    talk = [i for i, s in enumerate(shots) if s.get("window_of") is None and pc.talking(s)]
    god = [s for s in gens if pc.speaking(s) and s["speaker"] == ch.GOD]
    scenes = [s for s in gens if s["kind"] == "scene" and not pc.talking(s)]
    clip_seconds = sum(s.get("seconds") or 0 for s in scenes) + sum(
        pc.talk_need(sum(est[k] for k in carried[i]) + LONG_LINE_GAP * (len(carried[i]) - 1)) for i in talk)
    estimate = {"seconds": round(total, 1), "minutes": round(total / 60, 2), "keeper_share": round(share, 3),
                "cold_open_voice_s": round(cold_voice, 1), "cold_open_hold_s": round(cold_hold, 1),
                "climax_at": round(begin[climax[0]] / total, 3) if len(climax) == 1 else None,
                "rehooks": len(rehooks), "rehook_gap_max_s": round(gap, 1), "words": n_words,
                "words_per_minute": round(wpm, 1), "speech_presence": round(presence, 3),
                "figure_fraction": round(figures, 3), "holds": len(shots),
                "beats_s": {bt: round(beat_seconds(bt), 1) for bt in BEATS},
                "chapters": [{"id": c["id"], "short": c["short"], "start_s": round(min(
                    (begin[i] for i, s in enumerate(shots) if s.get("chapter") == c["id"]), default=0.0), 1)}
                    for c in chapters],
                "generations": {"scene": len(scenes) - len(god), "god": len(god), "talking": len(talk),
                                "windows": sum(len(v) for v in windows.values()), "total": len(gens)},
                "clip_seconds": clip_seconds,
                "pavo_minutes_sequential": round((len(scenes) * PAVO_SCENE_S + len(talk) * PAVO_TALK_S) / 60),
                "upscale_minutes_1440p": round(clip_seconds * UPSCALE_S_PER_CLIP_S / 60)}
    return {"problems": problems, "pending": pending, "estimate": estimate}


def frozen_qa_problem(path=QA):
    """None when story QA v3 is the frozen file (its pinned sha256), else the reason."""
    got = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return None if got == QA_SHA256 else f"QA_NOT_FROZEN {Path(path).name} sha256 {got}"


def main(argv):
    args = [a for a in argv[1:] if a != "--strict"]
    if len(args) != 1:
        raise SystemExit(__doc__)
    result = check(json.loads(Path(args[0]).read_text()))
    frozen = frozen_qa_problem()
    if frozen:
        result["problems"].append(frozen)
    print(json.dumps(dict(plan=args[0], **result), indent=1))
    if result["problems"] or ("--strict" in argv and result["pending"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
