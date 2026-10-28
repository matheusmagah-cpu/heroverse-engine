#!/usr/bin/env python3
"""HeroVerse ChatGPT image runner: on the owner's Windows PC, in the runner's OWN Chrome profile
(C:\\HeroVerse\\chatgpt-runner\\profile), logged in once by the owner. chatgpt.com answers cloud IPs with a Cloudflare
challenge, so image requests run here; cloud agents reach it through Desktop Commander (README.md "Bridge").

  runner.py login                                  a visible Chrome window at chatgpt.com; the owner signs in (once)
  runner.py status                                 LOGGED_IN / NOT_LOGGED_IN (the session cookie's name only)
  runner.py image --prompt FILE --ref IMG... --out DIR [--id ID] [--dry-run]
                                                   ONE 16:9 image from the prompt and the reference images
  runner.py job JOB.json [--dry-run]               the bridge: refs downloaded by URL and sha256-checked, then `image`
  runner.py probe                                  which page elements are found on chatgpt.com; read-only

One request at a time (runner.lock), 3-8 s between steps, 3 min between requests, 30 a day. A challenge page or a
usage-limit message stops the run (exit 4 CHALLENGE, 5 LIMIT) and is reported: nothing is solved or worked around,
no fingerprint masking, no proxy. ledger.json is written before the prompt is sent, so nothing is sent twice.
Cookies and passwords are never read, copied or logged: only the presence of the session cookie's name.
Exit codes: 0 image saved (or dry run ok), 2 job invalid, 3 not logged in, 4 challenge, 5 limit, 6 no image,
7 refused by the gate (cap, gap, already done), 8 runner busy.
"""
import argparse
import json
import os
from pathlib import Path
import random
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chatgpt_core as core  # noqa: E402

PROFILE = HERE / "profile"
LEDGER = HERE / "ledger.json"
LOG = HERE / "logs" / "runner.log"
LOCK = HERE / "runner.lock"
REFS = HERE / "refs"
BASE = "https://chatgpt.com/"
SESSION_COOKIE = "__Secure-next-auth.session-token"
SEL = {
    "composer": ["#prompt-textarea", "div[contenteditable='true'][id='prompt-textarea']", "div.ProseMirror[contenteditable='true']"],
    "file_input": ["input[type='file'][multiple]", "input[type='file']"],
    "send": ["button[data-testid='send-button']", "#composer-submit-button", "button[aria-label='Send prompt']"],
    "stop": ["button[data-testid='stop-button']", "button[aria-label='Stop streaming']"],
    "assistant": ["[data-message-author-role='assistant']"],
    "login_button": ["button[data-testid='login-button']", "a[href*='auth/login']"],
}


class Stop(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def log(msg):
    LOG.parent.mkdir(exist_ok=True)
    line = f"{core.iso(core.now_utc())} {msg}"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def pause(lo_hi=core.STEP_PAUSE):
    time.sleep(random.uniform(*lo_hi))


class Lock:
    def __enter__(self):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
        except FileExistsError:
            raise Stop(8, "RUNNER_BUSY (runner.lock: another request is running, or one died; check before deleting)")
        return self

    def __exit__(self, *exc):
        LOCK.unlink(missing_ok=True)


def browser(pw, headless=False):
    PROFILE.mkdir(exist_ok=True)
    return pw.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=headless,
                                                 viewport={"width": 1366, "height": 900}, accept_downloads=True)


def logged_in(ctx):
    # names only: the value of a cookie is never read into anything that is printed or stored
    return any(c["name"].startswith(SESSION_COOKIE) for c in ctx.cookies(BASE))


def first(scope, key, timeout=5000):
    for sel in SEL[key]:
        loc = scope.locator(sel)
        try:
            loc.first.wait_for(state="attached", timeout=timeout)
            return loc
        except Exception:  # noqa: BLE001
            continue
    return None


def page_block(page):
    try:
        text = page.title() + "\n" + page.inner_text("body", timeout=5000)
    except Exception:  # noqa: BLE001
        return None
    return core.blocked(text)


def check_block(page, where):
    b = page_block(page)
    if b:
        kind, hint = b
        raise Stop(4 if kind == "CHALLENGE" else 5, f"{kind} at {where}: '{hint}' (nothing solved; the owner looks at the window)")


# ---------- commands ----------

