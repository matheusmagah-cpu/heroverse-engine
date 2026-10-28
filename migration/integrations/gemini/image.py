#!/usr/bin/env python3
"""One image from Google's Gemini API with our approved stills as references (owner, 2026-10-28: a cloud image route
that does not depend on the PC). Key: repository secret HERO_GEMINI_API_KEY (the free AI Studio project, billing
disabled), only from the environment, sent in the x-goog-api-key header, never printed: every message that leaves
this script goes through `scrub`.

A request file (requests/<still>.json): {"still": still record path, "subject": who the references show,
"refs": [still record paths, APPROVED], "model": optional}. The scene's prompt is the still record's own prompt; each reference goes inline at its full
resolution (the repository file, checked against the sha256 its record names). One image, 16:9
(generationConfig.imageConfig.aspectRatio). The result is a DRAFT candidate (the image and its record: model,
model version, prompt, refs by sha256, time, size, sha256, licence) for Claude's still review; nothing is approved here.

Refusals (exit codes), never retried by this script and never a reason to enable billing:
  3 QUOTA_EXHAUSTED      429 / RESOURCE_EXHAUSTED (the free tier's daily or per-minute limit, or a limit of 0)
  4 BILLING_REQUIRED     the model needs a billed project (FAILED_PRECONDITION, "billing", "free tier ... not available")
  5 API_REFUSED          any other HTTP error (the API's own status and message, scrubbed)
  6 NO_IMAGE             an answer without an image (finishReason and text recorded)

usage: image.py models                         the image-capable models this key can see (GET, no generation)
       image.py generate REQUEST.json OUT_DIR  one image (needs HERO_GEMINI_API_KEY)
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
BASE = "https://generativelanguage.googleapis.com/v1beta/"
# "Nano Banana". Measured 2026-10-28 (evidence/gemini-image/20261028-free-tier.json): on the free key every image
# model answers 429 with free-tier limit 0, as the pricing page says ("Not available" on the Free Tier)
MODEL = "gemini-2.5-flash-image"
MAX_REFS = 3
TIMEOUT = 180
INSTRUCTION = ("The attached images are approved stills of {subject}: keep the face, skin tone, eyes and hair exactly "
               "as in them. Make ONE new image, a wide 16:9 frame, of this scene: ")
LICENCE = {
    "terms": "Gemini API Additional Terms of Service (https://ai.google.dev/gemini-api/terms), read 2026-10-28",
    "ownership": "Use of Generated Content: \"Google won't claim ownership over that content.\" \"Google may generate "
                 "the same or similar content for others and ... reserve[s] all rights to do so.\"",
    "unpaid_services": "Unpaid Services: Google uses submitted content and generated responses to provide, improve and "
                       "develop its products; human reviewers may read API input and output (our own stills only).",
    "use_policy": "Generative AI Prohibited Use Policy (https://policies.google.com/terms/generative-ai/use-policy)",
}


class Refusal(Exception):
    def __init__(self, code, name, detail):
        super().__init__(f"{name} {detail}")
        self.code, self.name, self.detail = code, name, detail


def scrub(text, key=None):
    """The text with the key (and anything shaped like a Google API key) removed."""
    text = str(text)
    if key:
        text = text.replace(key, "[KEY]")
    return re.sub(r"AIza[0-9A-Za-z_\-]{20,}", "[KEY]", text)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def size_of(data):
    """(width, height) of a PNG or JPEG, without an image library."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
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


def load_request(path, root=ROOT):
    """(still record, [(ref record, bytes)], problems)."""
    req = json.loads(Path(path).read_text())
    problems, refs = [], []
    still = json.loads((root / req["still"]).read_text())
    if not req.get("subject"):
        problems.append("SUBJECT_MISSING (who the references show, e.g. \"the same woman, Eve\")")
    if not still.get("prompt"):
        problems.append("STILL_HAS_NO_PROMPT")
    if not 1 <= len(req.get("refs", [])) <= MAX_REFS:
        problems.append(f"REFS_COUNT {len(req.get('refs', []))} (1-{MAX_REFS})")
    for r in req.get("refs", []):
        rec = json.loads((root / r).read_text())
        if rec.get("status") != "APPROVED":
            problems.append(f"REF_NOT_APPROVED {rec.get('id')}")
            continue
        data = (root / rec["repo_path"]).read_bytes()
        if sha256(data) != rec.get("sha256"):
            problems.append(f"REF_SHA256_MISMATCH {rec.get('id')}")
            continue
        refs.append((rec, data))
    return req, still, refs, problems


def payload(prompt, refs, subject):
    parts = [{"inline_data": {"mime_type": "image/jpeg" if data[:2] == b"\xff\xd8" else "image/png",
                              "data": base64.b64encode(data).decode()}} for _, data in refs]
    parts.append({"text": INSTRUCTION.format(subject=subject) + prompt})
    return {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "candidateCount": 1,
                                 "imageConfig": {"aspectRatio": "16:9"}}}


