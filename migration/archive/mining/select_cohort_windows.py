#!/usr/bin/env python3
"""Pick audiovisual windows to mine a format from today's raw panel: for each
given channel, the winner, median and weak long uploads (>= 8 min, 2-30 days
old, ranked by views per day), each with its opening 0-40 s; the winner also
gets a middle window (structure of the body). Output: the windows string for
acquire-reference-window.yml (max 12) and a JSON plan with the cohort labels.
usage: select_cohort_windows.py RAW_PANEL OUT_JSON CHANNEL_ID...
"""
from datetime import datetime
import json
from pathlib import Path
import sys

MAX_WINDOWS = 12


def main(raw, out, channel_ids):
    panel = json.loads(Path(raw).read_text())
    now = datetime.fromisoformat(panel["captured_at"].replace("Z", "+00:00"))
    by_id = {c["channel_id"]: c for c in panel["channels"]}
    plan, windows = [], []
    for cid in channel_ids:
        c = by_id.get(cid)
        if not c or not c.get("uploads"):
            plan.append({"channel_id": cid, "status": "NO_UPLOADS_IN_PANEL"})
            continue
        vids = []
        for u in c["uploads"]:
            age = (now - datetime.fromisoformat(u["published_at"].replace("Z", "+00:00"))).total_seconds() / 86400
            if 2 <= age <= 30 and (u["duration_seconds"] or 0) >= 480:
                vids.append(dict(u, views_per_day=u["views"] / age))
        vids.sort(key=lambda v: v["views_per_day"], reverse=True)
        if len(vids) < 3:
            plan.append({"channel_id": cid, "title": c["title"], "status": "FEWER_THAN_3_ELIGIBLE", "eligible": len(vids)})
            continue
        picks = {"WINNER": vids[0], "MEDIAN": vids[len(vids) // 2], "WEAK": vids[-1]}
        for label, v in picks.items():
            windows.append(f"{v['video_id']}:0:40")
            entry = {"channel_id": cid, "channel": c["title"], "cohort": label, "video_id": v["video_id"],
                     "title": v["title"], "minutes": round(v["duration_seconds"] / 60, 1),
                     "views_per_day": round(v["views_per_day"], 1), "windows": ["0:40"]}
            if label == "WINNER":
                mid = int(v["duration_seconds"] * 0.45) // 10 * 10
                windows.append(f"{v['video_id']}:{mid}:{mid + 40}")
                entry["windows"].append(f"{mid}:{mid + 40}")
            plan.append(entry)
    windows = windows[:MAX_WINDOWS]
    Path(out).write_text(json.dumps({"version": "cohort-windows-v1", "panel": panel["captured_at"],
                                     "windows": ";".join(windows), "plan": plan}, indent=1, ensure_ascii=False) + "\n")
    print(";".join(windows))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
