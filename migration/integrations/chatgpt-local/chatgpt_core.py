"""The ChatGPT app driver's rules, without the app (tested in the repository on every PR).

Ledger (ledger.json next to app_driver.py): {"requests": {job_id: {"state", "at", ...}}}. A job is written as
SENDING before the prompt is sent, so a run that dies never sends the same job twice by itself (it stays UNCERTAIN
until someone looks at the conversation).
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import struct

DAY_CAP = 30                       # images a day (a person's pace, well under any plan limit)
MIN_GAP = timedelta(minutes=3)     # between two requests
STEP_PAUSE = (3, 8)                # seconds between the steps of one request
WAIT_MAX = 600                     # seconds for one image
MAX_REFS = 4
JOB_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")
ASPECT = "Make exactly ONE image, a wide 16:9 landscape frame (not square). No text, captions or watermark in the image."
# words of a usage limit or a block in the assistant's answer or a banner (lower case)
LIMIT_HINTS = ("you've hit the", "you have hit the", "you've reached", "you have reached", "reached our limit",
               "image generation limit", "usage limit", "rate limit", "try again later", "try again after",
               "too many requests", "limit resets")
CHALLENGE_HINTS = ("verify you are human", "just a moment", "checking your browser", "unusual activity",
                   "are you a robot", "complete the security check")
LICENCE = {
    "terms": "OpenAI Terms of Use (https://openai.com/policies/terms-of-use/, effective January 1, 2026, read "
             "2026-10-28), 'Ownership of content'",
    "ownership": "\"As between you and OpenAI, and to the extent permitted by applicable law, you (a) retain your "
                 "ownership rights in Input and (b) own the Output. We hereby assign to you all our right, title, "
                 "and interest, if any, in and to Output.\"",
    "similar_output": "Output may not be unique; other users may receive similar output (same terms).",
    "automation_note": "The same terms forbid automatically or programmatically extracting data or Output; this image "
                       "was made by a UI Automation driver of the ChatGPT app in the owner's own session at the owner's explicit request "
                       "(2026-10-28), one at a time. The owner carries that account risk.",
    "usage_policies": "https://openai.com/policies/usage-policies/",
}


def now_utc():
    return datetime.now(timezone.utc)


def iso(t):
    return t.isoformat(timespec="seconds")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path, default):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def write_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)


def empty_ledger():
    return {"version": "chatgpt-local-ledger-v1", "requests": {}}


def size_of(data):
    """(width, height) of a PNG, JPEG or WebP, without an image library."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8X":
            return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
        if kind == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if kind == b"VP8L":
            b = int.from_bytes(data[21:25], "little")
            return (b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker, length = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + length
    return None


def extension(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    return None


def job_problems(job, ref_files):
    """Why a job may not be sent ([] = it may). ref_files: [(path, bytes)] already read."""
    out = []
    if not JOB_ID.match(str(job.get("id", ""))):
        out.append("JOB_ID_INVALID")
    if not (job.get("prompt") or "").strip():
        out.append("PROMPT_EMPTY")
    if len(job.get("prompt") or "") > 4000:
        out.append("PROMPT_TOO_LONG")
    if not 1 <= len(ref_files) <= MAX_REFS:
        out.append(f"REFS_COUNT {len(ref_files)} (1-{MAX_REFS})")
    want = {r.get("name"): r.get("sha256") for r in job.get("refs", []) if isinstance(r, dict)}
    for path, data in ref_files:
        if extension(data) is None:
            out.append(f"REF_NOT_AN_IMAGE {Path(path).name}")
        if want.get(Path(path).name) and want[Path(path).name] != sha256(data):
            out.append(f"REF_SHA256_MISMATCH {Path(path).name}")
    return out


def gate(ledger, job_id, now):
    """None when a request may start now; otherwise why not."""
    reqs = ledger.get("requests", {})
    if job_id in reqs:
        return f"ALREADY_{reqs[job_id].get('state', 'SEEN')} {job_id}"
    sent = [datetime.fromisoformat(r["at"]) for r in reqs.values() if r.get("state") != "REFUSED_BEFORE_SEND"]
    if sum(1 for t in sent if t.date() == now.date()) >= DAY_CAP:
        return "DAY_CAP_REACHED"
    if sent and now - max(sent) < MIN_GAP:
        return f"WAIT_MIN_GAP last request {iso(max(sent))}"
    return None


def full_prompt(prompt):
    return prompt.strip() + "\n\n" + ASPECT


def blocked(text):
    """('LIMIT' | 'CHALLENGE', the hint found) for a page or answer text, or None."""
    low = (text or "").lower()
    for h in CHALLENGE_HINTS:
        if h in low:
            return "CHALLENGE", h
    for h in LIMIT_HINTS:
        if h in low:
            return "LIMIT", h
    return None


def record(job, refs, data, conversation_url, started, finished):
    w_h = size_of(data)
    return {
        "id": job["id"], "status": "DRAFT", "engine": "ChatGPT desktop app, the owner's own account (driver on his PC)",
        "still": job.get("still"), "prompt": job["prompt"], "prompt_sent": full_prompt(job["prompt"]),
        "references": [{"name": Path(p).name, "sha256": sha256(d), "bytes": len(d), "size": list(size_of(d) or [])}
                       for p, d in refs],
        "conversation_url": conversation_url, "started_at": iso(started), "finished_at": iso(finished),
        "sha256": sha256(data), "bytes": len(data), "size": list(w_h) if w_h else None,
        "is_16_9": bool(w_h) and abs(w_h[0] / w_h[1] - 16 / 9) < 0.02,
        "licence": LICENCE, "generated_by": "HeroVerse pipeline (AI-generated image)",
    }
