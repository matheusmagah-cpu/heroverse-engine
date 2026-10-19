#!/usr/bin/env python3
"""Retry the channel's first comment on a published video (SYSTEM.md stage 5).

publish_video.py records steps.first_comment = "PENDING: <reason>" when YouTube
refuses the comment (scope, comments disabled, or the video still private or
scheduled). This posts it once the video is public: it checks the exact
channel, reads the video's privacy, and only then calls commentThreads.insert.
A comment already recorded (an id) is never posted again, and a comment of the
channel with the same text already on the video is recorded instead of posted.
The receipt (and the ledger, when given) gets the comment id, or a new PENDING
reason. Pinning is manual: the API cannot pin a comment.
Exit 0 = posted or already posted; 3 = still pending.
usage: first_comment.py VIDEO_ID TEXT RECEIPT [LEDGER]
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_video as pv  # noqa: E402


def main(video_id, text, receipt_path, ledger_path=None):
    receipt_path = Path(receipt_path)
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("video_id") != video_id:
        raise SystemExit(f"RECEIPT_VIDEO_MISMATCH {receipt.get('video_id')} != {video_id}")
    steps = receipt.setdefault("steps", {})
    if pv.comment_done(steps.get("first_comment")):
        print(json.dumps({"video_id": video_id, "first_comment": steps["first_comment"], "status": "ALREADY_POSTED"}))
        return 0
    s = pv.session()
    if [c["id"] for c in pv.check(s.get(pv.API + "channels", params={"part": "id", "mine": "true"}), "CHANNEL")["items"]] != [pv.CHANNEL]:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")
    items = pv.check(s.get(pv.API + "videos", params={"part": "status", "id": video_id}), "VIDEO")["items"]
    if not items:
        raise SystemExit("VIDEO_NOT_FOUND " + video_id)
    status = items[0]["status"]
    if status.get("privacyStatus") != "public":
        result = (f"PENDING: video not public yet (privacy={status.get('privacyStatus')}, "
                  f"publishAt={status.get('publishAt')})")
    else:
        result = pv.first_comment(s, video_id, text)
    steps["first_comment"] = result
    receipt["first_comment_checked_at"] = datetime.now(timezone.utc).isoformat()
    receipt_path.write_text(json.dumps(receipt, indent=1) + "\n")
    if ledger_path and Path(ledger_path).exists():  # keep publish_video.py from posting it a second time
        ledger = json.loads(Path(ledger_path).read_text())
        for entry in ledger.get("entries", {}).values():
            if entry.get("video_id") == video_id:
                entry.setdefault("steps", {})["first_comment"] = result
        Path(ledger_path).write_text(json.dumps(ledger, indent=1) + "\n")
    done = pv.comment_done(result)
    print(json.dumps({"video_id": video_id, "first_comment": result, "status": "POSTED" if done else "PENDING"}))
    return 0 if done else 3


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        raise SystemExit(__doc__)
    sys.exit(main(*sys.argv[1:5]))
