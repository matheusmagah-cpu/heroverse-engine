#!/usr/bin/env python3
"""HeroVerse TikTok runner: runs on the owner's Windows PC (TikTok blocks datacenter IPs), in the runner's own browser
profile, logged in once by the owner. Called by the main clock through Desktop Commander (OPERATIONS.md "Clocks").

  runner.py login                    opens a visible Chrome window on the runner's profile at TikTok's login page;
                                     the owner logs in by hand (once); waits up to 15 min
  runner.py status                   LOGGED_IN or NOT_LOGGED_IN (the login cookie's presence, never its value)
  runner.py comments [--out FILE]    our videos (@heroverse.official only) and their viewers' top-level comments not yet
                                     decided, to out/comments.json; read-only
  runner.py reply --in FILE [--dry-run] [--max N]
                                     acts on Claude's decisions {"replies": [{comment_id, video_id, author, decision,
                                     text | reason, verse?}]}: each REPLY is liked and answered; each SKIP is recorded
  runner.py probe VIDEO_ID           which selectors.json entries are found on one of our video pages; read-only
  runner.py story VIDEO_ID           STORY_WEB_UNSUPPORTED: TikTok's web upload has no Story option (README.md)

Pacing like a person (tiktok_core): one comment at a time, 45-240 s between comments, 4-15 s between the steps on
one, at most 3 a run, 20 a day and 20 min after the last action. Only our own videos. No captcha solving, no
fingerprint or webdriver masking, no proxy: a challenge page stops the run (CHALLENGE) for the owner to look at.
Nothing is done twice: ledger.json is written before the first click (ATTEMPTING) and after TikTok confirms.
Cookies and passwords never reach a file, a log or the output: only the presence of the login cookie is read.
"""
import argparse
import json
import os
from pathlib import Path
import random
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tiktok_core as core  # noqa: E402

PROFILE = HERE / "profile"
LEDGER = HERE / "ledger.json"
OWN = HERE / "out" / "own_videos.json"
LOG = HERE / "logs" / "runner.log"
LOCK = HERE / "runner.lock"
SELECTORS = json.loads((HERE / "selectors.json").read_text(encoding="utf-8"))
BASE = "https://www.tiktok.com"
CHALLENGE_HINTS = ("captcha", "verify to continue", "security check", "drag the slider")


def log(msg):
    LOG.parent.mkdir(exist_ok=True)
    line = f"{core.iso(core.now_utc())} {msg}"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def policy():
    """reply_policy.problems from the repository copy deployed in vendor/ (deploy.ps1), or None."""
    vendor = HERE / "vendor" / "migration" / "publish"
    if not (vendor / "reply_policy.py").exists():
        return None
    sys.path.insert(0, str(vendor))
    import reply_policy  # noqa: E402
    return reply_policy.problems


def pause(lo_hi):
    time.sleep(random.uniform(*lo_hi))


class Lock:
    def __enter__(self):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
        except FileExistsError:
            raise SystemExit("RUNNER_BUSY (runner.lock: another run, or a run that died; delete it after checking)")
        return self

    def __exit__(self, *exc):
        LOCK.unlink(missing_ok=True)


def browser(pw, headless):
    PROFILE.mkdir(exist_ok=True)
    return pw.chromium.launch_persistent_context(
        str(PROFILE), channel="chrome", headless=headless, viewport={"width": 1280, "height": 900}, locale="en-US")


def logged_in(ctx):
    # the name of the login cookie only; its value is never read into a variable that is printed or stored
    return any(c["name"] == "sessionid" and "tiktok.com" in c["domain"] for c in ctx.cookies(BASE))


def challenged(page):
    try:
        body = page.inner_text("body", timeout=5000).lower()
    except Exception:  # noqa: BLE001
        return False
    return any(h in body for h in CHALLENGE_HINTS)


def first(scope, key, timeout=4000):
    """The first selector of selectors.json[key] present in scope, as a locator, or None."""
    for sel in SELECTORS[key]:
        loc = scope.locator(sel)
        try:
            loc.first.wait_for(state="attached", timeout=timeout)
            return loc
        except Exception:  # noqa: BLE001
            continue
    return None


def json_of(response):
    try:
        return response.json()
    except Exception:  # noqa: BLE001
        return None


# ---------- commands ----------

