#!/usr/bin/env python3
"""Accuracy of the model-reported structure mining against native audio.

For every acquired native window (acquisition/profiles/acq-VIDEO-START-END-v1.json,
whose sound_classes.transcript is our own ASR of the original audio) that falls
inside a mined video, compare:
  * transcript agreement: word-sequence similarity between the mined transcript
    lines of that window and our ASR text (1.0 = identical word order);
  * opening-words agreement: share of mined beats starting in the window whose
    opening_words_verbatim are found, in order, in our ASR text.
Writes accuracy.json next to the structure records; the agreement rate is what
MODELING_SPEC.md cites before treating the mining as measured.
usage: accuracy_check.py STRUCTURE_DIR PROFILES_DIR [HOLDOUT_JSON]
       accuracy_check.py --pick STRUCTURE_DIR [N]   (prints N windows "VIDEO:START:END;..." to acquire)
"""
from difflib import SequenceMatcher
import glob
import json
from pathlib import Path
import re
import statistics
import sys

NAME = re.compile(r"acq-(.+)-(\d+)-(\d+)-v\d+\.json$")


def words(text):
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def found_in(needle, hay):
    n = words(needle)
    if not n or not hay:
        return False
    m = SequenceMatcher(None, hay, n, autojunk=False)
    return sum(b.size for b in m.get_matching_blocks()) / len(n) >= 0.8


def records(structure_dir):
    out = {}
    for f in glob.glob(str(Path(structure_dir) / "structure-*.json")):
        r = json.load(open(f))
        out[r["video"]["video_id"]] = r
    return out


# criteria fixed before the independent (holdout) evaluation; never lowered to fit results
AGREEMENT_MIN = 0.85      # per window: word-sequence similarity between mined transcript and our ASR
OPENINGS_MIN = 0.80       # share of mined opening phrases found in our ASR
WINDOW_PASS_RATE_MIN = 0.80  # share of speech windows that are COMPARED and >= AGREEMENT_MIN (errors count as failures)
SPEECH_WORDS = 10         # fewer ASR words than this in 30 s = no speech to compare


def covering(windows, start, end):
    """The mined window(s) that contain the acquired range; lines are never borrowed from other windows."""
    return [w for w in windows if w["window_start_seconds"] - 1 <= start and end <= w["window_end_seconds"] + 1] or \
           [w for w in windows if w["window_start_seconds"] < end and start < w["window_end_seconds"]]


