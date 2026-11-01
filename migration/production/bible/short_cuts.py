#!/usr/bin/env python3
"""Shorts cut from a long-first long (owner, 2026-11-01; DECISIONS.md "Long-first, Shorts cut from the long", E259).

"It is much easier to crop an image already framed for the long into a Short than the inverse." A long-first long
(plan track buzzy-long, buzzy_long.py) keeps, bound to its master in the build report, a caption-free master and the
sentence timeline. A cuts spec (migration/production/bible/cuts/<long>.json, bible-cuts-v1) names ranges of it; each
becomes a 9:16 1080x1920 Short: the centre 9:16 column of the clean master (optional per-cut `x`, 0-1, the window's
centre across the frame), captions from the same sentences in the Short's own style (short_engine.build_ass), gain
only to -14 LUFS, faded edges.

A cut is refused when it starts or ends inside a spoken sentence (the owner's hard limit: no cut speech), when it is
under 20 s or over 179 s, or when it is not a coherent unit: it starts in the silence before a sentence start and ends
in the silence after a sentence end. Advice (never a refusal): open on a hook line, carry one beat, close on a KJV line
or the Keeper's insight.

Each cut is a new file: its record (episodes/<cut>.json, track buzzy-cut, `parent` = its long) carries no review; the
existing native review runs on the cut's own master (native-review.yml with plan = the cuts spec) and the session
reviewer writes its defect decision before publish-episode.yml. Nothing is generated, reviewed or published here.

usage: short_cuts.py check SPEC                      the spec against the long's report and plan (no media)
       short_cuts.py render SPEC CLEAN_MASTER OUT    every cut: OUT/<cut>.mp4 and OUT/<cut>.json (measured)
       short_cuts.py record SPEC CUT_JSON            a draft episodes/<cut>.json (no review) from a rendered cut
"""
import json
from pathlib import Path
import re
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "migration" / "publish"))
import buzzy_long  # noqa: E402
import compilation_long as cl  # noqa: E402
import short_engine  # noqa: E402

