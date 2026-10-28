#!/usr/bin/env python3
"""Drive the owner's ChatGPT desktop app (already signed in) for ONE image. Owner, 2026-10-28: "Use o programa que tem
no meu computador" (chatgpt.com in a browser stops at Cloudflare's check, which we never work around) and "tem que
simular uma ação humana".

  app_driver.py status                  APP_READY / APP_NOT_RUNNING
  app_driver.py job JOB.json            the bridge: refs by URL and sha256 (bridge.py job), then one image
  app_driver.py image --prompt FILE --ref IMG... --out DIR [--id ID]

How: Windows UI Automation (pywinauto). The app is Electron and shows its controls to UI Automation only while
Windows' screen-reader flag is on, so the driver turns that OS flag on for the run and restores it. Only the main
area (x > 350) of a NEW chat is ever read: the sidebar with the owner's other chats is never read or recorded.
Steps, like a person: the mouse glides to each control and clicks, with pauses of seconds between steps; "Novo chat",
mode "Chat", the reference files pasted into the composer, the prompt pasted, Enter; the image is awaited (a large
image in the new chat and no stop button) and saved with the app's own download action.
While it runs the app is in front and busy and the clipboard is replaced: nobody should use the PC's ChatGPT then.
One request at a time (runner.lock), 3 min apart at least, 30 a day (chatgpt_core). A limit, error or verification
text in the new chat stops it for the owner to look at: nothing is solved or worked around. No credential is read.
Exit codes: 0 saved, 2 job invalid, 4 verification, 5 limit, 6 no image or the app changed, 7 gate, 8 busy,
9 app not running.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chatgpt_core as core  # noqa: E402

LEDGER = HERE / "ledger.json"
LOG = HERE / "logs" / "driver.log"
LOCK = HERE / "runner.lock"
REFS = HERE / "refs"
MAIN_X = 350                      # the main area starts right of the sidebar
DOWNLOADS = Path(os.environ.get("USERPROFILE", str(HERE))) / "Downloads"
SPI_GETSCREENREADER, SPI_SETSCREENREADER, SPIF_SENDCHANGE = 0x0046, 0x0047, 0x2
PLUS_NAME, SEND_NAME = "Adicionar arquivos e mais", "Enviar"   # pt-BR app, 2026-10-28
OPEN_DIALOG = ("Abrir", "Open")
SAVE_NAMES = ("Baixar", "Baixar imagem", "Download", "Salvar", "Salvar imagem")
FLAG_FILE = HERE / "screenreader.was"   # the flag's value before a run, kept until the run restores it


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


class ScreenReaderFlag:
    """Windows' screen-reader flag on for the run (Electron then exposes its UI to UI Automation), restored after."""
    def __enter__(self):
        self.u = ctypes.windll.user32
        if FLAG_FILE.exists():                 # a run that was killed: its saved value is the real one
            self.was = int(FLAG_FILE.read_text() or 0)
        else:
            cur = ctypes.c_int(0)
            self.u.SystemParametersInfoW(SPI_GETSCREENREADER, 0, ctypes.byref(cur), 0)
            self.was = cur.value
            FLAG_FILE.write_text(str(self.was))
        self.u.SystemParametersInfoW(SPI_SETSCREENREADER, 1, None, SPIF_SENDCHANGE)
        time.sleep(2)
        return self

    def __exit__(self, *exc):
        self.u.SystemParametersInfoW(SPI_SETSCREENREADER, self.was, None, SPIF_SENDCHANGE)
        FLAG_FILE.unlink(missing_ok=True)


# ---------- a person's hand ----------