def classify(status, body, key=None):
    """The refusal for an HTTP error answer of the API."""
    try:
        err = json.loads(body).get("error", {})
    except Exception:  # noqa: BLE001
        err = {}
    msg = scrub(f"{err.get('status', '')} {err.get('message', body)[:400]}", key).strip()
    low = msg.lower()
    if status == 429 or "resource_exhausted" in low or "quota" in low:
        return Refusal(3, "QUOTA_EXHAUSTED", f"HTTP {status}: {msg}")
    if "billing" in low or "failed_precondition" in low or ("free tier" in low and "not available" in low):
        return Refusal(4, "BILLING_REQUIRED", f"HTTP {status}: {msg}")
    return Refusal(5, "API_REFUSED", f"HTTP {status}: {msg}")


def call(method, url, key, body=None, opener=urllib.request.urlopen):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with opener(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise classify(e.code, e.read().decode("utf-8", "replace"), key) from None
    except urllib.error.URLError as e:
        raise Refusal(5, "API_UNREACHABLE", scrub(e.reason, key)) from None


def image_of(answer):
    """(bytes, mime) of the first image part, or raise NO_IMAGE with why."""
    cands = answer.get("candidates") or []
    for part in ((cands[0].get("content") or {}).get("parts") or []) if cands else []:
        blob = part.get("inline_data") or part.get("inlineData")
        if blob and blob.get("data"):
            return base64.b64decode(blob["data"]), blob.get("mime_type") or blob.get("mimeType")
    why = {"finishReason": cands[0].get("finishReason") if cands else None,
           "promptFeedback": answer.get("promptFeedback"),
           "text": " ".join(p.get("text", "") for p in (((cands[0].get("content") or {}).get("parts")) or [])
                            if p.get("text"))[:300] if cands else ""}
    raise Refusal(6, "NO_IMAGE", json.dumps(why))


def generate(request_path, out_dir, key, now=None, opener=urllib.request.urlopen, root=ROOT):
    req, still, refs, problems = load_request(request_path, root)
    if problems:
        raise Refusal(2, "REQUEST_INVALID", "; ".join(problems))
    model = req.get("model") or MODEL
    now = now or datetime.now(timezone.utc)
    answer = call("POST", f"{BASE}models/{model}:generateContent", key, payload(still["prompt"], refs, req["subject"]), opener)
    data, mime = image_of(answer)
    ext = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"
    run = os.environ.get("GITHUB_RUN_ID") or now.strftime("%Y%m%d%H%M%S")
    name = f"{still['id']}-gemini-{run}-1"
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / (name + ext)).write_bytes(data)
    w_h = size_of(data)
    record = {
        "id": name, "still": still["id"], "status": "DRAFT", "engine": "gemini-api",
        "model": model, "model_version": answer.get("modelVersion"), "response_id": answer.get("responseId"),
        "prompt": still["prompt"], "instruction": INSTRUCTION.format(subject=req["subject"]), "aspect_ratio_requested": "16:9",
        "references": [{"record": rec["id"], "repo_path": rec["repo_path"], "sha256": rec["sha256"],
                        "bytes": len(d), "size": rec.get("size")} for rec, d in refs],
        "file": name + ext, "mime": mime, "sha256": sha256(data), "size": list(w_h) if w_h else None,
        "is_16_9": bool(w_h) and abs(w_h[0] / w_h[1] - 16 / 9) < 0.02,
        "usage": answer.get("usageMetadata"), "made_at": now.isoformat(timespec="seconds"),
        "licence": LICENCE, "generated_by": "HeroVerse pipeline (AI-generated image)",
    }
    (out / (name + ".json")).write_text(json.dumps(record, indent=1) + "\n")
    return record


def models(key, opener=urllib.request.urlopen):
    out, token = [], None
    for _ in range(5):
        url = f"{BASE}models?pageSize=200" + (f"&pageToken={token}" if token else "")
        body = call("GET", url, key, opener=opener)
        out += [m["name"].split("/", 1)[-1] for m in body.get("models", []) if "image" in m.get("name", "")
                and "generateContent" in m.get("supportedGenerationMethods", [])]
        token = body.get("nextPageToken")
        if not token:
            break
    return out


def main(argv):
    key = os.environ.get("HERO_GEMINI_API_KEY", "")
    if len(argv) < 2 or argv[1] not in ("models", "generate") or (argv[1] == "generate" and len(argv) != 4):
        print(__doc__)
        return 2
    if not key:
        print("KEY_MISSING HERO_GEMINI_API_KEY")
        return 2
    try:
        if argv[1] == "models":
            print(json.dumps({"image_models": models(key)}))
        else:
            rec = generate(argv[2], argv[3], key)
            print(json.dumps({k: rec[k] for k in ("id", "model", "model_version", "size", "is_16_9", "sha256")}))
        return 0
    except Refusal as r:
        print(f"{r.name}: {scrub(r.detail, key)}")
        return r.code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
