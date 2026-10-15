"""Read public tool contracts and bounded quota metadata. Never starts a media job."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rapidapi-mcp"))
from connection_probe import Client, NoRedirect, ProbeError

SOURCE = "https://www.youtube.com/watch?v=j2rk8ycXe3c"
HOST = "youtube-info-download-api.p.rapidapi.com"
MAX_INFO_BYTES = 262144


def quota_headers(headers):
    """Keep numeric quota counters only; discard all sessions and arbitrary text."""
    result = {}
    for name, value in headers.items():
        name = name.lower()
        if (re.fullmatch(r"x-ratelimit-[a-z0-9_-]{1,80}-(limit|remaining|reset)", name)
                and re.fullmatch(r"[0-9]{1,16}(?:\.[0-9]{1,6})?", value.strip())):
            result[name] = value.strip()
    return result


def safe_public_schemas(result, key):
    tools = result.get("tools")
    if not isinstance(tools, list):
        raise ProbeError("NO_TOOL_SCHEMAS")
    selected = []
    for tool in tools:
        if isinstance(tool, dict) and tool.get("name") in ("download", "progress", "info"):
            schema = tool.get("inputSchema")
            if not isinstance(schema, dict):
                raise ProbeError("INVALID_TOOL_SCHEMA")
            selected.append({"name": tool["name"], "inputSchema": schema})
    if sorted(t["name"] for t in selected) != ["download", "info", "progress"]:
        raise ProbeError("REQUIRED_TOOL_MISSING_OR_DUPLICATE")
    return json.loads(json.dumps(selected).replace(key, "[REDACTED]"))


def run(key, evidence, opener=None):
    client = Client(key, opener)
    client.send("initialize", {"protocolVersion":"2025-11-25","capabilities":{},
        "clientInfo":{"name":"heroverse-native-av-contract-reader","version":"0.1.0"}})
    client.send("notifications/initialized")
    evidence["public_tool_schemas"] = safe_public_schemas(client.send("tools/list", {}), key)
    evidence["mcp_transport_reused"] = True
    # Info costs at most the pre-recorded two included units. It creates no job.
    # Exact path and parameter names were observed in the provider playground.
    request = Request("https://" + HOST + "/ajax/api.php?" + urlencode({"u":SOURCE,"function":"i"}),
        headers={"Accept":"application/json","x-rapidapi-host":HOST,"x-rapidapi-key":key})
    evidence["info_requests_attempted"] = 1
    started = time.monotonic()
    with (opener or build_opener(NoRedirect())).open(request, timeout=20) as response:
        evidence["info_http_status"] = response.status
        evidence["quota_headers"] = quota_headers(response.headers)
        raw = response.read(MAX_INFO_BYTES + 1)
        evidence["info_received_bytes"] = len(raw)
        if len(raw) > MAX_INFO_BYTES:
            raise ProbeError("INFO_RESPONSE_TOO_LARGE")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ProbeError("INVALID_INFO_RESPONSE")
        evidence["info_top_level_keys"] = [k for k in value if re.fullmatch(r"[a-zA-Z0-9_]{1,60}", k) and k != key][:80]
        evidence["info_public_fields"] = {k: value[k] for k in ("id","vid","title","duration","duration_seconds","lengthSeconds","status","success")
            if k in value and isinstance(value[k], (str,int,float,bool)) and len(str(value[k])) <= 300}
    evidence["info_elapsed_seconds"] = round(time.monotonic()-started,3)
    evidence["status"] = "CONTRACT_AND_QUOTA_RESPONSE_RECEIVED"


def main():
    evidence = {"version":"heroverse-rapidapi-native-preflight-v1","status":"BLOCKED", "media_jobs_submitted":0,
        "download_tools_call_requests":0,"request_id":"20261015-rapidapi-native-j2rk8ycXe3c-0-40-v1",
        "info_requests_attempted":0,"native_video_verified":False,"native_audio_verified":False}
    key = os.environ.get("HERO_RAPIDAPI_KEY", "")
    try:
        if os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
            raise ProbeError("WORKFLOW_RERUN_REFUSED")
        run(key, evidence)
    except HTTPError as error:
        evidence["failure_code"] = "HTTP_" + str(error.code)
        evidence["quota_headers"] = quota_headers(error.headers)
    except (URLError, TimeoutError):
        evidence["failure_code"] = "TRANSPORT_UNAVAILABLE_OR_TIMEOUT"
    except ProbeError as error:
        evidence["failure_code"] = str(error)
    except (ValueError, UnicodeError, TypeError, AttributeError):
        evidence["failure_code"] = "INVALID_RESPONSE"
    # Literal key redaction covers even provider-reflected metadata.
    encoded = json.dumps(evidence, separators=(",", ":"))
    if key:
        encoded = encoded.replace(key, "[REDACTED]")
    print("HEROVERSE_NATIVE_PREFLIGHT=" + encoded, flush=True)
    return 0 if evidence["status"] == "CONTRACT_AND_QUOTA_RESPONSE_RECEIVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