def glide_click(el, double=False):
    """Move the mouse along a curved path to a random point inside the control, wait a moment, click."""
    from pywinauto import mouse
    r = el.rectangle()
    tx = random.randint(r.left + max(2, r.width() // 4), r.right - max(2, r.width() // 4))
    ty = random.randint(r.top + max(2, r.height() // 4), r.bottom - max(2, r.height() // 4))
    import ctypes.wintypes as wt
    pt = wt.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    sx, sy = pt.x, pt.y
    steps = random.randint(18, 35)
    bend = random.uniform(-0.25, 0.25)
    for i in range(1, steps + 1):
        t = i / steps
        e = t * t * (3 - 2 * t)                      # ease in and out
        x = sx + (tx - sx) * e + bend * (ty - sy) * t * (1 - t)
        y = sy + (ty - sy) * e - bend * (tx - sx) * t * (1 - t)
        mouse.move(coords=(int(x), int(y)))
        time.sleep(random.uniform(0.008, 0.025))
    time.sleep(random.uniform(0.15, 0.5))
    (mouse.double_click if double else mouse.click)(coords=(tx, ty))


def keys(seq):
    from pywinauto.keyboard import send_keys
    time.sleep(random.uniform(0.2, 0.6))
    send_keys(seq)


def clip_text(text):
    subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ([Console]::In.ReadToEnd())"],
                   input=text, text=True, check=True, timeout=30, encoding="utf-8")


# ---------- the app ----------

def app_window():
    from pywinauto import Desktop
    for w in Desktop(backend="uia").windows(title="ChatGPT"):
        if (w.element_info.class_name or "").startswith("Chrome_WidgetWin"):
            return w
    raise Stop(9, "APP_NOT_RUNNING: open the ChatGPT app (signed in) and run again")


def main_controls(w, types=("Button", "Image", "Text", "Edit")):
    """Controls of the main area only (x > MAIN_X): the sidebar is never read."""
    out = []
    for el in w.descendants():
        try:
            if el.rectangle().left >= MAIN_X and el.element_info.control_type in types:
                out.append(el)
        except Exception:  # noqa: BLE001
            continue
    return out


def named(w, names, control_type="Button"):
    names = (names,) if isinstance(names, str) else names
    for el in main_controls(w, (control_type,)):
        if (el.element_info.name or "").strip() in names:
            return el
    return None


def composer(w):
    box = [e for e in main_controls(w, ("Edit",)) if "ProseMirror" in (e.element_info.class_name or "")]
    return box[0] if box else None


def new_chat_button(w):
    """The topmost "Novo chat" button (the sidebar's own). E145: a window found through Desktop().windows() is a
    wrapper (no child_window): only descendants() and element_info are used, and only the button's name is compared."""
    found = [e for e in w.descendants() if e.element_info.control_type == "Button"
             and (e.element_info.name or "").strip() == "Novo chat"]
    return min(found, key=lambda e: e.rectangle().top) if found else None


def open_new_chat(w):
    w.set_focus()
    pause((1, 2))
    new = new_chat_button(w)
    if new is None:
        raise Stop(6, "APP_CHANGED: no 'Novo chat' button")
    glide_click(new)
    pause((3, 5))
    chat = named(w, "Chat")
    if chat is not None:
        glide_click(chat)
        pause((1, 3))
    box = composer(w)
    if box is None:
        raise Stop(6, "APP_CHANGED: no composer in the new chat")
    return box


def menu_item(w, prefix):
    """An entry of the composer's "+" menu, opened like a person would."""
    plus = named(w, PLUS_NAME)
    if plus is None:
        raise Stop(6, "APP_CHANGED: no '+' (Adicionar arquivos e mais) button")
    glide_click(plus)
    pause((1, 2))
    for el in main_controls(w, ("Button", "MenuItem")):
        if (el.element_info.name or "").startswith(prefix):
            return el
    keys("{ESC}")
    raise Stop(6, f"APP_CHANGED: no '{prefix}' in the '+' menu")


def file_dialog(w):
    """The app's own Open dialog (a Windows #32770 dialog owned by the app: a child of its window or a top-level
    window of the same process). E146: it is not found among the desktop's top-level windows by its title alone."""
    from pywinauto import Desktop
    pid = w.element_info.process_id
    cands = [d for d in w.descendants() if d.element_info.control_type == "Window"]
    cands += [d for d in Desktop(backend="uia").windows() if d.element_info.process_id == pid]
    for d in cands:
        if d.element_info.class_name == "#32770" or (d.element_info.name or "") in OPEN_DIALOG:
            return d
    return None


def close_file_dialog(w):
    """A file dialog left open by an earlier run is cancelled first."""
    d = file_dialog(w)
    if d is not None:
        d.set_focus()
        keys("{ESC}")
        pause((1, 2))


def attach(w, refs):
    """The app's own file dialog: '+' > 'Adicionar fotos e arquivos', the files' full paths in the name box, Enter."""
    glide_click(menu_item(w, "Adicionar fotos e arquivos"))
    dlg = None
    for _ in range(30):
        time.sleep(0.5)
        dlg = file_dialog(w)
        if dlg is not None:
            break
    if dlg is None:
        raise Stop(6, "APP_CHANGED: the file dialog did not open")
    dlg.set_focus()
    pause((1, 2))
    clip_text(" ".join(f'"{Path(p).resolve()}"' for p in refs))
    keys("%n")                                 # the dialog's own "Nome" box (Alt+N)
    keys("^a^v")
    pause((1, 2))
    keys("{ENTER}")
    pause((8, 14))                             # the uploads finish


def send(w, box, refs, prompt, before_send):
    glide_click(menu_item(w, "Criar imagem"))  # the image tool, chosen in the menu
    pause((1, 3))
    attach(w, refs)
    glide_click(composer(w) or box)
    clip_text(prompt)
    keys("^v")
    pause()
    btn = named(w, SEND_NAME)
    if btn is None:
        raise Stop(6, "APP_CHANGED: no 'Enviar' button")
    before_send()                              # the ledger says SENDING before the click, never after
    glide_click(btn)


def biggest_image(w):
    best = None
    for el in main_controls(w, ("Image",)):
        r = el.rectangle()
        if r.width() >= 300 and r.height() >= 150 and (best is None or r.width() * r.height() > best[1]):
            best = (el, r.width() * r.height())
    return best[0] if best else None


def new_chat_text(w):
    return "\n".join((el.element_info.name or "") for el in main_controls(w, ("Text",)))


def wait_image(w):
    start, seen = time.time(), 0
    while time.time() - start < core.WAIT_MAX:
        time.sleep(random.uniform(5, 9))
        b = core.blocked(new_chat_text(w))
        if b:
            raise Stop(4 if b[0] == "CHALLENGE" else 5, f"{b[0]} in the new chat: '{b[1]}'")
        img = biggest_image(w)
        if img is not None and named(w, SEND_NAME) is not None:   # while it answers, the stop button replaces Enviar
            seen += 1
            if seen >= 2:                        # the same finished state twice
                return img
        else:
            seen = 0
    raise Stop(6, f"NO_IMAGE after {core.WAIT_MAX} s")


def save_image(w, img):
    """The app's own download action: the image opened, its download button; the file lands in Downloads, or a Save
    dialog takes our file name."""
    before = {p.name for p in DOWNLOADS.glob("*")} if DOWNLOADS.exists() else set()
    glide_click(img)
    pause((2, 4))
    btn = named(w, SAVE_NAMES)
    if btn is None:
        names = sorted({(e.element_info.name or "")[:30] for e in main_controls(w, ("Button",))})
        keys("{ESC}")
        raise Stop(6, "SAVE_BUTTON_NOT_FOUND; buttons in the new chat: " + ", ".join(n for n in names if n)[:400])
    glide_click(btn)
    pause((2, 4))
    from pywinauto import Desktop
    if any((d.element_info.name or "") in ("Salvar como", "Save As") for d in Desktop(backend="uia").windows()):
        keys("{ENTER}")                          # the dialog's own folder and name (Downloads by default)
        pause((2, 4))
    for _ in range(40):
        new = [p for p in DOWNLOADS.glob("*") if p.name not in before and p.is_file()
               and not p.name.endswith((".crdownload", ".tmp", ".partial"))]
        if new:
            keys("{ESC}")
            return max(new, key=lambda p: p.stat().st_mtime)
        time.sleep(2)
    keys("{ESC}")
    raise Stop(6, "DOWNLOAD_NOT_FOUND in Downloads")


def make_image(job, ref_paths, out_dir):
    refs = [(str(p), Path(p).read_bytes()) for p in ref_paths]
    bad = core.job_problems(job, refs)
    if bad:
        raise Stop(2, "JOB_INVALID " + "; ".join(bad))
    ledger = core.read_json(LEDGER, core.empty_ledger())
    why = core.gate(ledger, job["id"], core.now_utc())
    if why:
        raise Stop(7, why)
    log("APP_BUSY: the ChatGPT app is driven now (a new chat; the clipboard is replaced); do not use it until IMAGE_SAVED")
    out = Path(out_dir)
    with ScreenReaderFlag():
        w = app_window()
        close_file_dialog(w)
        box = open_new_chat(w)
        started = core.now_utc()

        def sending():
            ledger["requests"][job["id"]] = {"state": "SENDING", "at": core.iso(core.now_utc()),
                                             "still": job.get("still"), "client": "chatgpt-app"}
            core.write_json(LEDGER, ledger)
        try:
            send(w, box, [p for p, _ in refs], core.full_prompt(job["prompt"]), sending)
            ledger["requests"][job["id"]]["state"] = "SENT"
            core.write_json(LEDGER, ledger)
            img = wait_image(w)
            pause()
            src = save_image(w, img)
        except Stop as s:
            close_file_dialog(w)
            if job["id"] in ledger["requests"]:   # only a prompt that was sent is recorded (and never resent)
                ledger["requests"][job["id"]].update(state="UNCERTAIN" if s.code == 6 else "STOPPED", why=str(s))
                core.write_json(LEDGER, ledger)
            raise
    data = src.read_bytes()
    ext = core.extension(data) or src.suffix or ".png"
    out.mkdir(parents=True, exist_ok=True)
    (out / (job["id"] + ext)).write_bytes(data)
    rec = core.record(job, refs, data, None, started, core.now_utc())
    rec.update(file=job["id"] + ext, engine="ChatGPT desktop app, the owner's own account (driver on his PC)",
               downloaded_as=src.name)
    core.write_json(out / (job["id"] + ".json"), rec)
    ledger["requests"][job["id"]].update(state="SAVED", file=str(out / rec["file"]), sha256=rec["sha256"])
    core.write_json(LEDGER, ledger)
    log(f"IMAGE_SAVED {out / rec['file']} size={rec['size']} 16:9={rec['is_16_9']} sha256={rec['sha256'][:12]}")
    return 0


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


def status():
    with ScreenReaderFlag():
        w = app_window()
        return "APP_READY" if composer(w) is not None else "APP_OPEN_NO_COMPOSER"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    j = sub.add_parser("job")
    j.add_argument("job")
    i = sub.add_parser("image")
    i.add_argument("--prompt", required=True)
    i.add_argument("--ref", nargs="+", required=True)
    i.add_argument("--out", required=True)
    i.add_argument("--id")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "status":
            s = status()
            print(s)
            return 0 if s == "APP_READY" else 6
        with Lock():
            if args.cmd == "job":
                job = read_job(args.job)
                return make_image(job, fetch_refs(job), HERE / "out" / job["id"])
            job = {"id": args.id or Path(args.prompt).stem, "prompt": Path(args.prompt).read_text(encoding="utf-8")}
            return make_image(job, args.ref, args.out)
    except Stop as s:
        log(str(s))
        return s.code


if __name__ == "__main__":
    sys.exit(main())
