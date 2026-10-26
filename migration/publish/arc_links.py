#!/usr/bin/env python3
"""Link each arc's Shorts to its long video, and the long back to its Shorts (owner, 2026-10-26; SERIES.md
"One format, two lengths": one arc = 4 Short episodes = 1 long).

The arcs table (production/bible/arcs.json) is the only list of videos this touches: the Shorts by their episode
ids (publish ledger key "bible:<id>:<sha>"), the long by its pilot (key "<pilot>:<sha>"). Any other video is never
written. Once an arc's long is public (videos.list status), for each public Short of the arc:
  - its description's first line becomes "▶ The full story: https://youtu.be/<long>" (the rest is kept, and the
    KJV public-domain and AI disclosure lines publish_episode.py requires must still be there, or it is skipped);
  - one top-level comment linking the long is posted (commentThreads.insert), once per Short.
Then the long's description gets a block listing its public Shorts (title and youtu.be link) and the next arc's
first Short once that one is public.

Idempotent: every write compares with what is live first, so a second run changes nothing; each change is recorded
in publish/arc_links_ledger.json. The Data API has no field for a Short's Studio "related video" and cannot pin a
comment (Data API v3 discovery document, revision 20261022): both stay the manual step in OPERATIONS.md.

usage: arc_links.py todo [NOW_ISO]     offline, no secrets: prints the arcs with link work waiting (heartbeat)
       arc_links.py plan [NOW_ISO]     reads YouTube, prints the planned changes, writes nothing
       arc_links.py apply [NOW_ISO]    reads YouTube, writes the changes and the ledger
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import publish_episode as pe  # noqa: E402
import publish_video as pv  # noqa: E402

ROOT = HERE.parent.parent
ARCS = ROOT / "migration/production/bible/arcs.json"
EPISODES = ROOT / "migration/production/bible/episodes"
PUBLISH_LEDGER = HERE / "ledger.json"
LINKS_LEDGER = HERE / "arc_links_ledger.json"
HOLD = ROOT / "migration/ops/PUBLICATION_HOLD"   # owner pause: nothing is written, todo reports nothing

LINK = "▶ The full story: https://youtu.be/{}"
LINK_RE = re.compile(r"^▶ The full story: https://youtu\.be/[A-Za-z0-9_-]{11}\s*$")
COMMENT = "▶ The full story, every part in one video: https://youtu.be/{}"
BLOCK_HEAD = "▶ This story in Shorts:"
NEXT = "Next story: {} https://youtu.be/{}"
WRITABLE = ("title", "description", "tags", "categoryId", "defaultLanguage", "defaultAudioLanguage")
TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"
TRANSIENT = re.compile(r"HTTP_(409|429|5\d\d)|NOT_ATTEMPTED|NO_ID_IN_RESPONSE|Error\b|Timeout|Connection")
RECHECK = timedelta(hours=6)   # a video seen not public is looked at again after this (todo stays quiet meanwhile)
# Data API v3 discovery document: videos.update accepts any of these; commentThreads.insert only youtube.force-ssl
UPDATE_SCOPES = {"https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/youtube.force-ssl",
                 "https://www.googleapis.com/auth/youtubepartner"}
COMMENT_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def due(slot, now):
    return slot is None or ts(slot) <= now


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def latest(entries):
    entries = [e for e in entries if e.get("video_id")]
    return max(entries, key=lambda e: e.get("uploaded_at", ""))["video_id"] if entries else None


def resolve(arcs, ledger, episodes_dir):
    """Each arc with its Shorts (episode id, video id or None, slot) and its long's video id, from the repo files."""
    entries = ledger.get("entries", {})
    by_id = {a["id"]: a for a in arcs["arcs"]}

    def short(ep):
        rec = read_json(Path(episodes_dir) / f"{ep}.json", {}) or {}
        exact = entries.get(f"bible:{ep}:{rec.get('output_sha256')}", {}).get("video_id")
        vid = exact or latest(v for k, v in entries.items() if k.startswith(f"bible:{ep}:"))
        return ep, vid, rec.get("slot")

    out = []
    for a in arcs["arcs"]:
        pilot = (a.get("long") or {}).get("pilot")
        long_id = latest(v for k, v in entries.items() if pilot and k.startswith(f"{pilot}:")) if pilot else None
        nxt = by_id.get(a.get("next")) if a.get("next") else None
        out.append({"id": a["id"], "shorts": [short(ep) for ep in a["shorts"]], "long": long_id,
                    "long_slot": (a.get("long") or {}).get("slot"), "next_first": short(nxt["shorts"][0]) if nxt else None})
    return out