VERSION = "bible-cuts-v1"
TRACK = "buzzy-cut"
SPEC_PATH = re.compile(r"^migration/production/bible/cuts/([a-z0-9]+(?:-[a-z0-9]+)*)\.json$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CUT_SECONDS = (20.0, 179.0)       # publish_episode.CUT_SECONDS: YouTube Shorts end at 180 s
TOL = 0.02                        # the timeline's rounding (3 decimals) and the encoder's frame
FADE = 0.25
W, H = short_engine.W, short_engine.H
SERIES = "The Bible, story by story (KJV)"


def sources(spec, root=ROOT):
    """(plan, report) of the spec's long."""
    plan = cl.load(Path(root) / "migration/production/bible/plans" / f"{spec['long']}.json")
    return plan, cl.load(Path(root) / spec["report"])


def boundaries(sentences, start, end, total):
    """Problems of one range on the sentence timeline: it starts in the silence before a sentence (never inside one)
    and ends in the silence after one; (problems, first sentence index, last sentence index)."""
    out = []
    first = next((i for i, s in enumerate(sentences) if start <= s["start"] + TOL), None)
    if first is None or (first > 0 and start < sentences[first - 1]["end"] - TOL):
        out.append(f"CUT_STARTS_INSIDE_SPEECH at {start} s (start in the silence before a sentence)")
    last = next((i for i in range(len(sentences) - 1, -1, -1) if end >= sentences[i]["end"] - TOL), None)
    nxt = sentences[last + 1]["start"] if last is not None and last + 1 < len(sentences) else total
    if last is None or end > nxt + TOL:
        out.append(f"CUT_ENDS_INSIDE_SPEECH at {end} s (end in the silence after a sentence)")
    if not out and (first is None or last is None or last < first):
        out.append("CUT_HAS_NO_SENTENCE")
    return out, first, last


def advice(sentences, first, last):
    """The recommended shape: a hook line, one beat, then a KJV line or the Keeper's insight. Information only."""
    kinds = [s.get("line_kind") for s in sentences[first:last + 1]]
    tips = []
    if kinds and kinds[-1] not in ("scripture", "insight"):
        tips.append(f"ends on a {kinds[-1]} line: a KJV line or the Keeper's insight closes a cut best")
    if len({s.get("line") for s in sentences[first:last + 1]}) < 2:
        tips.append("one line only: a hook line and one beat read as a story")
    return tips


def check(spec, root=ROOT, spec_path=None):
    """{"problems": [...], "cuts": {id: {first, last, seconds, advice}}} of a cuts spec."""
    bad, out = [], {}
    if spec_path is not None:
        m = SPEC_PATH.fullmatch(spec_path)
        if not m or m.group(1) != spec.get("long"):
            bad.append("SPEC_PATH (migration/production/bible/cuts/<long episode>.json)")
    if spec.get("version") != VERSION or spec.get("track") != TRACK:
        return {"problems": bad + [f"SPEC_VERSION (need {VERSION}, track {TRACK})"], "cuts": out}
    if not isinstance(spec.get("long"), str) or not SLUG.fullmatch(spec["long"]):
        return {"problems": bad + ["LONG_ID"], "cuts": out}
    report_re = rf"migration/evidence/episodes/{re.escape(spec['long'])}/report-[0-9]+\.json"
    if not isinstance(spec.get("report"), str) or not re.fullmatch(report_re, spec["report"]):
        return {"problems": bad + ["REPORT_PATH (the long's build report on main)"], "cuts": out}
    try:
        plan, report = sources(spec, root)
    except (OSError, ValueError) as exc:
        return {"problems": bad + [f"LONG_UNREADABLE {type(exc).__name__}"], "cuts": out}
    if not buzzy_long.long_first(plan):
        bad.append("LONG_NOT_LONG_FIRST (the plan's track is not buzzy-long)")
    bad += [f"REPORT {p}" for p in buzzy_long.report_problems(plan, report)]
    if (plan.get("long") or {}).get("pilot") != spec.get("pilot"):
        bad.append("PILOT (the spec's pilot is the long's)")
    cuts = spec.get("cuts")
    if bad or not isinstance(cuts, list) or not cuts:
        return {"problems": bad + ([] if isinstance(cuts, list) and cuts else ["CUTS_MISSING"]), "cuts": out}
    sentences = report["composed"]["sentences"]
    total = report["composed"]["seconds"]
    seen = set()
    for c in cuts:
        cid = c.get("id") if isinstance(c, dict) else None
        if not isinstance(cid, str) or not SLUG.fullmatch(cid) or cid in seen or cid == spec["long"]:
            bad.append(f"CUT_ID {cid!r} (a new episode id, once)")
            continue
        seen.add(cid)
        start, end = c.get("start"), c.get("end")
        if type(start) not in (int, float) or type(end) not in (int, float) or not 0 <= start < end <= total:
            bad.append(f"CUT_RANGE {cid} (0 <= start < end <= {total})")
            continue
        x = c.get("x", 0.5)
        if type(x) not in (int, float) or not 0.0 <= x <= 1.0:
            bad.append(f"CUT_X {cid} (0-1, the 9:16 window's centre across the frame)")
        if not CUT_SECONDS[0] <= end - start <= CUT_SECONDS[1]:
            bad.append(f"CUT_LENGTH {cid} {end - start:.2f} s ({CUT_SECONDS[0]:.0f}-{CUT_SECONDS[1]:.0f})")
        found, first, last = boundaries(sentences, start, end, total)
        bad += [f"{p.split()[0]} {cid} {' '.join(p.split()[1:])}" for p in found]
        if not found:
            out[cid] = {"first": first, "last": last, "seconds": round(end - start, 3),
                        "advice": advice(sentences, first, last)}
        for k in ("title", "description"):
            if not isinstance(c.get(k), str) or not c[k].strip():
                bad.append(f"CUT_{k.upper()} {cid}")
    return {"problems": bad, "cuts": out}


def window(x):
    """The 9:16 crop of a 16:9 frame, its centre at x of the width, kept inside the frame."""
    return f"crop=ih*9/16:ih:(iw-ih*9/16)*{min(max(float(x), 0.0), 1.0):.4f}:0"


def cut_sentences(sentences, first, last, start):
    return [dict(s, start=round(s["start"] - start, 3), end=round(s["end"] - start, 3))
            for s in sentences[first:last + 1]]


def render(spec_path, clean, out_dir, root=ROOT):
    spec = cl.load(spec_path)
    result = check(spec, root)
    cl.refuse(result["problems"])
    plan, report = sources(spec, root)
    want = report["composed"]["clean"]["output_sha256"]
    if cl.sha256(clean) != want:
        raise SystemExit("CLEAN_MASTER_SHA256_MISMATCH")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sentences = report["composed"]["sentences"]
    done = []
    for c in spec["cuts"]:
        info = result["cuts"][c["id"]]
        start, end = float(c["start"]), float(c["end"])
        d = end - start
        mp4 = out / f"{c['id']}.mp4"
        lines = cut_sentences(sentences, info["first"], info["last"], start)
        with tempfile.TemporaryDirectory() as tmp:
            seg = Path(tmp) / "segment.mov"   # the exact range, re-encoded (frame-accurate), audio kept lossless
            cl.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", clean, "-t", f"{d:.3f}",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-c:a", "pcm_s16le", "-ar", "48000", seg])
            ass = Path(tmp) / "captions.ass"
            ass.write_text(short_engine.build_ass(lines))
            v, a = cl.fades(d)
            graph = (f"[0:v]{window(c.get('x', 0.5))},scale={W}:{H}:flags=lanczos,setsar=1,subtitles={ass},{v}[v];"
                     f"[0:a]aresample=48000,aformat=channel_layouts=stereo,{cl.gain_filter(seg)},{a}[a]")
            cl.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", seg, "-filter_complex", graph, "-map", "[v]",
                    "-map", "[a]", "-t", f"{d:.3f}", *cl.ENC, mp4])
        lufs, peak = cl.loudness(mp4)
        probe = short_engine_probe(mp4)
        sha = cl.sha256(mp4)
        rec = {"version": "bible-cut-v1", "id": c["id"], "spec": str(spec_path),
               "parent": {"long": spec["long"], "pilot": spec["pilot"], "report": spec["report"],
                          "clean_master_sha256": want, "start": start, "end": end, "x": c.get("x", 0.5)},
               "output_sha256": sha, "seconds": round(cl.duration(mp4), 3), "frame": [probe[0], probe[1]],
               "lufs": lufs, "true_peak_dbfs": peak, "sentences": lines, "advice": info["advice"],
               "checks": {"frame_1080x1920": probe == (W, H), "lufs_band": cl.LUFS_BAND[0] <= lufs <= cl.LUFS_BAND[1],
                          "true_peak_ceiling": peak <= cl.TRUE_PEAK_MAX,
                          "length": abs(cl.duration(mp4) - d) < 0.2}}
        cl.save(out / f"{c['id']}.json", rec)
        done.append({k: rec[k] for k in ("id", "output_sha256", "seconds", "lufs", "advice")})
        if not all(rec["checks"].values()):
            raise SystemExit(f"CUT_QA_FAILED {c['id']} {rec['checks']}")
    print(json.dumps(done, indent=1))
    return done