def cmd_login(args):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = browser(pw)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(BASE + "auth/login", wait_until="domcontentloaded")
        log("LOGIN_WINDOW_OPEN: sign in to ChatGPT in this window (up to 15 min); the window closes by itself")
        for _ in range(180):
            if logged_in(ctx):
                log("LOGGED_IN")
                time.sleep(5)
                ctx.close()
                return 0
            time.sleep(5)
        ctx.close()
    log("LOGIN_TIMEOUT")
    return 3


def cmd_status(args):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = browser(pw, headless=True)
        ok = logged_in(ctx)
        ctx.close()
    print("LOGGED_IN" if ok else "NOT_LOGGED_IN")
    return 0 if ok else 3


def newest_image(page):
    """(src, natural width) of the largest image in the last assistant message, or (None, 0)."""
    return page.evaluate("""() => {
        const msgs = document.querySelectorAll("[data-message-author-role='assistant']");
        const scope = msgs.length ? msgs[msgs.length - 1].closest('article') || msgs[msgs.length - 1] : document;
        let best = [null, 0];
        for (const img of scope.querySelectorAll('img')) {
            if (img.naturalWidth > best[1] && img.complete) best = [img.currentSrc || img.src, img.naturalWidth];
        }
        return best;
    }""")


def last_answer_text(page):
    msgs = page.locator(SEL["assistant"][0])
    try:
        return msgs.last.inner_text(timeout=2000) if msgs.count() else ""
    except Exception:  # noqa: BLE001
        return ""


def wait_for_image(page):
    start, stable, last = time.time(), 0, None
    while time.time() - start < core.WAIT_MAX:
        time.sleep(5)
        check_block(page, "answer")
        b = core.blocked(last_answer_text(page))
        if b:
            raise Stop(5 if b[0] == "LIMIT" else 4, f"{b[0]} in the answer: '{b[1]}'")
        streaming = first(page, "stop", 500) is not None
        src, width = newest_image(page)
        if src and width >= 1000 and not streaming:
            stable = stable + 1 if src == last else 0
            last = src
            if stable >= 2:   # the same final image for 10 s
                return src
    text = last_answer_text(page)[:300].replace("\n", " ")
    raise Stop(6, f"NO_IMAGE after {core.WAIT_MAX} s; answer: {text!r}")


def fetch_image(page, src):
    """The full file behind the generated image: the page's own download button when present, else the image URL
    fetched by the browser context (its session is used by the browser, never read by this script)."""
    for label in ("Download this image", "Download"):
        btn = page.get_by_role("button", name=label)
        try:
            if btn.count():
                with page.expect_download(timeout=30000) as d:
                    btn.last.click()
                return Path(d.value.path()).read_bytes()
        except Exception:  # noqa: BLE001
            continue
    r = page.context.request.get(src, timeout=60000)
    if not r.ok:
        raise Stop(6, f"IMAGE_FETCH_HTTP_{r.status}")
    return r.body()