def classify(windows, start, end, asr):
    """One acquired window -> status and measures. Statuses: COMPARED, MINED_WINDOW_INVALID, MINED_OMISSION,
    ASR_SILENT_MINED_SPEECH (a conflict), NO_SPEECH (both silent). Only COMPARED carries an agreement value."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from structure_mining import transcript_problems
    cover = covering(windows, start, end)
    if not cover:
        return {"status": "MINED_WINDOW_MISSING"}
    problems = sorted({p for w in cover for p in transcript_problems(w, w["window_start_seconds"], w["window_end_seconds"])})
    if problems:
        return {"status": "MINED_WINDOW_INVALID", "problems": problems}
    mined = [t for w in cover for t in w.get("transcript", []) if start <= t["start_seconds"] < end]
    mined_words = words(" ".join(t["text"] for t in mined))
    if len(asr) < SPEECH_WORDS:
        return {"status": "ASR_SILENT_MINED_SPEECH" if len(mined_words) >= SPEECH_WORDS else "NO_SPEECH",
                "asr_words": len(asr), "mined_words": len(mined_words)}
    if not mined_words:
        return {"status": "MINED_OMISSION", "asr_words": len(asr)}
    beats = [b for w in cover for b in w.get("beats", [])
             if start <= b["start_seconds"] < end - 3 and b.get("opening_words_verbatim") not in (None, "", "UNKNOWN")]
    hits = [found_in(b["opening_words_verbatim"], asr) for b in beats]
    return {"status": "COMPARED", "asr_words": len(asr), "mined_words": len(mined_words),
            "transcript_agreement": round(SequenceMatcher(None, mined_words, asr, autojunk=False).ratio(), 3),
            "openings_checked": len(hits), "openings_found": sum(hits),
            "examples": [{"mined": b["opening_words_verbatim"], "found": h} for b, h in zip(beats, hits)][:4]}


def summarise(rows):
    speech = [r for r in rows if r["status"] != "NO_SPEECH"]
    done = [r for r in rows if r["status"] == "COMPARED"]
    checked = sum(r["openings_checked"] for r in done)
    passing = [r for r in done if r["transcript_agreement"] >= AGREEMENT_MIN]
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    out = {"windows": len(rows), "speech_windows": len(speech), "status_counts": counts,
           "transcript_agreement_median": round(statistics.median([r["transcript_agreement"] for r in done]), 3) if done else None,
           "transcript_agreement_min": min((r["transcript_agreement"] for r in done), default=None),
           "window_pass_rate": round(len(passing) / len(speech), 3) if speech else None,
           "opening_words_agreement": round(sum(r["openings_found"] for r in done) / checked, 3) if checked else None,
           "openings_checked": checked,
           "criteria": {"agreement_min": AGREEMENT_MIN, "openings_min": OPENINGS_MIN, "window_pass_rate_min": WINDOW_PASS_RATE_MIN}}
    if not speech:
        out["verdict"] = "UNKNOWN"          # nothing to compare is not evidence either way
    elif out["window_pass_rate"] < WINDOW_PASS_RATE_MIN or (checked and out["opening_words_agreement"] < OPENINGS_MIN):
        out["verdict"] = "FAIL"
    elif not checked:
        out["verdict"] = "UNKNOWN"          # transcripts pass but no opening phrase could be checked
    else:
        out["verdict"] = "PASS"
    return out


def check(structure_dir, profiles_dir, holdout=None):
    recs = records(structure_dir)
    rows = []
    for f in sorted(glob.glob(str(Path(profiles_dir) / "acq-*.json"))):
        m = NAME.search(Path(f).name)
        if not m or m.group(1) not in recs:
            continue
        vid, start, end = m.group(1), int(m.group(2)), int(m.group(3))
        asr = words((json.load(open(f))["profiles"][0].get("sound_classes") or {}).get("transcript", ""))
        rows.append({"video_id": vid, "window": [start, end], **classify(recs[vid]["windows"], start, end, asr)})
    tuning = set(json.loads(Path(holdout).read_text()).get("tuning_windows", [])) if holdout and Path(holdout).exists() else set()
    for r in rows:
        r["set"] = "tuning" if f"{r['video_id']}:{r['window'][0]}:{r['window'][1]}" in tuning else "holdout"
    result = {"version": "mining-accuracy-v2", "structure_dir": str(structure_dir), "all": summarise(rows),
              "holdout": summarise([r for r in rows if r["set"] == "holdout"]),
              "tuning": summarise([r for r in rows if r["set"] == "tuning"]), "windows": rows,
              "reading": "verdict on the holdout set only; tuning windows were used to find defects and prove nothing"}
    (Path(structure_dir) / "accuracy.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: result[k][kk] for k in ("all", "holdout", "tuning") for kk in ("verdict",)}),
          json.dumps({k: {kk: result[k][kk] for kk in ("speech_windows", "status_counts", "window_pass_rate", "opening_words_agreement")}
                      for k in ("holdout", "tuning")}))


def pick(structure_dir, n=12):
    """Openings (0-30 s) of a third of the videos, mid-video beats of the rest; 30 s each, one per video,
    skipping videos an earlier accuracy run already compared (daily runs add new evidence only)."""
    done = set()  # videos already used (tuning or an earlier run): holdout windows come from other videos only
    for f in glob.glob(str(Path(structure_dir).parent / "*" / "accuracy.json")):
        done |= {w["video_id"] for w in json.load(open(f)).get("windows", [])}
    reg = Path(structure_dir).parent.parent / "mining-accuracy-holdout.json"
    if reg.exists():
        done |= {w.split(":")[0] for w in json.loads(reg.read_text()).get("tuning_windows", [])}
    picks = []
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from blueprint_stats import BORROWED
    clean = [(v, r) for v, r in sorted(records(structure_dir).items()) if not BORROWED.search(r["video"]["title"])
             and ((r.get("measured") or {}).get("speech") or {}).get("words_per_minute", 0) >= 40]  # narrated only
    clean = [(v, r) for v, r in clean if v not in done]
    for i, (vid, r) in enumerate(clean):
        beats = [b for w in r["windows"] for b in w.get("beats", []) if b.get("opening_words_verbatim") not in (None, "", "UNKNOWN")]
        if not beats:
            continue
        mid = [b for b in beats if b["start_seconds"] >= 90]
        b = beats[0] if i % 3 == 0 or not mid else mid[len(mid) // 2]
        s = max(0, int(b["start_seconds"]) - 2)
        picks.append(f"{vid}:{s}:{s + 30}")
    return ";".join(picks[: int(n)])


if __name__ == "__main__":
    if sys.argv[1] == "--pick":
        print(pick(*sys.argv[2:4]))
    else:
        check(*sys.argv[1:4])