def allowed(resolved):
    """Every video id the arcs table names: the only ones this may ever write."""
    ids = set()
    for r in resolved:
        ids.update(v for _, v, _ in r["shorts"] if v)
        if r["long"]:
            ids.add(r["long"])
    return ids


def todo(resolved, links, now):
    """Arcs with work waiting, from the repo files alone (no secrets): the long is uploaded and its slot passed,
    and a Short due by now is not linked or commented, or the long's list is not what is due."""
    out = []
    for r in resolved:
        if not r["long"] or not due(r["long_slot"], now):
            continue
        state = links.get("arcs", {}).get(r["id"], {})
        shorts = state.get("shorts", {})
        seen = state.get("not_public", {})

        def waiting(ep, vid, slot):
            # due by its slot, unless the last run saw it still not public less than RECHECK ago
            return vid and due(slot, now) and not (ep in seen and now - ts(seen[ep]) < RECHECK)
        if not waiting("long", r["long"], r["long_slot"]):
            continue
        expected = [ep for ep, vid, slot in r["shorts"] if waiting(ep, vid, slot)]
        listed = state.get("long", {})
        nf = r["next_first"]
        def open_work(ep):
            st = shorts.get(ep, {})
            return ((st.get("linked_to") != r["long"] and not st.get("terminal"))
                    or not (pv.comment_done(st.get("comment")) or st.get("comment_terminal")))
        if (any(open_work(ep) for ep in expected)
                or listed.get("video_id") != r["long"] or not set(expected) <= set(listed.get("shorts") or [])
                or (nf and waiting(*nf) and listed.get("next") != nf[0])):
            out.append(r["id"])
    return out


def with_link(description, long_id):
    """First line = the link to the long; any older link line is dropped; everything else is kept as it is."""
    rest = [line for line in description.split("\n") if not LINK_RE.match(line)]
    return "\n".join([LINK.format(long_id)] + rest)


def short_title(item):
    return re.sub(r"\s*#shorts\s*$", "", item["snippet"]["title"], flags=re.I).strip()


def make_block(shorts, nxt):
    """shorts: [(video_id, item)] of the arc in order; nxt: (video_id, item) or None."""
    if not shorts and not nxt:
        return None
    lines = [BLOCK_HEAD] + [f"{short_title(it)} https://youtu.be/{vid}" for vid, it in shorts]
    if nxt:
        lines.append(NEXT.format(short_title(nxt[1]), nxt[0]))
    return "\n".join(lines)


def with_block(description, block):
    """The long's description with its Shorts block as the last paragraph (an older block is replaced)."""
    lines, out, i = description.split("\n"), [], 0
    while i < len(lines):
        if lines[i].strip() == BLOCK_HEAD:          # an older block: its heading and every line up to a blank one
            i += 1
            while i < len(lines) and lines[i].strip():
                i += 1
            continue
        out.append(lines[i])
        i += 1
    base = "\n".join(out).rstrip()
    return base + "\n\n" + block if block else base


def check(response, what):
    return pv.check(response, what)


def videos(s, ids):
    out = {}
    ids = sorted(ids)
    for i in range(0, len(ids), 50):
        body = check(s.get(pv.API + "videos", params={"part": "snippet,status", "id": ",".join(ids[i:i + 50])}), "VIDEOS")
        out.update({it["id"]: it for it in body.get("items", [])})
    return out


def public(item, processed=False):
    """Public on our channel; for the long also fully processed (uploadStatus), so its link plays."""
    status = (item or {}).get("status", {})
    return bool(item) and status.get("privacyStatus") == "public" \
        and item.get("snippet", {}).get("channelId") == pv.CHANNEL \
        and (not processed or status.get("uploadStatus") == "processed")