def short_engine_probe(path):
    p = json.loads(cl.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                           "-of", "json", path]).stdout)["streams"][0]
    return p["width"], p["height"]


def narration(sentences):
    """The cut's words, one entry per line of the long (kind from the plan's line; KJV lines keep their reference)."""
    out = []
    for s in sentences:
        if out and out[-1]["line"] == s.get("line"):
            out[-1]["text"] += " " + s["text"]
            continue
        out.append({"line": s.get("line"), "kind": s.get("line_kind"), "text": s["text"],
                    **({"reference": s["reference"]} if s.get("reference") else {}),
                    **({"speaker": s["speaker"]} if s.get("speaker") else {})})
    return [{k: v for k, v in x.items() if k != "line"} for x in out]


def record(spec_path, cut_json, root=ROOT):
    """A draft Short episode record of a rendered cut (no review: the native review of this file and the session
    reviewer's defect decision come next)."""
    spec, cut = cl.load(spec_path), cl.load(cut_json)
    cl.refuse(check(spec, root)["problems"])
    c = next((x for x in spec["cuts"] if x["id"] == cut.get("id")), None)
    if c is None or cut.get("parent", {}).get("long") != spec["long"]:
        raise SystemExit("CUT_NOT_IN_SPEC")
    plan, _ = sources(spec, root)
    words = narration(cut["sentences"])
    rec = {"version": "bible-episode-v1", "id": c["id"], "series": SERIES, "part": plan.get("part"),
           "passage": plan.get("passage"), "format": "short", "track": TRACK,
           "parent": {k: cut["parent"][k] for k in ("long", "pilot", "clean_master_sha256", "start", "end")},
           "output_sha256": cut["output_sha256"], "seconds": cut["seconds"], "frame": cut["frame"],
           "narration": words, "scripture": [{"reference": w["reference"], "text": w["text"]} for w in words
                                             if w.get("kind") == "scripture" and w.get("reference")],
           "title": c["title"], "description": c["description"], "tags": c.get("tags") or [], "category_id": "29",
           "first_comment": c.get("first_comment", ""), "credits": {"vidiq": 0, "pavo": 0},
           **({"slot": c["slot"]} if c.get("slot") else {})}
    path = Path(root) / "migration/production/bible/episodes" / f"{c['id']}.json"
    if path.exists() and cl.load(path).get("output_sha256") not in (None, rec["output_sha256"]):
        raise SystemExit("RECORD_EXISTS_FOR_ANOTHER_FILE (a new file is a new review; archive the old record first)")
    cl.save(path, rec)
    return path


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "check" and len(argv) == 3:
        result = check(cl.load(argv[2]), spec_path=argv[2])
        print(json.dumps(result, indent=1))
        return 1 if result["problems"] else 0
    if cmd == "render" and len(argv) == 5:
        render(*argv[2:5])
    elif cmd == "record" and len(argv) == 4:
        print(record(*argv[2:4]))
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
