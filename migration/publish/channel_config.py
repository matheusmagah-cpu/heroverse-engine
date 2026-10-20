#!/usr/bin/env python3
"""Keep the channel's configuration true to structures/channel.json (SYSTEM.md stage 0).

Reads CHANNEL_JSON (version channel-v1: every setting has a value, its source and
when it was verified), fetches the channel with channels.list
(part=brandingSettings,snippet,localizations, mine=true) and prints the diff.
Only with --apply it calls channels.update part=brandingSettings, changing ONLY
the fields that differ: the whole fetched brandingSettings is sent back with
those fields replaced, because update replaces the entire part. A setting whose
source is empty or UNMEASURED is never applied (REFUSED), nor one over YouTube's
limits. Home sections live in channelSections, not brandingSettings: they are
reported, never applied here. Writes receipts/channel-config-<UTC date>.json
with the before and after values.
usage: channel_config.py CHANNEL_JSON [--apply]
"""
import copy
from datetime import datetime, timezone
import json
import time
from pathlib import Path
import shlex
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_video as pv  # noqa: E402

RECEIPTS = Path(__file__).resolve().parent / "receipts"
# channel.json setting -> brandingSettings.channel field
FIELDS = {"description": "description", "keywords": "keywords", "country": "country",
          "default_language": "defaultLanguage", "unsubscribed_trailer": "unsubscribedTrailer"}
NOT_HERE = {"sections": "channelSections API, not brandingSettings: reported only, not applied by this tool"}
LIMITS = {"description": 1000, "keywords": 500}  # characters (Data API channel resource)


def keyword_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(k).strip() for k in value if str(k).strip()]
    try:
        return shlex.split(str(value))
    except ValueError:
        return str(value).split()


def api_value(name, value):
    """The value as YouTube stores it in brandingSettings.channel."""
    if name == "keywords":
        return " ".join(f'"{k}"' if " " in k else k for k in keyword_list(value))
    if name == "country":
        return str(value).strip().upper()
    return value.strip() if isinstance(value, str) else value


def same(name, current, target):
    if name == "keywords":
        return keyword_list(current) == keyword_list(target)
    return (current or None) == (api_value(name, target) or None)


def plan(settings, channel):
    rows = []
    for name, spec in settings.items():
        if name in NOT_HERE:
            rows.append({"setting": name, "status": "NOT_APPLIED", "reason": NOT_HERE[name],
                         "target": spec.get("value") if isinstance(spec, dict) else spec})
            continue
        if name not in FIELDS:
            rows.append({"setting": name, "status": "UNKNOWN_SETTING", "reason": "no brandingSettings field"})
            continue
        if not isinstance(spec, dict) or spec.get("value") is None:
            rows.append({"setting": name, "status": "NOT_SET", "reason": "no value in channel.json"})
            continue
        current, target = channel.get(FIELDS[name]), api_value(name, spec["value"])
        row = {"setting": name, "field": "brandingSettings.channel." + FIELDS[name], "current": current,
               "target": target, "source": spec.get("source"), "verified_at": spec.get("verified_at")}
        if same(name, current, spec["value"]):
            row["status"] = "SAME"
        elif not str(spec.get("source") or "").strip() or str(spec["source"]).strip().upper() == "UNMEASURED":
            row.update(status="REFUSED", reason="source empty or UNMEASURED: never applied")
        elif name in LIMITS and len(target) > LIMITS[name]:
            row.update(status="REFUSED", reason=f"{len(target)} characters, over the {LIMITS[name]} limit")
        else:
            row["status"] = "CHANGE"
        rows.append(row)
    return rows


def fetch(s, expected):
    items = pv.check(s.get(pv.API + "channels", params={"part": "brandingSettings,snippet,localizations", "mine": "true"}),
                     "CHANNELS_LIST")["items"]
    if [c["id"] for c in items] != [expected] or expected != pv.CHANNEL:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")
    return items[0]


def show(value):
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 120 else text[:117] + "..."


VERIFY_WAITS = (0, 20, 40, 60, 120)  # seconds; run 39320063115 read the old text right after the update


def main(channel_json, apply=False, receipts_dir=RECEIPTS):
    config = json.loads(Path(channel_json).read_text())
    if config.get("version") != "channel-v1":
        raise SystemExit("CHANNEL_JSON_VERSION " + str(config.get("version")))
    s = pv.session()
    item = fetch(s, config.get("channel_id"))
    before = item.get("brandingSettings", {})
    rows = plan(config.get("settings", {}), before.get("channel", {}))
    for r in rows:
        line = f"{r['status']:<15} {r['setting']}"
        if "current" in r:
            line += f": {show(r['current'])} -> {show(r['target'])}"
        if r.get("reason"):
            line += f"  [{r['reason']}]"
        print(line)
    changes = [r for r in rows if r["status"] == "CHANGE"]
    after, sent = before, None
    if apply and changes:
        sent = copy.deepcopy(before)  # update replaces the whole part: every other field goes back exactly as fetched
        for r in changes:
            sent.setdefault("channel", {})[FIELDS[r["setting"]]] = r["target"]
        pv.check(s.put(pv.API + "channels", params={"part": "brandingSettings"},
                       json={"id": item["id"], "brandingSettings": sent}), "CHANNELS_UPDATE")
        for wait in VERIFY_WAITS:  # YouTube serves the old branding for a while after a successful update
            time.sleep(wait)
            after = fetch(s, config["channel_id"]).get("brandingSettings", {})
            for r in changes:
                r["applied"] = same(r["setting"], after.get("channel", {}).get(FIELDS[r["setting"]]), r["target"])
            if all(r["applied"] for r in changes):
                break
    now = datetime.now(timezone.utc)
    receipt = {"version": "channel-config-receipt-v1", "channel_id": item["id"], "channel_json": str(channel_json),
               "mode": "apply" if apply else "plan", "applied": bool(apply and changes),
               "changed_fields": [FIELDS[r["setting"]] for r in changes] if apply else [],
               "rows": rows, "before": {"brandingSettings": before, "localizations": item.get("localizations")},
               "after": {"brandingSettings": after}, "at": now.isoformat()}
    path = Path(receipts_dir) / f"channel-config-{now.date().isoformat()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"receipt": str(path), "mode": receipt["mode"], "changes": [r["setting"] for r in changes],
                      "refused": [r["setting"] for r in rows if r["status"] == "REFUSED"]}))
    if apply and changes and not all(r["applied"] for r in changes):
        raise SystemExit("CHANNEL_UPDATE_NOT_VERIFIED " + ",".join(r["setting"] for r in changes if not r["applied"]))
    return receipt


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--apply"]
    if len(args) != 1 or any(a.startswith("--") for a in args):
        raise SystemExit(__doc__)
    main(args[0], apply="--apply" in sys.argv[1:])