def plan(s, resolved, links):
    items = videos(s, allowed(resolved) | {r["next_first"][1] for r in resolved if r["next_first"] and r["next_first"][1]})
    actions = []
    for r in resolved:
        if not r["long"]:
            actions.append({"kind": "skip", "arc": r["id"], "reason": "LONG_NOT_UPLOADED"})
            continue
        long_item = items.get(r["long"])
        if not public(long_item, processed=True):
            actions.append({"kind": "skip", "arc": r["id"], "episode": "long", "video_id": r["long"],
                            "reason": "LONG_NOT_PUBLIC"})
            continue
        state = links.get("arcs", {}).get(r["id"], {}).get("shorts", {})
        listed = []
        for ep, vid, _ in r["shorts"]:
            item = items.get(vid) if vid else None
            if not public(item):
                if vid:
                    actions.append({"kind": "skip", "arc": r["id"], "episode": ep, "video_id": vid,
                                    "reason": "SHORT_NOT_PUBLIC"})
                continue
            listed.append((ep, vid, item))
            before = item["snippet"].get("description", "")
            after = with_link(before, r["long"])
            bad = pe.description_problems(after)
            base = {"arc": r["id"], "episode": ep, "video_id": vid, "long": r["long"]}
            if bad:
                actions.append({**base, "kind": "skip", "reason": "SHORT_DESCRIPTION " + " ".join(bad)})
            else:
                actions.append({**base, "kind": "short_description" if after != before else "short_description_ok",
                                "before": before, "after": after, "item": item})
            if not pv.comment_done(state.get(ep, {}).get("comment")) and not state.get(ep, {}).get("comment_terminal"):
                actions.append({**base, "kind": "comment", "text": COMMENT.format(r["long"])})
        nf = r["next_first"]
        nxt = (nf[1], items[nf[1]]) if nf and nf[1] and public(items.get(nf[1])) else None
        if nf and nf[1] and not nxt:
            actions.append({"kind": "skip", "arc": r["id"], "episode": nf[0], "video_id": nf[1],
                            "reason": "NEXT_NOT_PUBLIC"})
        before = long_item["snippet"].get("description", "")
        block = make_block([(vid, it) for _, vid, it in listed], nxt)
        after = with_block(before, block) if block else before
        base = {"arc": r["id"], "video_id": r["long"], "shorts": [ep for ep, _, _ in listed],
                "next": nf[0] if nxt else None}
        if len(after) > pe.DESCRIPTION_MAX:
            actions.append({**base, "kind": "skip", "reason": "LONG_DESCRIPTION_LENGTH"})
        else:
            actions.append({**base, "kind": "long_description" if after != before else "long_description_ok",
                            "before": before, "after": after, "item": long_item})
    return actions


def update_description(s, item, description):
    snippet = {k: item["snippet"][k] for k in WRITABLE if k in item["snippet"]}
    snippet["description"] = description
    got = check(s.put(pv.API + "videos", params={"part": "snippet"}, json={"id": item["id"], "snippet": snippet}),
                "UPDATE_DESCRIPTION")
    if (got.get("snippet") or {}).get("description") != description:
        raise RuntimeError(f"VERIFY_DESCRIPTION {item['id']}")


def summary(a):
    """What the plan prints and the ledger keeps: no full descriptions, only their first line and hashes."""
    out = {k: v for k, v in a.items() if k not in ("before", "after", "item")}
    if "after" in a:
        out.update(before_sha256=sha(a["before"]), after_sha256=sha(a["after"]),
                   first_line=a["after"].split("\n", 1)[0])
    return out


def apply(s, actions, resolved, links, links_path, scopes, now):
    ok = allowed(resolved)
    when = now.isoformat()
    arcs_state = links.setdefault("arcs", {})
    changes = links.setdefault("changes", [])

    def save():
        Path(links_path).write_text(json.dumps(links, indent=1, ensure_ascii=False) + "\n")

    if any(a["kind"] in ("short_description", "long_description") for a in actions) and not scopes & UPDATE_SCOPES:
        raise SystemExit("SCOPE_MISSING videos.update needs youtube, youtube.force-ssl or youtubepartner")
    for a in actions:
        if a["kind"] == "skip":
            if a["reason"].startswith("SHORT_DESCRIPTION"):   # terminal until the live description is fixed
                arcs_state.setdefault(a["arc"], {}).setdefault("shorts", {}).setdefault(
                    a["episode"], {"video_id": a["video_id"]})["terminal"] = a["reason"]
            if a["reason"].endswith("NOT_PUBLIC"):   # nothing written; todo waits RECHECK before asking again
                arcs_state.setdefault(a["arc"], {}).setdefault("not_public", {})[a["episode"]] = when
            continue
        if a["video_id"] not in ok:
            raise SystemExit(f"NOT_IN_ARCS_TABLE {a['video_id']}")   # never touch a video outside the arcs table
        arc = arcs_state.setdefault(a["arc"], {})
        if a["kind"] in ("short_description", "long_description"):
            update_description(s, a["item"], a["after"])
            changes.append({"at": when, **summary(a)})
        if a["kind"].startswith("short_description"):
            arc.get("not_public", {}).pop(a["episode"], None)
            arc.setdefault("shorts", {}).setdefault(a["episode"], {}).update(video_id=a["video_id"], linked_to=a["long"])
            arc["shorts"][a["episode"]].pop("terminal", None)
        elif a["kind"].startswith("long_description"):
            arc["long"] = {"video_id": a["video_id"], "shorts": a["shorts"], "next": a["next"]}
            for ep in ["long"] + ([a["next"]] if a["next"] else []):
                arc.get("not_public", {}).pop(ep, None)
        elif a["kind"] == "comment":
            state = arc.setdefault("shorts", {}).setdefault(a["episode"], {"video_id": a["video_id"]})
            if COMMENT_SCOPE in scopes:
                state["comment"] = pv.first_comment(s, a["video_id"], a["text"])
            else:
                state["comment"] = "PENDING: SCOPE_MISSING youtube.force-ssl"
            if not pv.comment_done(state["comment"]) and not TRANSIENT.search(state["comment"]):
                state["comment_terminal"] = state["comment"]   # refused for good (scope, comments off): todo stops
            if pv.comment_done(state["comment"]):
                changes.append({"at": when, **summary(a), "comment_id": state["comment"]})
        save()
    links["checked_at"] = when
    save()