def cmd_login(args):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = browser(pw, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(BASE + "/login", wait_until="domcontentloaded")
        log("LOGIN_WINDOW_OPEN: log in to @heroverse.official in this window (up to 15 min)")
        for _ in range(180):
            if logged_in(ctx):
                log("LOGGED_IN")
                ctx.close()
                return 0
            time.sleep(5)
        log("LOGIN_TIMEOUT")
        ctx.close()
        return 1


def cmd_status(args):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = browser(pw, headless=True)
        ok = logged_in(ctx)
        ctx.close()
    print("LOGGED_IN" if ok else "NOT_LOGGED_IN")
    return 0 if ok else 1


def collect_videos(page, max_videos):
    videos = []
    page.on("response", lambda r: "/api/post/item_list" in r.url and videos.extend(core.videos_from_api(json_of(r))))
    page.goto(f"{BASE}/@{core.HANDLE}", wait_until="domcontentloaded")
    pause((4, 8))
    if challenged(page):
        return None   # E134: a puzzle instead of the videos; never solved, reported
    for _ in range(4):
        if len(videos) >= max_videos:
            break
        page.mouse.wheel(0, 2500)
        pause((3, 7))
    if not videos:   # the first page of items can come inside the HTML instead of an API response
        for a in page.locator(f'a[href*="/@{core.HANDLE}/video/"]').all():
            vid = (a.get_attribute("href") or "").rstrip("/").split("/")[-1]
            if core.VIDEO_ID.match(vid):
                videos.append({"video_id": vid, "desc": "", "create_time": None, "comments": None})
    uniq = {}
    for v in videos:
        uniq.setdefault(v["video_id"], v)
    return list(uniq.values())[:max_videos]


def open_video(page, vid):
    page.goto(f"{BASE}/@{core.HANDLE}/video/{vid}", wait_until="domcontentloaded")
    pause((3, 6))
    if f"/@{core.HANDLE}/video/{vid}" not in page.url:
        raise RuntimeError(f"NOT_OUR_VIDEO_PAGE {vid}")
    if challenged(page):
        raise RuntimeError("CHALLENGE")
    icon = first(page, "comment_icon", 3000)
    if icon is not None and first(page, "comment_item", 2500) is None:
        icon.first.click()
        pause((2, 4))


def cmd_comments(args):
    from playwright.sync_api import sync_playwright
    ledger = core.read_json(LEDGER, core.empty_ledger())
    found = []
    with sync_playwright() as pw:
        ctx = browser(pw, headless=args.headless)
        if not logged_in(ctx):
            log("NOT_LOGGED_IN (comments are read anyway where TikTok shows them)")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        videos = collect_videos(page, args.max_videos)
        code, why = core.listing_outcome(videos)
        if code:
            log(why)
            ctx.close()
            return code
        core.write_json(OWN, {"handle": core.HANDLE, "at": core.iso(core.now_utc()), "videos": videos})
        current = {"vid": None}
        page.on("response", lambda r: "/api/comment/list" in r.url and current["vid"]
                and found.extend(core.comments_from_api(json_of(r), current["vid"])))
        for v in videos:
            if v.get("comments") == 0:
                continue
            current["vid"] = v["video_id"]
            try:
                open_video(page, v["video_id"])
                lst = first(page, "comment_list", 3000)
                for _ in range(3):
                    if lst is not None:
                        lst.first.hover()
                    page.mouse.wheel(0, 1800)
                    pause((2, 5))
            except RuntimeError as e:
                log(f"SKIP_VIDEO {v['video_id']} {e}")
                if "CHALLENGE" in str(e):
                    break
            current["vid"] = None
            pause((6, 20))
        ctx.close()
    desc = {v["video_id"]: v.get("desc", "") for v in videos}
    new = core.new_comments(found, ledger)
    for c in new:
        c["video_desc"] = desc.get(c["video_id"], "")
    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    core.write_json(out, {"handle": core.HANDLE, "at": core.iso(core.now_utc()), "videos": len(videos), "comments": new})
    log(f"COMMENTS videos={len(videos)} read={len(found)} new={len(new)} -> {out}")
    return 0


def find_comment(page, item):
    """The comment's container on the open video page, by its author and text, scrolling the list a few times."""
    snippet = (item.get("comment_text") or "").strip()[:40]
    for _ in range(6):
        items = first(page, "comment_item", 3000)
        if items is not None:
            for el in items.all():
                try:
                    text = el.inner_text(timeout=1500)
                except Exception:  # noqa: BLE001
                    continue
                if (not snippet or snippet in text) and (not item.get("author") or item["author"] in text):
                    return el
        page.mouse.wheel(0, 1500)
        pause((2, 4))
    return None


def wait_api(page, fragment, action, timeout=15000):
    with page.expect_response(lambda r: fragment in r.url, timeout=timeout) as info:
        action()
    return json_of(info.value) or {}


def act(page, item, ledger, dry):
    cid = item["comment_id"]
    open_video(page, item["video_id"])
    el = find_comment(page, item)
    if el is None:
        return "COMMENT_NOT_FOUND"
    like, reply = first(el, "comment_like", 2000), first(el, "comment_reply", 2000)
    if dry:
        return f"DRY_RUN_FOUND like={'yes' if like is not None else 'no'} reply={'yes' if reply is not None else 'no'}"
    if reply is None:
        return "REPLY_BUTTON_NOT_FOUND"
    entry = ledger["actions"][cid] = {"video_id": item["video_id"], "state": "ATTEMPTING", "at": core.iso(core.now_utc())}
    core.write_json(LEDGER, ledger)
    if like is not None and not item.get("liked_by_us"):
        body = wait_api(page, "/api/comment/digg", lambda: like.first.click())
        entry["liked"] = body.get("status_code") == 0
        core.write_json(LEDGER, ledger)
        pause(core.SHORT_PAUSE)
    reply.first.click()
    pause(core.SHORT_PAUSE)
    box = first(page, "reply_input", 4000)
    if box is None:
        entry["state"] = "UNCERTAIN"
        entry["why"] = "REPLY_INPUT_NOT_FOUND"
        return entry["why"]
    box.last.click()
    page.keyboard.type(item["text"].strip(), delay=random.randint(60, 140))
    pause(core.SHORT_PAUSE)
    post = first(page, "reply_post", 4000)
    try:
        body = wait_api(page, "/api/comment/publish", (lambda: post.last.click()) if post is not None
                        else (lambda: page.keyboard.press("Enter")))
    except Exception as e:  # noqa: BLE001
        entry["state"], entry["why"] = "UNCERTAIN", f"NO_PUBLISH_RESPONSE {type(e).__name__}"
        return entry["why"]
    if body.get("status_code") == 0:
        entry["state"], entry["reply_cid"] = "REPLIED", str((body.get("comment") or {}).get("cid", ""))
    else:
        entry["state"], entry["why"] = "UNCERTAIN", f"PUBLISH_STATUS {body.get('status_code')}"
    entry["at"] = core.iso(core.now_utc())
    return entry["state"]


def cmd_reply(args):
    from playwright.sync_api import sync_playwright
    data = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    ledger = core.read_json(LEDGER, core.empty_ledger())
    own = {v["video_id"] for v in core.read_json(OWN, {}).get("videos", [])}
    todo, skips, refused, wait = core.plan(data.get("replies", []), ledger, own, core.now_utc(),
                                           args.max or core.RUN_CAP, policy())
    for r in refused:
        log(f"REFUSED {r['comment_id']} {r['problems']}")
    if not args.dry_run:
        for s in skips:
            ledger["actions"][s["comment_id"]] = {"video_id": s["video_id"], "state": "SKIPPED",
                                                  "reason": s.get("reason"), "at": core.iso(core.now_utc())}
        core.write_json(LEDGER, ledger)
    log(f"PLAN act={len(todo)} skip={len(skips)} refused={len(refused)} wait={wait} dry_run={args.dry_run}")
    if not todo:
        return 0
    with sync_playwright() as pw:
        ctx = browser(pw, headless=args.headless)
        if not logged_in(ctx) and not args.dry_run:
            log("NOT_LOGGED_IN: run `runner.py login` once (the owner logs in by hand)")
            ctx.close()
            return 3
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for item, wait_s in zip(todo, core.pauses(len(todo))):
            if wait_s:
                log(f"PAUSE {int(wait_s)} s")
                time.sleep(wait_s)
            try:
                result = act(page, item, ledger, args.dry_run)
            except RuntimeError as e:
                result = str(e)
            finally:
                if not args.dry_run:
                    core.write_json(LEDGER, ledger)
            log(f"COMMENT {item['comment_id']} {result}")
            if result == "CHALLENGE":
                break
        ctx.close()
    return 0


def cmd_probe(args):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = browser(pw, headless=args.headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        print("logged_in", logged_in(ctx))
        try:
            open_video(page, args.video_id)
        except RuntimeError as e:
            print(e)
        for key, sels in SELECTORS.items():
            if key.startswith("_"):
                continue
            hits = [f"{s}={page.locator(s).count()}" for s in sels]
            print(key, " ".join(hits))
        ctx.close()
    return 0


def cmd_story(args):
    print("STORY_WEB_UNSUPPORTED: TikTok Stories are posted from the mobile app; the web upload "
          "(tiktok.com/tiktokstudio/upload) has no Story option (README.md, verified 2026-10-28). Nothing was done.")
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--headless", action="store_true", help="no visible window (TikTok may challenge it sooner)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login")
    sub.add_parser("status")
    c = sub.add_parser("comments")
    c.add_argument("--out", default=str(HERE / "out" / "comments.json"))
    c.add_argument("--max-videos", type=int, default=20)
    r = sub.add_parser("reply")
    r.add_argument("--in", dest="inp", required=True)
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--max", type=int, default=0)
    p = sub.add_parser("probe")
    p.add_argument("video_id")
    s = sub.add_parser("story")
    s.add_argument("video_id")
    args = ap.parse_args(argv)
    fn = {"login": cmd_login, "status": cmd_status, "comments": cmd_comments, "reply": cmd_reply,
          "probe": cmd_probe, "story": cmd_story}[args.cmd]
    if args.cmd in ("story", "status"):
        return fn(args)
    with Lock():
        return fn(args)


if __name__ == "__main__":
    sys.exit(main())