def make_image(job, ref_paths, out_dir, dry_run):
    from playwright.sync_api import sync_playwright
    refs = [(str(p), Path(p).read_bytes()) for p in ref_paths]
    bad = core.job_problems(job, refs)
    if bad:
        raise Stop(2, "JOB_INVALID " + "; ".join(bad))
    ledger = core.read_json(LEDGER, core.empty_ledger())
    why = core.gate(ledger, job["id"], core.now_utc())
    if why and not dry_run:
        raise Stop(7, why)
    with sync_playwright() as pw:
        ctx = browser(pw)
        try:
            if not logged_in(ctx):
                raise Stop(3, "NOT_LOGGED_IN: the owner runs `runner.py login` once")
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(BASE, wait_until="domcontentloaded")
            pause()
            check_block(page, "chatgpt.com")
            if first(page, "login_button", 2000) is not None and first(page, "composer", 3000) is None:
                raise Stop(3, "NOT_LOGGED_IN (the page offers a login)")
            composer, files = first(page, "composer", 15000), first(page, "file_input", 5000)
            if composer is None or files is None:
                raise Stop(6, f"PAGE_CHANGED composer={composer is not None} file_input={files is not None} (runner.py probe)")
            if dry_run:
                log(f"DRY_RUN_OK {job['id']}: logged in, composer and file input found, {len(refs)} refs valid, gate={why}")
                return 0
            ledger["requests"][job["id"]] = {"state": "SENDING", "at": core.iso(core.now_utc()), "still": job.get("still")}
            core.write_json(LEDGER, ledger)
            started = core.now_utc()
            files.first.set_input_files([p for p, _ in refs])
            pause((6, 12))   # the uploads finish
            composer.first.click()
            page.keyboard.insert_text(core.full_prompt(job["prompt"]))
            pause()
            send = first(page, "send", 10000)
            if send is None:
                raise Stop(6, "SEND_BUTTON_NOT_FOUND")
            send.first.click()
            ledger["requests"][job["id"]]["state"] = "SENT"
            core.write_json(LEDGER, ledger)
            src = wait_for_image(page)
            pause()
            data = fetch_image(page, src)
            ext = core.extension(data) or ".png"
            out = Path(out_dir)
            out.mkdir(parents=True, exist_ok=True)
            (out / (job["id"] + ext)).write_bytes(data)
            rec = core.record(job, refs, data, page.url, started, core.now_utc())
            rec["file"] = job["id"] + ext
            core.write_json(out / (job["id"] + ".json"), rec)
            ledger["requests"][job["id"]].update(state="SAVED", file=str(out / rec["file"]), sha256=rec["sha256"],
                                                 conversation_url=page.url)
            core.write_json(LEDGER, ledger)
            log(f"IMAGE_SAVED {out / rec['file']} size={rec['size']} 16:9={rec['is_16_9']} sha256={rec['sha256'][:12]}")
            return 0
        except Stop as s:
            if job["id"] in ledger["requests"] and ledger["requests"][job["id"]]["state"] in ("SENDING", "SENT"):
                ledger["requests"][job["id"]].update(state="UNCERTAIN" if s.code == 6 else "STOPPED", why=str(s))
                core.write_json(LEDGER, ledger)
            raise
        finally:
            ctx.close()


def cmd_image(args):
    job = {"id": args.id or Path(args.prompt).stem, "prompt": Path(args.prompt).read_text(encoding="utf-8")}
    return make_image(job, args.ref, args.out, args.dry_run)


def cmd_job(args):
    """The bridge's PC side: a job written by a cloud agent (bridge.py job) names its refs by URL and sha256."""
    job = read_job(args.job)
    return make_image(job, fetch_refs(job), HERE / "out" / job["id"], args.dry_run)


def read_job(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:   # E143: a missing or broken job file is a named refusal, not a traceback
        raise Stop(2, f"JOB_UNREADABLE {path}: {type(e).__name__}") from None


def fetch_refs(job):
    """The job's references in refs/, downloaded by URL when missing and checked by sha256."""
    paths = []
    for r in job.get("refs", []):
        dest = REFS / r["name"]
        if not dest.exists() or core.sha256(dest.read_bytes()) != r["sha256"]:
            REFS.mkdir(exist_ok=True)
            with urllib.request.urlopen(r["url"], timeout=60) as resp:
                dest.write_bytes(resp.read())
        if core.sha256(dest.read_bytes()) != r["sha256"]:
            raise Stop(2, f"REF_SHA256_MISMATCH {r['name']}")
        paths.append(dest)
    return paths


def cmd_probe(args):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = browser(pw)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        print("logged_in", logged_in(ctx))
        page.goto(BASE, wait_until="domcontentloaded")
        time.sleep(6)
        print("title", page.title(), "| block", page_block(page))
        for key, sels in SEL.items():
            print(key, " ".join(f"{s}={page.locator(s).count()}" for s in sels))
        ctx.close()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login")
    sub.add_parser("status")
    sub.add_parser("probe")
    i = sub.add_parser("image")
    i.add_argument("--prompt", required=True)
    i.add_argument("--ref", nargs="+", required=True)
    i.add_argument("--out", required=True)
    i.add_argument("--id")
    i.add_argument("--dry-run", action="store_true")
    j = sub.add_parser("job")
    j.add_argument("job")
    j.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    fn = {"login": cmd_login, "status": cmd_status, "probe": cmd_probe, "image": cmd_image, "job": cmd_job}[args.cmd]
    try:
        if args.cmd == "status":
            return fn(args)
        with Lock():
            return fn(args)
    except Stop as s:
        log(str(s))
        return s.code


if __name__ == "__main__":
    sys.exit(main())
