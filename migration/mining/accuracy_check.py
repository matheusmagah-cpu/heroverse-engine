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
usage: accuracy_check.py STRUCTURE_DIR PROFILES_DIR
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


def check(structure_dir, profiles_dir):
    recs = records(structure_dir)
    rows = []
    for f in sorted(glob.glob(str(Path(profiles_dir) / "acq-*.json"))):
        m = NAME.search(Path(f).name)
        if not m or m.group(1) not in recs:
            continue
        vid, start, end = m.group(1), int(m.group(2)), int(m.group(3))
        prof = json.load(open(f))["profiles"][0]
        asr = words((prof.get("sound_classes") or {}).get("transcript", ""))
        windows = recs[vid]["windows"]
        mined = [t for w in windows for t in w.get("transcript", []) if start <= t["start_seconds"] < end]
        beats = [b for w in windows for b in w.get("beats", [])
                 if start <= b["start_seconds"] < end - 3 and b.get("opening_words_verbatim") not in (None, "", "UNKNOWN")]
        mined_words = words(" ".join(t["text"] for t in mined))
        if not asr or not mined_words:
            rows.append({"video_id": vid, "window": [start, end], "status": "NO_SPEECH_TO_COMPARE",
                         "asr_words": len(asr), "mined_words": len(mined_words)})
            continue
        sim = SequenceMatcher(None, mined_words, asr, autojunk=False).ratio()
        hits = [found_in(b["opening_words_verbatim"], asr) for b in beats]
        rows.append({"video_id": vid, "window": [start, end], "status": "COMPARED", "asr_words": len(asr),
                     "mined_words": len(mined_words), "transcript_agreement": round(sim, 3),
                     "openings_checked": len(hits), "openings_found": sum(hits),
                     "examples": [{"mined": b["opening_words_verbatim"], "found": h} for b, h in zip(beats, hits)][:4]})
    done = [r for r in rows if r["status"] == "COMPARED"]
    checked = sum(r["openings_checked"] for r in done)
    result = {"version": "mining-accuracy-v1", "structure_dir": str(structure_dir), "windows_compared": len(done),
              "transcript_agreement_median": round(statistics.median([r["transcript_agreement"] for r in done]), 3) if done else None,
              "transcript_agreement_min": min((r["transcript_agreement"] for r in done), default=None),
              "opening_words_agreement": round(sum(r["openings_found"] for r in done) / checked, 3) if checked else None,
              "openings_checked": checked, "windows": rows,
              "reading": "agreement >= 0.85 and openings >= 0.8: mined structure usable as measured; below: model-reported only"}
    (Path(structure_dir) / "accuracy.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: result[k] for k in ("windows_compared", "transcript_agreement_median", "opening_words_agreement")}))


def pick(structure_dir, n=12):
    """Openings (0-30 s) of a third of the videos, mid-video beats of the rest; 30 s each, one per video,
    skipping videos an earlier accuracy run already compared (daily runs add new evidence only)."""
    done = set()
    for f in glob.glob(str(Path(structure_dir).parent / "*" / "accuracy.json")):
        done |= {w["video_id"] for w in json.load(open(f)).get("windows", []) if w.get("status") == "COMPARED"}
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
        check(*sys.argv[1:3])
