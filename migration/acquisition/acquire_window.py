#!/usr/bin/env python3
"""Recurring reference-window acquisition through the proven free RapidAPI route.

Two separate commands so the reservation is durable in Git before any effect:

  acquire_window.py reserve VIDEO START END   -> appends a RESERVED claim
  acquire_window.py execute VIDEO START END   -> one provider job, no retry
  acquire_window.py finish VIDEO START END RECEIPT -> records the terminal state

Reuses the qualified helpers of diagnostics/rapidapi-native-av/native_probe.py
(start, progress polling, guarded HTTPS delivery). Zero additional cost is
enforced from the provider's own quota headers: the free-plan hard-limit header
must be present, the unit plan must be the observed 500/day free tier, and the
remaining units must keep a floor. A request id is never sent twice, including
historical ones; failures are terminal for that window.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "diagnostics/rapidapi-native-av"))

LEDGER = HERE / "ledger.json"
HISTORIC = HERE.parent / "evidence/cloud-video-player-20261015/native-av-reservations.json"
FIRST_RESULT = HERE.parent / "evidence/cloud-video-player-20261015/rapidapi-native-first-result.json"
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
MIN_WINDOW, MAX_WINDOW = 10, 60  # native_probe media cap is 64 MB (~35 MB per 40 s 1080p)
UNITS_PER_JOB = 14


class AcquisitionError(Exception):
    pass


def require(ok, code):
    if not ok:
        raise AcquisitionError(code)


def request_id(video, start, end):
    return f"acq-{video}-{start}-{end}-v1"


def validate_window(video, start, end):
    require(isinstance(video, str) and VIDEO_ID.fullmatch(video), "INVALID_VIDEO_ID")
    require(type(start) is int and type(end) is int and 0 <= start < end, "INVALID_WINDOW")
    require(MIN_WINDOW <= end - start <= MAX_WINDOW, "WINDOW_LENGTH_OUT_OF_RANGE")


def historic_windows():
    """(video, start, end) of every historical native request, success or not."""
    claims = json.loads(HISTORIC.read_text())["claims"]
    windows = set()
    for claim in claims:
        match = re.fullmatch(r"\d{8}-rapidapi-native-([A-Za-z0-9_-]{11})-(\d+)-(\d+)-v1", claim["request_id"])
        require(match, "UNPARSED_HISTORIC_REQUEST")
        windows.add((match.group(1), int(match.group(2)), int(match.group(3))))
    return windows


def load_ledger(path=LEDGER):
    ledger = json.loads(path.read_text())
    require(ledger["version"] == "acquisition-ledger-v1", "LEDGER_VERSION")
    ids = [c["request_id"] for c in ledger["claims"]]
    require(len(ids) == len(set(ids)), "DUPLICATE_LEDGER_CLAIM")
    return ledger


def check_quota(headers, ledger):
    """Free plan only, unchanged plan, unit floor kept after this job."""
    require(headers.get("x-ratelimit-units-limit") == "500", "UNIT_PLAN_NOT_FREE_500")
    require("x-ratelimit-rapid-free-plans-hard-limit-limit" in headers, "FREE_PLAN_HARD_LIMIT_HEADER_MISSING")
    remaining = int(headers.get("x-ratelimit-units-remaining", "-1"))
    require(remaining - UNITS_PER_JOB >= ledger["unit_floor"], "UNIT_FLOOR_WOULD_BE_BROKEN")
    hard = int(headers.get("x-ratelimit-rapid-free-plans-hard-limit-remaining", "-1"))
    require(hard >= 40, "FREE_PLAN_REQUEST_HEADROOM")
    return remaining


def reserve(video, start, end, now, headers, ledger):
    validate_window(video, start, end)
    rid = request_id(video, start, end)
    require((video, start, end) not in historic_windows(), "HISTORIC_WINDOW_NEVER_REPEATED")
    require(all(c["request_id"] != rid for c in ledger["claims"]), "PRIOR_CLAIM_EXISTS_NO_RESTART")
    require(all(c["status"] != "RESERVED_BEFORE_EFFECT" for c in ledger["claims"]), "UNRESOLVED_CLAIM_EXISTS")
    today = now.date().isoformat()
    require(sum(c["day_utc"] == today for c in ledger["claims"]) < ledger["daily_job_cap"], "DAILY_JOB_CAP")
    remaining = check_quota(headers, ledger)
    claim = {"request_id": rid, "video_id": video, "start_seconds": start, "end_seconds": end,
             "status": "RESERVED_BEFORE_EFFECT", "reserved_at": now.isoformat(), "day_utc": today,
             "units_remaining_at_reservation": remaining, "reserved_units": UNITS_PER_JOB}
    ledger["claims"].append(claim)
    return claim


def finish(ledger, rid, receipt):
    claims = [c for c in ledger["claims"] if c["request_id"] == rid]
    require(len(claims) == 1 and claims[0]["status"] == "RESERVED_BEFORE_EFFECT", "NO_OPEN_CLAIM")
    claim = claims[0]
    ok = receipt.get("status") == "WINDOW_RECEIVED_AND_DECODED"
    claim["status"] = "COMPLETED" if ok else ("FAILED_TERMINAL_EFFECT_UNKNOWN"
                                               if receipt.get("effect_status") != "NOT_SENT"
                                               else "FAILED_BEFORE_EFFECT")
    for key in ("provider_job_id", "failure_code", "effect_status", "media_file", "returned_duration_seconds",
                "video_height", "units_used_observed", "completed_at", "run_id"):
        if key in receipt:
            claim[key] = receipt[key]
    claim["restart_allowed"] = False
    return claim


def save_ledger(ledger, path=LEDGER):
    path.write_text(json.dumps(ledger, indent=2) + "\n")


def quota_from_completed_job(key):
    """Read live quota headers by polling the already completed first opening
    job (no new job, no media)."""
    import native_probe as n
    prior = json.loads(FIRST_RESULT.read_text())
    evidence = {"control_response_bytes": 0, "progress_polls": 0,
                "baseline_quota_headers": prior["last_quota_headers"]}
    out = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "acq-quota"
    out.mkdir(exist_ok=True)
    try:
        value = n.progress(prior["provider_job_id"], key, evidence, out, 0)
    except HTTPError as error:
        # the provider purges old jobs (2026-10-19: 404 for the 2026-10-15 reference job, every reservation refused).
        # The gateway's quota counters still come on that reply; check_quota then enforces the free plan and the floor
        # exactly as before, and refuses when they are absent.
        return quota_from_error(error)
    require(value.get("success") == 1, "REFERENCE_JOB_NOT_COMPLETE")
    return evidence["last_quota_headers"]


def quota_from_error(error):
    from preflight import quota_headers
    require(getattr(error, "code", None) == 404, f"QUOTA_READ_HTTP_{getattr(error, 'code', 'ERROR')}")
    q = quota_headers(error.headers or {})
    require("x-ratelimit-units-remaining" in q, "QUOTA_HEADERS_MISSING_ON_PURGED_JOB")
    return q


def inspect(path, start, end, evidence):
    import native_probe as n
    data = json.loads(n.command(["ffprobe", "-v", "error", "-show_entries",
                                 "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
                                 "-of", "json", str(path)]))
    videos = [s for s in data["streams"] if s["codec_type"] == "video"]
    audios = [s for s in data["streams"] if s["codec_type"] == "audio"]
    require(len(videos) == 1 and len(audios) == 1, "VIDEO_AND_ONE_AUDIO_REQUIRED")
    duration = float(data["format"]["duration"])
    evidence["returned_duration_seconds"] = round(duration, 3)
    evidence["video_height"] = videos[0].get("height")
    require(abs(duration - (end - start)) <= 0.15, "RETURNED_DURATION_DOES_NOT_MATCH_REQUEST")
    require(720 <= (videos[0].get("height") or 0) <= 1080, "UNEXPECTED_VIDEO_HEIGHT")
    n.command(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:v:0", "-map", "0:a:0",
               "-f", "null", "-"], timeout=600)
    evidence["complete_clip_decode_passed"] = True


def execute(video, start, end, key, out):
    import native_probe as n
    from connection_probe import Client
    rid = request_id(video, start, end)
    ledger = load_ledger()
    claims = [c for c in ledger["claims"] if c["request_id"] == rid]
    require(len(claims) == 1 and claims[0]["status"] == "RESERVED_BEFORE_EFFECT", "COMMITTED_RESERVATION_REQUIRED")
    require(os.environ.get("GITHUB_REF") == "refs/heads/main" and os.environ.get("GITHUB_RUN_ATTEMPT") == "1",
            "MAIN_FIRST_ATTEMPT_ONLY")
    e = {"version": "acquire-window-v1", "request_id": rid, "video_id": video, "window": [start, end],
         "run_id": os.environ.get("GITHUB_RUN_ID"), "status": "BLOCKED", "effect_status": "NOT_SENT",
         "download_tools_call_requests": 0, "progress_polls": 0, "control_response_bytes": 0,
         "production": False, "publication": False}
    try:
        headers = quota_from_completed_job(key)
        e["baseline_quota_headers"] = headers
        check_quota(headers, ledger)
        n.PARAMS = dict(n.PARAMS, url="https://www.youtube.com/watch?v=" + video,
                        start_time=start, end_time=end)
        n.REQUEST_ID = rid
        client = Client(key, opener=n.build_opener(n.NoRedirect()))
        client.send("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                   "clientInfo": {"name": "heroverse-acquire-window", "version": "1"}})
        client.send("notifications/initialized")
        value = n.start_download(client, n.OneStart(), e, out)
        job = value.get("id")
        require(isinstance(job, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,160}", job) and key not in job, "NO_SAFE_JOB_ID")
        e.update(provider_job_id=job, effect_status="JOB_ID_RECEIVED_NO_RESTART_ALLOWED")
        deadline = time.monotonic() + 420
        for index in range(36):
            require(time.monotonic() <= deadline, "PENDING_STOP_NO_AUTOMATIC_RECOVERY")
            if index:
                time.sleep(10)
            value = n.progress(job, key, e, out, index)
            url = n.ready_delivery_url(value)
            if url:
                host = urlsplit(url).hostname or ""
                require(host == "savenow.to" or host.endswith(".savenow.to"), "UNEXPECTED_DELIVERY_HOST_STOP")
                n.fetch_media(url, out, e, timeout=90)
                inspect(out / "native.mp4", start, end, e)
                used = int(headers["x-ratelimit-units-remaining"]) - int(e["last_quota_headers"]["x-ratelimit-units-remaining"])
                e["units_used_observed"] = used
                e["status"] = "WINDOW_RECEIVED_AND_DECODED"
                break
        else:
            raise AcquisitionError("PENDING_STOP_NO_AUTOMATIC_RECOVERY")
    except Exception as error:  # terminal; never retried
        e["status"] = "BLOCKED"
        e["failure_code"] = str(error) if isinstance(error, (AcquisitionError, n.ProbeError)) else type(error).__name__
    e["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    public = {k: v for k, v in e.items() if k not in ("baseline_quota_headers", "last_quota_headers",
                                                       "quota_observations", "native_probe")}
    (out / "public-receipt.json").write_text(json.dumps(public, indent=2) + "\n")
    print("HEROVERSE_ACQUIRE_RECEIPT=" + json.dumps(public), flush=True)
    return 0 if e["status"] == "WINDOW_RECEIVED_AND_DECODED" else 2


def main(argv):
    command, video, start, end = argv[0], argv[1], int(argv[2]), int(argv[3])
    if command == "reserve":
        ledger = load_ledger()
        key = os.environ.get("HERO_RAPIDAPI_KEY", "")
        require(bool(key), "KEY_MISSING")
        claim = reserve(video, start, end, dt.datetime.now(dt.timezone.utc), quota_from_completed_job(key), ledger)
        save_ledger(ledger)
        print("HEROVERSE_ACQUIRE_RESERVED=" + json.dumps(claim))
        return 0
    if command == "execute":
        out = Path(argv[4])
        out.mkdir(parents=True, exist_ok=False)
        return execute(video, start, end, os.environ.get("HERO_RAPIDAPI_KEY", ""), out)
    if command == "finish":
        ledger = load_ledger()
        claim = finish(ledger, request_id(video, start, end), json.loads(Path(argv[4]).read_text()))
        save_ledger(ledger)
        print("HEROVERSE_ACQUIRE_FINISHED=" + json.dumps(claim))
        return 0
    raise SystemExit("usage: acquire_window.py reserve|execute|finish VIDEO START END [PATH]")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
