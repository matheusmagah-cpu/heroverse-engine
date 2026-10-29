#!/usr/bin/env python3
"""Offline tests of arc_links.py with a fake YouTube (no network, no secrets)."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "migration/ops"))
import arc_links as al  # noqa: E402
import heartbeat as hb  # noqa: E402
import publish_video as pv  # noqa: E402

FORCE_SSL = {al.COMMENT_SCOPE}
NOW = "2026-10-28T10:41:00+00:00"
DISCLOSURE = "Scripture: King James Version (public domain).\nVisuals and voice made with AI tools."
LONG, OTHER, NEXT1 = "LONGvid0015", "OTHERvid001", "NEXTshort05"
SHORTS = {"genesis-01-short": "SHORTvid001", "genesis-02-short": "SHORTvid002",
          "genesis-03-short": "SHORTvid003", "genesis-04-short": "SHORTvid004"}


class R:
    def __init__(self, code, body=None):
        self.status_code, self._body, self.headers = code, body, {}
        self.content = json.dumps(body).encode() if body is not None else b""
        self.text = self.content.decode()

    def json(self):
        return self._body


def video(vid, title, description, privacy="public"):
    return {"id": vid, "etag": "e-" + vid,
            "snippet": {"channelId": pv.CHANNEL, "title": title, "description": description, "tags": ["Bible"],
                        "categoryId": "29", "defaultLanguage": "en", "defaultAudioLanguage": "en", "localized": {}},
            "status": {"privacyStatus": privacy, "uploadStatus": "processed"}}


class FakeYT:
    """Videos by id; records every write. Comment threads are kept per video, so a lost ledger is caught too."""

    def __init__(self, vids):
        self.vids = {v["id"]: v for v in vids}
        self.writes, self.comments = [], {}

    def get(self, url, params=None, **kw):
        if url.endswith("channels"):
            return R(200, {"items": [{"id": pv.CHANNEL}]})
        if url.endswith("videos"):
            return R(200, {"items": [json.loads(json.dumps(self.vids[i])) for i in params["id"].split(",") if i in self.vids]})
        if url.endswith("commentThreads"):
            return R(200, {"items": [{"id": cid, "snippet": {"topLevelComment": {"snippet": {
                "authorChannelId": {"value": pv.CHANNEL}, "textOriginal": text}}}}
                for cid, text in self.comments.get(params["videoId"], [])]})
        raise AssertionError("unexpected GET " + url)

    def put(self, url, params=None, json=None, **kw):
        assert url.endswith("videos") and params == {"part": "snippet"}, url
        self.writes.append(("update", json["id"]))
        assert json["id"] in self.vids
        self.vids[json["id"]]["snippet"].update(json["snippet"])
        return R(200, self.vids[json["id"]])

    comment_answer = None   # an R to return instead of posting (a refusal)

    def post(self, url, params=None, json=None, **kw):
        assert url.endswith("commentThreads"), url
        vid = json["snippet"]["videoId"]
        if self.comment_answer is not None:
            self.writes.append(("comment_refused", vid))
            return self.comment_answer
        self.writes.append(("comment", vid))
        cid = f"Ugz-{vid}-{len(self.comments.get(vid, []))}"
        self.comments.setdefault(vid, []).append((cid, json["snippet"]["topLevelComment"]["snippet"]["textOriginal"]))
        return R(200, {"id": cid})


class Fixture:
    def __init__(self, d, long_privacy="public", next_privacy="private"):
        d = Path(d)
        self.arcs, self.eps, self.ledger, self.links = d / "arcs.json", d / "episodes", d / "ledger.json", d / "links.json"
        self.eps.mkdir()
        # the scenarios below are timed around a long slot of 28/10 10:00; the real calendar moves (arc-01 went to
        # 04/11, owner 27/10), so the fixture pins its own slot and RepoFiles checks the real one
        table = json.loads((ROOT / "migration/production/bible/arcs.json").read_text())
        table["arcs"][0]["long"]["slot"] = "2026-10-28T10:00:00Z"
        self.arcs.write_text(json.dumps(table))
        entries = {}
        vids = []
        for n, (ep, vid) in enumerate(SHORTS.items(), 1):
            sha = f"{n:064d}"
            (self.eps / f"{ep}.json").write_text(json.dumps({"id": ep, "output_sha256": sha}))
            entries[f"bible:{ep}:{sha}"] = {"video_id": vid, "uploaded_at": f"2026-10-24T1{n}:00:00+00:00"}
            vids.append(video(vid, f"Part {n} title 🌿 | Genesis, Bible Story (KJV) #shorts",
                              f"Genesis part {n}.\n\nNext: Part {n + 1}.\n\n{DISCLOSURE}\n\n#Bible #shorts"))
        (self.eps / "genesis-05-short.json").write_text(json.dumps({"id": "genesis-05-short", "output_sha256": "5" * 64,
                                                                     "slot": "2026-10-26T13:30:00Z"}))
        entries["bible:genesis-05-short:" + "5" * 64] = {"video_id": NEXT1, "uploaded_at": "2026-10-25T01:59:00+00:00"}
        vids.append(video(NEXT1, "Am I My Brother's Keeper? 🐑 | Cain and Abel, Bible Story (KJV) #shorts",
                          "Cain and Abel.\n\n" + DISCLOSURE, next_privacy))
        entries["pilot-015:" + "f" * 64] = {"video_id": LONG, "uploaded_at": "2026-10-27T12:00:00+00:00", "steps": {}}
        vids.append(video(LONG, "Creation, Eden and the Fall | Genesis 1-3 Bible Story (KJV)",
                          "The first story of the Bible.\n\n0:00 Cold open\n1:10 In the beginning\n\n" + DISCLOSURE,
                          long_privacy))
        entries["pilot-014:" + "e" * 64] = {"video_id": OTHER, "uploaded_at": "2026-10-25T08:24:00+00:00", "steps": {}}
        vids.append(video(OTHER, "Morning prayer", "A prayer.\n\nVisuals made with AI."))
        self.ledger.write_text(json.dumps({"version": "publish-ledger-v1", "entries": entries}))
        self.yt = FakeYT(vids)

    def run(self, mode="apply", now=NOW, scopes=FORCE_SSL):
        lines = []
        al.run(mode, now, self.yt, scopes, self.arcs, self.eps, self.ledger, self.links, out=lines.append)
        return lines

    def todo(self, now=NOW):
        lines = []
        al.run("todo", now, None, None, self.arcs, self.eps, self.ledger, self.links, out=lines.append)
        return lines

    def desc(self, vid):
        return self.yt.vids[vid]["snippet"]["description"]


class ArcLinks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.f = Fixture(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_short_description_first_line_links_the_long_and_keeps_the_rest(self):
        before = self.f.desc(SHORTS["genesis-02-short"])
        self.f.run()
        for vid in SHORTS.values():
            first, rest = self.f.desc(vid).split("\n", 1)
            self.assertEqual(first, f"▶ The full story: https://youtu.be/{LONG}")
        self.assertEqual(self.f.desc(SHORTS["genesis-02-short"]).split("\n", 1)[1], before)

    def test_required_disclosure_lines_are_kept(self):
        self.f.run()
        for vid in list(SHORTS.values()) + [LONG]:
            self.assertIn(DISCLOSURE, self.f.desc(vid))
            self.assertEqual(al.pe.description_problems(self.f.desc(vid)), [])
        # a Short whose live description lost its disclosure is not edited
        self.f.yt.vids[SHORTS["genesis-03-short"]]["snippet"]["description"] = "No source line."
        self.f.yt.writes.clear()
        lines = self.f.run()
        self.assertNotIn(("update", SHORTS["genesis-03-short"]), self.f.yt.writes)
        self.assertTrue(any("DISCLOSURE_MISSING" in x for x in lines))

    def test_second_run_changes_nothing(self):
        self.f.run()
        snapshot = {v: self.f.desc(v) for v in self.f.yt.vids}
        ledger = json.loads(self.f.links.read_text())
        self.f.yt.writes.clear()
        self.f.run("apply", "2026-10-28T13:41:00+00:00")
        self.assertEqual(self.f.yt.writes, [])
        self.assertEqual({v: self.f.desc(v) for v in self.f.yt.vids}, snapshot)
        self.assertEqual(json.loads(self.f.links.read_text())["changes"], ledger["changes"])
        self.assertEqual(self.f.todo("2026-10-28T13:41:00+00:00"), [])

    def test_one_comment_per_short_even_when_the_ledger_is_lost(self):
        self.f.run()
        for vid in SHORTS.values():
            self.assertEqual(len(self.f.yt.comments[vid]), 1)
            self.assertIn(f"https://youtu.be/{LONG}", self.f.yt.comments[vid][0][1])
        self.f.run()
        self.f.links.unlink()   # a run that stopped before saving: the existing comment is found, not reposted
        self.f.run()
        self.assertEqual([len(self.f.yt.comments[v]) for v in SHORTS.values()], [1, 1, 1, 1])
        state = json.loads(self.f.links.read_text())["arcs"]["arc-01"]["shorts"]
        self.assertTrue(all(pv.comment_done(state[ep]["comment"]) for ep in SHORTS))

    def test_long_lists_its_shorts_then_the_next_arc_once_public(self):
        self.f.run()
        block = self.f.desc(LONG).split("\n\n")[-1].split("\n")
        self.assertEqual(block[0], al.BLOCK_HEAD)
        self.assertEqual([re.sub(r".* https://youtu\.be/", "", x) for x in block[1:]], list(SHORTS.values()))
        self.assertTrue(block[1].startswith("Part 1 title 🌿 | Genesis, Bible Story (KJV) https://"))
        self.assertIn("0:00 Cold open\n1:10 In the beginning", self.f.desc(LONG))   # chapters untouched
        self.assertNotIn("Next story", self.f.desc(LONG))                           # next arc's Short still private
        self.assertEqual(self.f.todo("2026-10-28T13:41:00+00:00"), [])   # seen private at 10:41: quiet for RECHECK
        self.f.yt.vids[NEXT1]["status"]["privacyStatus"] = "public"
        self.assertEqual(self.f.todo("2026-10-28T23:41:00+00:00"), ["arc-01"])
        self.f.run("apply", "2026-10-28T23:41:00+00:00")
        last = self.f.desc(LONG).split("\n\n")[-1].split("\n")
        self.assertEqual(last[-1], f"Next story: Am I My Brother's Keeper? 🐑 | Cain and Abel, Bible Story (KJV) https://youtu.be/{NEXT1}")
        self.assertEqual(self.f.desc(LONG).count(al.BLOCK_HEAD), 1)
        self.assertEqual(self.f.todo("2026-10-29T13:41:00+00:00"), [])

    def test_videos_outside_the_arcs_table_are_never_touched(self):
        before = json.dumps(self.f.yt.vids[OTHER], sort_keys=True)
        self.f.run()
        self.assertEqual(json.dumps(self.f.yt.vids[OTHER], sort_keys=True), before)
        touched = {v for _, v in self.f.yt.writes}
        self.assertEqual(touched, set(SHORTS.values()) | {LONG})
        self.assertNotIn(NEXT1, touched)          # the next arc's Short is listed, never written
        resolved = al.resolve(json.loads(self.f.arcs.read_text()), json.loads(self.f.ledger.read_text()), self.f.eps)
        with self.assertRaises(SystemExit):
            al.apply(self.f.yt, [{"kind": "comment", "arc": "arc-01", "episode": "x", "video_id": OTHER, "text": "t"}],
                     resolved, {}, self.f.links, FORCE_SSL, datetime.now(timezone.utc))
        self.assertNotIn(("comment", OTHER), self.f.yt.writes)

    def test_nothing_before_the_long_is_public(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        f = Fixture(tmp.name, long_privacy="private")
        lines = f.run()
        self.assertEqual(f.yt.writes, [])
        self.assertTrue(any("LONG_NOT_PUBLIC" in x for x in lines))
        self.assertEqual(f.todo("2026-10-28T09:41:00+00:00"), [])     # before the long's slot: no dispatch
        self.assertEqual(f.todo(), [])                                  # just seen private: quiet for RECHECK
        self.assertEqual(f.todo("2026-10-28T17:00:00+00:00"), ["arc-01"])  # then asked again

    def test_dry_run_prints_the_plan_and_writes_nothing(self):
        lines = self.f.run("plan")
        self.assertEqual(self.f.yt.writes, [])
        self.assertFalse(self.f.links.exists())
        plans = [json.loads(x[5:]) for x in lines if x.startswith("PLAN ")]
        kinds = sorted(p["kind"] for p in plans if p["kind"] != "skip")
        self.assertEqual(kinds, ["comment"] * 4 + ["long_description"] + ["short_description"] * 4)
        self.assertTrue(all("before" not in p and "item" not in p for p in plans))

    def test_missing_scopes(self):
        with self.assertRaises(SystemExit):
            self.f.run(scopes=set())
        self.assertEqual(self.f.yt.writes, [])
        self.f.run(scopes={"https://www.googleapis.com/auth/youtube"})   # update yes, comments need force-ssl
        self.assertFalse(self.f.yt.comments)
        state = json.loads(self.f.links.read_text())["arcs"]["arc-01"]["shorts"]
        self.assertTrue(all(state[ep]["comment"].startswith("PENDING: SCOPE_MISSING") for ep in SHORTS))
        self.assertTrue(all(state[ep]["comment_terminal"].startswith("PENDING: SCOPE_MISSING") for ep in SHORTS))
        self.assertEqual(self.f.todo(), [])           # terminal, with its reason: no endless dispatch

    # review of PR #404
    def test_publication_hold_stops_everything(self):
        hold = Path(self.tmp.name) / "PUBLICATION_HOLD"
        hold.write_text("owner pause\n")
        lines = []
        al.run("todo", NOW, None, None, self.f.arcs, self.f.eps, self.f.ledger, self.f.links, out=lines.append, hold=hold)
        self.assertEqual(lines, [])
        for mode in ("apply", "plan"):
            with self.assertRaises(SystemExit) as e:
                al.run(mode, NOW, self.f.yt, FORCE_SSL, self.f.arcs, self.f.eps, self.f.ledger, self.f.links,
                       out=lines.append, hold=hold)
            self.assertEqual(str(e.exception.code), "PUBLICATION_HOLD")
        self.assertEqual(self.f.yt.writes, [])
        self.assertFalse(self.f.links.exists())

    def test_block_is_not_duplicated_when_the_description_ends_in_a_newline(self):
        b = al.BLOCK_HEAD + "\nPart 1 https://youtu.be/SHORTvid001"
        once = al.with_block("Intro\nmore\n", b)
        self.assertEqual(al.with_block(once, b), once)
        self.assertEqual(al.with_block(once, b).count(al.BLOCK_HEAD), 1)
        self.assertEqual(once, "Intro\nmore\n\n" + b)
        for desc in ("Intro", "Intro\n\n\n", "Intro\n\n" + b + "\n", "Intro\n\n" + b + "\n\nTail"):
            twice = al.with_block(al.with_block(desc, b), b)
            self.assertEqual(twice, al.with_block(desc, b))
            self.assertEqual(twice.count(al.BLOCK_HEAD), 1, desc)
        self.f.yt.vids[LONG]["snippet"]["description"] += "\n"
        self.f.run()
        self.f.yt.writes.clear()
        self.f.run()
        self.assertEqual(self.f.yt.writes, [])
        self.assertEqual(self.f.desc(LONG).count(al.BLOCK_HEAD), 1)

    def test_token_goes_in_a_post_body_and_never_reaches_the_log(self):
        import contextlib
        import io
        token = "ya29.SECRET-TOKEN-VALUE"
        seen = {}

        def post(url, data=None, timeout=None, **kw):
            seen.update(url=url, data=data, kw=kw)
            return R(200, {"scope": al.COMMENT_SCOPE})
        self.assertEqual(al.token_scopes(token, post), {al.COMMENT_SCOPE})
        self.assertEqual(seen["url"], al.TOKENINFO)
        self.assertNotIn(token, seen["url"])
        self.assertEqual(seen["data"], {"access_token": token})
        self.assertNotIn("params", seen["kw"])

        def broken(url, data=None, timeout=None, **kw):
            raise ConnectionError(f"failed {url}?access_token={data['access_token']}")
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(err):
            self.assertEqual(al.token_scopes(token, broken), set())
        self.assertNotIn(token, err.getvalue())
        self.assertIn("TOKENINFO_FAILED ConnectionError", err.getvalue())
        source = (HERE / "arc_links.py").read_text()
        self.assertNotIn('params={"access_token"', source)
        self.assertIn('raise SystemExit(f"AUTH_FAILED {type(e).__name__}") from None', source)

    def test_terminal_states_stop_todo(self):
        # a Short whose live description lost its disclosure: skipped with its reason, todo stops asking
        self.f.yt.vids[SHORTS["genesis-03-short"]]["snippet"]["description"] = "No source line."
        self.f.run()
        state = json.loads(self.f.links.read_text())["arcs"]["arc-01"]["shorts"]
        self.assertIn("DISCLOSURE_MISSING", state["genesis-03-short"]["terminal"])
        self.assertEqual(self.f.todo(), [])

    def test_refused_comment_is_terminal_and_a_transient_one_is_retried(self):
        from unittest import mock
        self.f.yt.comment_answer = R(403, {"error": {"code": 403, "message": "comments disabled",
                                                     "errors": [{"reason": "commentsDisabled"}]}})
        self.f.run()
        state = json.loads(self.f.links.read_text())["arcs"]["arc-01"]["shorts"]
        self.assertTrue(all("commentsDisabled" in state[ep]["comment_terminal"] for ep in SHORTS))
        self.assertEqual(self.f.todo(), [])
        self.f.yt.writes.clear()
        self.f.run()
        self.assertFalse([w for w in self.f.yt.writes if w[0].startswith("comment")])   # not attempted again

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        f = Fixture(tmp.name)
        f.yt.comment_answer = R(503, {"error": {"code": 503, "message": "backend", "errors": [{"reason": "backendError"}]}})
        with mock.patch.object(pv.time, "sleep", lambda _: None):
            f.run()
        state = json.loads(f.links.read_text())["arcs"]["arc-01"]["shorts"]
        self.assertFalse(any("comment_terminal" in state[ep] for ep in SHORTS))
        self.assertEqual(f.todo("2026-10-28T13:41:00+00:00"), ["arc-01"])

    def test_long_must_be_processed_as_well_as_public(self):
        self.f.yt.vids[LONG]["status"]["uploadStatus"] = "uploaded"
        lines = self.f.run()
        self.assertEqual(self.f.yt.writes, [])
        self.assertTrue(any("LONG_NOT_PUBLIC" in x for x in lines))
        self.f.yt.vids[LONG]["status"]["uploadStatus"] = "processed"
        self.f.run("apply", "2026-10-28T17:00:00+00:00")
        self.assertIn(("update", LONG), self.f.yt.writes)


class RepoFiles(unittest.TestCase):
    def test_arcs_table_follows_the_series_calendar(self):
        arcs = json.loads((ROOT / "migration/production/bible/arcs.json").read_text())["arcs"]
        self.assertEqual([a["id"] for a in arcs], ["arc-01", "arc-02", "arc-03", "arc-04"])
        self.assertEqual([a["shorts"] for a in arcs],
                         [[f"genesis-{n:02d}-short" for n in range(k, k + 4)] for k in (1, 5, 9, 13)])
        self.assertEqual(arcs[0]["long"]["pilot"], "pilot-015")
        self.assertEqual(arcs[0]["long"]["slot"], "2026-10-29T22:00:00Z")   # owner recovery direction 29/10
        self.assertEqual([a["next"] for a in arcs], ["arc-02", "arc-03", "arc-04", None])
        for p in (ROOT / "migration/production/bible/episodes").glob("*.json"):
            self.assertEqual(sum(p.stem in a["shorts"] for a in arcs), 1, p.stem)

    def test_heartbeat_dispatches_arc_links_on_its_condition(self):
        task = [t for t in hb.TASKS if t["workflow"] == "arc-links.yml"]
        self.assertEqual(len(task), 1)
        self.assertEqual(task[0]["when"], "arc_links_todo")
        at = datetime(2026, 10, 28, 10, 41, tzinfo=timezone.utc)
        self.assertIn("arc-links.yml", hb.decide({}, {"arc_links_todo": True}, at))
        self.assertNotIn("arc-links.yml", hb.decide({}, {"arc_links_todo": False}, at))
        ran = {"arc-links.yml": [{"createdAt": "2026-10-28T10:41:30Z", "status": "completed", "conclusion": "success"}]}
        self.assertNotIn("arc-links.yml", hb.decide(ran, {"arc_links_todo": True}, datetime(2026, 10, 28, 11, 41, tzinfo=timezone.utc)))

    def test_condition_builder_computes_arc_links_todo_without_secrets(self):
        beat = (ROOT / ".github/workflows/heartbeat.yml").read_text()
        step = beat[beat.index("name: Work waiting"):beat.index("runner-wake:")]
        self.assertIn("migration/publish/arc_links.py todo", step)
        self.assertIn("'arc_links_todo'", step)
        self.assertNotIn("secrets.", step)
        wf = (ROOT / ".github/workflows/arc-links.yml").read_text()
        self.assertNotIn("schedule:", wf)          # crons are dropped here: the heartbeat dispatches it
        self.assertIn("secrets.HERO_YT_AUTHORIZED_USER_JSON", wf)
        self.assertIn("migration/publish/test_arc_links.py", wf)
        # the real repo files decide without network: arc 1 is waiting only once pilot-015 is in the ledger
        lines = []
        al.run("todo", "2026-10-26T12:00:00+00:00", out=lines.append)
        self.assertNotIn("arc-01", lines)          # long slot not reached yet

    def test_workflows_hold_pull_concurrency_and_loud_crash(self):
        wf = (ROOT / ".github/workflows/arc-links.yml").read_text()
        hold = 'if [ -f migration/ops/PUBLICATION_HOLD ]; then'
        pull = "git pull -q --ff-only origin main"
        run = 'migration/publish/arc_links.py "$MODE"'
        self.assertIn(hold, wf)
        self.assertLess(wf.index("actions/checkout"), wf.index(pull))
        self.assertLess(wf.index(hold), wf.index(run))
        self.assertLess(wf.index(pull), wf.index(run))       # E-race: the ledger read is the latest on main
        self.assertIn("group: heroverse-arc-links", wf)
        self.assertNotIn("group: heroverse-publish", wf)
        beat = (ROOT / ".github/workflows/heartbeat.yml").read_text()
        self.assertIn('arc_links.py todo > "$T/arcs" || echo "TODO_CHECK_FAILED" > "$T/arcs"', beat)
        self.assertNotIn('arc_links.py todo > "$T/arcs" || true', beat)
        self.assertIn('if [ -f migration/ops/PUBLICATION_HOLD ]; then : > "$T/arcs"; fi', beat)
        self.assertLess(beat.index('|| echo "TODO_CHECK_FAILED"'), beat.index(': > "$T/arcs"'))

    def test_arc_links_ledger_starts_valid(self):
        links = json.loads((HERE / "arc_links_ledger.json").read_text())
        self.assertEqual(links["version"], "arc-links-ledger-v1")
        self.assertIsInstance(links["arcs"], dict)
        self.assertIsInstance(links["changes"], list)


if __name__ == "__main__":
    unittest.main()
