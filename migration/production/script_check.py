#!/usr/bin/env python3
"""Deterministic acceptance of a pilot written by the executor (Dot) before Claude merges it (migration/ops/DOT_PROTOCOL.md).
It replaces reading 4,000 words with checks that never change after results: files and frozen QA criteria, required
fields, estimated length per format, estimated speech presence (frozen QA floor 0.85, target >= 0.86), Scripture per
10 min (>= 4, KJV marked), policy wording, originality against every other pilot (no shared 12-word run outside
Scripture), schedule slot, and images. Prints PASS or FAIL with every problem; exit 0 only on PASS.
usage: script_check.py PILOT_DIR [PRODUCTION_DIR]
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "publish"))
import three_stage  # noqa: E402; approval owns the shared image-overlap limit

FROZEN_QA = "49fedd2e5ebf525e38dab1e5135124d31f8ce822f71f3a02c61c702d2da8790d"
WPM = 140                    # Kokoro narration measured on pilots 002-004 (QA ASR 132.7-141)
RESIDUAL_GAP = 0.067         # non-speech share inside spoken time, measured on the 003/004 renders
SPEECH_MIN = 0.86
BACKGROUNDS_MIN = 18  # E46/E48
BANDS = {"morning": (22, 32), "night": (25, 38)}  # minutes; DECISIONS D-01/D-04, registered strategy 25-40
REQUIRED = ("version", "pilot_id", "archetype", "spec", "working_title", "promise", "angle", "authorship", "voice",
            "segments", "figure", "backgrounds", "overlay", "description_intro", "hashtags", "thumbnail", "tags",
            "figure_choice", "playlist", "motion", "cinematic")
# fear-bait wording is judged on the packaging (title, description); promises anywhere in the text
RISK = re.compile(r"(?i)prophec|warning|hiding from you|they don.?t want you|before it.?s too late|don.?t ignore|"
                  r"is here!|exposed|banned|last chance")
PROMISE = re.compile(r"(?i)guarantee|you will be healed|instantly healed|money will come|get rich|miracle money")
FORMULA = ("stillness", "cta", "blessing")   # channel formulas (breathing guide, call to action, closing blessing)
# modeling (strategy/MODELING_SPEC.md section 1, beat order): the promise is spoken by 8 s, the first prayer
# starts by 1:30, the CTA comes only after the payoff
HOOK_MAX_WORDS = 20          # 8.6 s at WPM
FIRST_PRAYER_MAX_S = 90
SHINGLE = 12
MAX_SHARED = 3


def words(t):
    return re.findall(r"[a-z']+", t.lower())


def shingles(segments):
    out = set()
    for s in segments:
        if s.get("reference") or s.get("id", "").startswith(FORMULA):  # Scripture verbatim; channel formulas
            continue
        w = words(s["text"])
        out |= {" ".join(w[i:i + SHINGLE]) for i in range(len(w) - SHINGLE + 1)}
    return out


def check(pilot_dir, production=None):
    d = Path(pilot_dir)
    production = Path(production) if production else d.parent
    problems = []
    for f in ("script.json", "images.json", "schedule.json", "qa_criteria.json"):
        if not (d / f).exists():
            problems.append(f"MISSING {f}")
    if problems:
        return problems, {}
    if hashlib.sha256((d / "qa_criteria.json").read_bytes()).hexdigest() != FROZEN_QA:
        problems.append("QA_CRITERIA_NOT_THE_FROZEN_FILE")
    s = json.loads((d / "script.json").read_text())
    problems += [f"FIELD_MISSING {k}" for k in REQUIRED if k not in s]
    if s.get("pilot_id") != d.name:
        problems.append(f"PILOT_ID {s.get('pilot_id')} != {d.name}")
    segs = s.get("segments", [])
    ids = [x.get("id") for x in segs]
    if not segs or ids[0] != "hook":
        problems.append("FIRST_SEGMENT_NOT_HOOK")
    if len(set(ids)) != len(ids):
        problems.append("DUPLICATE_SEGMENT_ID")
    for x in segs:
        if not x.get("text", "").strip():
            problems.append(f"EMPTY_TEXT {x.get('id')}")
        if not 0.5 <= float(x.get("pause_after", 0)) <= (8.0 if x.get("id", "").startswith("stillness") else 4.0):
            problems.append(f"PAUSE_OUT_OF_RANGE {x.get('id')} {x.get('pause_after')}")
        if x.get("reference") and not x["reference"].endswith("(KJV)"):
            problems.append(f"REFERENCE_NOT_KJV {x.get('id')}")
    n_words = sum(len(words(x.get("text", ""))) for x in segs)
    pauses = sum(float(x.get("pause_after", 0)) for x in segs)
    spoken = n_words / WPM * 60
    minutes = (spoken + pauses) / 60
    speech = spoken * (1 - RESIDUAL_GAP) / (spoken + pauses) if spoken else 0
    title = s.get("working_title", "")
    fmt = "night" if re.search(r"(?i)night|sleep", title) else "morning"
    lo, hi = BANDS[fmt]
    if not lo <= minutes <= hi:
        problems.append(f"LENGTH {minutes:.1f} min outside {fmt} band {lo}-{hi}")
    if speech < SPEECH_MIN:
        problems.append(f"SPEECH_PRESENCE_EST {speech:.3f} < {SPEECH_MIN}")
    if segs and ids[0] == "hook" and len(words(segs[0].get("text", ""))) > HOOK_MAX_WORDS:
        problems.append(f"HOOK_TOO_LONG {len(words(segs[0].get('text', '')))} words > {HOOK_MAX_WORDS} (promise spoken by 8 s)")
    t, first_prayer = 0.0, None
    for x in segs:
        if x.get("id", "").startswith("prayer"):
            first_prayer = t
            break
        t += len(words(x.get("text", ""))) / WPM * 60 + float(x.get("pause_after", 0))
    if first_prayer is None or first_prayer > FIRST_PRAYER_MAX_S:
        problems.append(f"FIRST_PRAYER_LATE {'none' if first_prayer is None else f'{first_prayer:.0f} s'} > {FIRST_PRAYER_MAX_S} s")
    if "payoff" not in ids or "cta" not in ids:
        problems.append("PAYOFF_OR_CTA_MISSING")
    elif ids.index("cta") < ids.index("payoff"):
        problems.append("CTA_BEFORE_PAYOFF")
    refs = sum(1 for x in segs if x.get("reference"))
    per10 = refs / max(minutes, 1e-6) * 10
    if per10 < 4:
        problems.append(f"SCRIPTURE_PER_10_MIN {per10:.1f} < 4")
    if len(title) > 100:
        problems.append("TITLE_OVER_100_CHARS")
    packaging = " ".join([title, s.get("description_intro", "")])
    body = " ".join([packaging] + [x.get("text", "") for x in segs])  # every segment: a promise must not hide in a reading
    hits = sorted({m.group(0).lower() for m in RISK.finditer(packaging)} | {m.group(0).lower() for m in PROMISE.finditer(body)})
    if hits:
        problems.append(f"POLICY_WORDING {hits}")
    if len(",".join(s.get("tags", []))) > 450:
        problems.append("TAGS_TOO_LONG")
    # a long video needs enough distinct backgrounds: 12 for 28 min scored pacing 6.5, "a small loop of recurring
    # images" (pilot-008 review 2026-10-20, E48); 18 also keeps REPEAT_GAP with 18 s split holds (E46)
    if len(set(s.get("backgrounds", []))) < BACKGROUNDS_MIN:
        problems.append(f"TOO_FEW_BACKGROUNDS {len(set(s.get('backgrounds', [])))} < {BACKGROUNDS_MIN}")
    mine = shingles(segs)
    backgrounds = set(s.get("backgrounds", []))
    image_comparisons = []
    for other in sorted(production.glob("pilot-[0-9][0-9][0-9]/script.json")):
        if other.parent.name == d.name:
            continue
        other_script = json.loads(other.read_text())
        other_backgrounds = set(other_script.get("backgrounds", []))
        union = backgrounds | other_backgrounds
        overlap = len(backgrounds & other_backgrounds) / max(1, len(union))
        image_comparisons.append({"pilot": other.parent.name, "jaccard": overlap})
        if overlap > three_stage.IMAGE_SHARE_MAX:
            problems.append(f"image_set_overlap vs {other.parent.name}: {overlap:.6f} > {three_stage.IMAGE_SHARE_MAX}")
        shared = mine & shingles(other_script.get("segments", []))
        if len(shared) > MAX_SHARED:
            problems.append(f"NOT_ORIGINAL vs {other.parent.name}: {len(shared)} shared {SHINGLE}-word runs")
    sch = json.loads((d / "schedule.json").read_text())
    at = sch.get("publish_at", "")
    try:
        t = datetime.fromisoformat(at.replace("Z", "+00:00"))
        if t <= datetime.now(timezone.utc):
            problems.append("PUBLISH_AT_IN_THE_PAST")
        if (fmt, t.hour) not in (("morning", 10), ("night", 0)):
            problems.append(f"SLOT {fmt} at {t:%H:%M} UTC (morning 10:00, night 00:00)")
    except ValueError:
        problems.append("PUBLISH_AT_INVALID")
    for other in production.glob("pilot-[0-9][0-9][0-9]/schedule.json"):
        if other.parent.name != d.name and json.loads(other.read_text()).get("publish_at") == at:
            problems.append(f"SLOT_TAKEN by {other.parent.name}")
    # one Short per long video goes at the pilot's first Shorts slot: night pilot of day D at D 14:00 UTC, morning
    # pilot of day D at D 20:00 UTC, so two pilots never put their Short at the same minute
    first = (sch.get("shorts_slots") or [None])[0]
    for other in production.glob("pilot-[0-9][0-9][0-9]/schedule.json"):
        if first and other.parent.name != d.name and (json.loads(other.read_text()).get("shorts_slots") or [None])[0] == first:
            problems.append(f"SHORTS_SLOT_TAKEN {first} by {other.parent.name}")
    img = json.loads((d / "images.json").read_text())
    planned = {x.get("id") for x in img.get("images", []) if isinstance(x, dict)}
    for ids in (img.get("reused") or {}).values():
        planned |= set(ids if isinstance(ids, list) else [])
    have = {p.stem for p in (d / "images").glob("*.json")} if (d / "images").exists() else set()
    for b in s.get("backgrounds", []) + [s.get("figure")]:
        if b and b not in planned | have:
            problems.append(f"IMAGE_NOT_PLANNED {b}")
    for source, ids in (img.get("reused") or {}).items():
        for i in ids if isinstance(ids, list) else []:
            if i not in have:   # the render reads records from the pilot's own images/ folder
                problems.append(f"REUSED_NOT_HYDRATED {source}/{i} (run imagegen/hydrate_reused.py)")
    new = [x.get("id") for x in img.get("images", []) if isinstance(x, dict) and x.get("id") not in have]
    if len(new) > 12:
        problems.append(f"TOO_MANY_NEW_IMAGES {len(new)} > 12 (Cloudflare free day)")
    stats = {"format": fmt, "words": n_words, "minutes_est": round(minutes, 1), "speech_presence_est": round(speech, 3),
             "scripture_per_10_min": round(per10, 1), "new_images": len(new)}
    stats["image_set_overlap"] = {
        "status": "FAIL" if any(r["jaccard"] > three_stage.IMAGE_SHARE_MAX for r in image_comparisons) else "PASS",
        "limit": three_stage.IMAGE_SHARE_MAX, "comparisons": image_comparisons,
    }
    return problems, stats


if __name__ == "__main__":
    probs, stats = check(*sys.argv[1:3])
    print(json.dumps({"result": "FAIL" if probs else "PASS", "stats": stats, "problems": probs}, indent=1))
    sys.exit(1 if probs else 0)
