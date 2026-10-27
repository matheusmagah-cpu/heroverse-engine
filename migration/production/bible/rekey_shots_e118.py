"""E118 one-off migration: re-key every approved clip in shots/*.json to the request digest without `seconds`.

The E114 digest held the clip seconds, which a voice-over or talking shot derives from measured line timing; E118
removed them (episode_build.request_digest) and checks coverage instead (clip_seconds >= what the layout needs).
An approval is re-keyed only when nothing but the form changed:
  1. the preflight report of its plan is bound to the plan, characters, image records and probes now (only its
     `code` part may differ: this PR changed the code);
  2. its old request_sha256 equals the digest of the canonical form its probe record holds AND the committed
     preflight's (old-form) digest of the current plan;
  3. the new canonical form computed from the CURRENT plan (episode_build.request_identity) equals that old form
     with `seconds` taken out.
It then gets the new request_sha256, `clip_seconds` (the seconds the clip was generated at, from the old form) and
`rekeyed_from` (the old digest). Anything else is refused and nothing is written. Running it twice changes nothing.

  python3 migration/production/bible/rekey_shots_e118.py [--check]
"""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import episode_build as eb  # noqa: E402
import episode_preflight as pf  # noqa: E402

plan_check = eb.plan_check


def layout_for(plan):
    """A layout of the plan from estimated line lengths: the new canonical form reads none of its numbers (the
    E118 antidote proves it), only which records exist."""
    items, _ = plan_check.sequence(plan)
    durations = [max(2.0, plan_check.words(x["text"]) / 2.7) for x in items]
    return eb.predict(plan, durations)[1]


def rekey(path):
    data = json.loads(Path(path).read_text())
    plan_path = HERE / "plans" / f"{data['episode']}.json"
    plan = json.loads(plan_path.read_text())
    report = json.loads((pf.REPORTS / f"{data['episode']}.json").read_text())
    stale = [p for p in pf.stale_parts(report.get("binding"), pf.binding(plan_path, plan)) if not p.startswith("code:")]
    if stale or report.get("status") != "PASS":
        raise SystemExit(f"REKEY_REFUSED {data['episode']}: preflight {report.get('status')} or stale {stale}")
    old_digests = (report.get("requests") or {}).get("digests") or {}
    layout, refs = layout_for(plan), eb.ref_paths(plan, eb.REPO / ".episode" / plan["episode"])
    index = {s["id"]: i for i, s in enumerate(plan["shots"])}
    out, bad = {}, []
    for sid, a in data["shots"].items():
        if "rekeyed_from" in a:
            out[sid] = a
            continue
        entry = json.loads((eb.REPO / a["probe_record"]).read_text())["shots"][sid]
        old = entry["request"]
        if not (eb.digest(old) == a["request_sha256"] == old_digests.get(sid)):
            bad.append(f"{sid} (old digest is not the plan's at preflight)")
            continue
        i = index[sid]
        new_sha, new = eb.request_identity(plan["shots"][i], i, plan, layout, refs)
        if new != {k: v for k, v in old.items() if k != "seconds"}:
            bad.append(f"{sid} (the current plan's request differs beyond `seconds`)")
            continue
        out[sid] = dict(a, request_sha256=new_sha, clip_seconds=old["seconds"], rekeyed_from=a["request_sha256"])
    if bad:
        raise SystemExit(f"REKEY_REFUSED {data['episode']}: " + "; ".join(bad))
    return dict(data, shots={k: out[k] for k in sorted(out)})


def main(argv):
    changed = []
    for path in sorted(eb.SHOTS_DIR.glob("*.json")):
        new = rekey(path)
        if new != json.loads(path.read_text()):
            changed.append(path.name)
            if "--check" not in argv:
                path.write_text(json.dumps(new, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"rekeyed": changed, "written": "--check" not in argv}))


if __name__ == "__main__":
    main(sys.argv[1:])