def session():
    """The same OAuth credential as publish_video.py (secret HERO_YT_AUTHORIZED_USER_JSON), plus its granted scopes."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import AuthorizedSession, Request
        creds = Credentials.from_authorized_user_info(json.loads(os.environ["HERO_YT_AUTHORIZED_USER_JSON"]))
        creds.refresh(Request())
        s = AuthorizedSession(creds)
    except Exception as e:  # noqa: BLE001 - only the type reaches the log, never a token or the credential
        raise SystemExit(f"AUTH_FAILED {type(e).__name__}") from None
    scopes = set(getattr(creds, "granted_scopes", None) or creds.scopes or [])
    if not scopes:
        scopes = token_scopes(creds.token)
    return s, scopes


def token_scopes(token, post=None):
    """Scopes of the access token from Google's tokeninfo: the token goes in the POST body (never a URL), and any
    failure prints only its exception type."""
    try:
        if post is None:
            import requests
            post = requests.post
        r = post(TOKENINFO, data={"access_token": token}, timeout=30)
        return set((r.json().get("scope") or "").split()) if r.status_code < 300 else set()
    except Exception as e:  # noqa: BLE001
        print(f"TOKENINFO_FAILED {type(e).__name__}", file=sys.stderr)
        return set()


def run(mode, now=None, s=None, scopes=None, arcs_path=ARCS, episodes_dir=EPISODES, ledger_path=PUBLISH_LEDGER,
        links_path=LINKS_LEDGER, out=print, hold=HOLD):
    if Path(hold).exists():
        if mode == "todo":
            print("PUBLICATION_HOLD", file=sys.stderr)   # nothing waiting while the owner holds publication
            return 0
        raise SystemExit("PUBLICATION_HOLD")
    now = ts(now) if isinstance(now, str) else (now or datetime.now(timezone.utc))
    resolved = resolve(read_json(arcs_path), read_json(ledger_path), episodes_dir)
    links = read_json(links_path, None) or {"version": "arc-links-ledger-v1", "arcs": {}, "changes": []}
    if mode == "todo":
        for arc in todo(resolved, links, now):
            out(arc)
        return 0
    if mode not in ("plan", "apply"):
        raise SystemExit("usage: arc_links.py todo|plan|apply [NOW_ISO]")
    if s is None:
        s, scopes = session()
    scopes = set(scopes or ())
    if [c["id"] for c in check(s.get(pv.API + "channels", params={"part": "id", "mine": "true"}), "CHANNEL")["items"]] != [pv.CHANNEL]:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")
    out(json.dumps({"scopes": {"videos.update": bool(scopes & UPDATE_SCOPES),
                               "commentThreads.insert": COMMENT_SCOPE in scopes}}))
    actions = plan(s, resolved, links)
    for a in actions:
        if not a["kind"].endswith("_ok"):
            out(("PLAN " if mode == "plan" else "DO ") + json.dumps(summary(a), ensure_ascii=False))
    if mode == "apply":
        apply(s, actions, resolved, links, links_path, scopes, now)
    return 0


if __name__ == "__main__":
    sys.exit(run(*(sys.argv[1:3] or ["plan"])))
