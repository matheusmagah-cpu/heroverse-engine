"""Bounded MCP transport probe. No video downloads or tools/call are implemented."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = "https://mcp.rapidapi.com"
API_HOST = "youtube-info-download-api.p.rapidapi.com"
PROTOCOLS = ("2025-06-18", "2025-03-26")
MAX_RESPONSE_BYTES = 1024 * 1024
ALLOWED_METHODS = frozenset(("initialize", "notifications/initialized", "tools/list"))


class ProbeError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProbeError("REDIRECT_REFUSED")


def _validate_reply(value, request_id):
    if not isinstance(value, dict) or value.get("jsonrpc") != "2.0":
        raise ProbeError("INVALID_RPC_REPLY")
    if value.get("id") != request_id:
        return None
    if "error" in value:
        raise ProbeError("RPC_ERROR")
    if not isinstance(value.get("result"), dict):
        raise ProbeError("INVALID_RPC_RESULT")
    return value["result"]


def read_reply(response, request_id, deadline):
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip()
    if content_type == "application/json":
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProbeError("RESPONSE_TOO_LARGE")
        result = _validate_reply(json.loads(raw), request_id)
        if result is None:
            raise ProbeError("RPC_ID_MISMATCH")
        return result
    if content_type != "text/event-stream":
        raise ProbeError("UNSUPPORTED_RESPONSE_TYPE")
    total, data = 0, []
    while True:
        if time.monotonic() > deadline:
            raise ProbeError("RESPONSE_DEADLINE")
        line = response.readline(MAX_RESPONSE_BYTES - total + 1)
        total += len(line)
        if total > MAX_RESPONSE_BYTES:
            raise ProbeError("RESPONSE_TOO_LARGE")
        if not line:
            raise ProbeError("SSE_ENDED_WITHOUT_REPLY")
        line = line.decode("utf-8").rstrip("\r\n")
        if line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
        elif not line and data:
            result = _validate_reply(json.loads("\n".join(data)), request_id)
            data = []
            if result is not None:
                return result


class Client:
    def __init__(self, key, opener=None):
        if not key or any(c in key for c in "\r\n"):
            raise ProbeError("MISSING_OR_INVALID_HERO_RAPIDAPI_KEY")
        self._key = key
        self._opener = opener or build_opener(NoRedirect())
        self._session = None
        self._protocol = None
        self._next_id = 1
        self.methods_sent = []

    def send(self, method, params=None):
        if method not in ALLOWED_METHODS:
            raise ProbeError("METHOD_NOT_ALLOWED")
        if method != "initialize" and self._protocol is None:
            raise ProbeError("INITIALIZATION_REQUIRED")
        notification = method == "notifications/initialized"
        request_id = None if notification else self._next_id
        payload = {"jsonrpc": "2.0", "method": method}
        if not notification:
            payload["id"] = request_id
            self._next_id += 1
        if params is not None:
            payload["params"] = params
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "x-api-host": API_HOST,
            "x-api-key": self._key,
        }
        if self._session:
            headers["Mcp-Session-Id"] = self._session
        if self._protocol:
            headers["MCP-Protocol-Version"] = self._protocol
        req = Request(ENDPOINT, data=json.dumps(payload).encode(), headers=headers, method="POST")
        self.methods_sent.append(method)
        with self._opener.open(req, timeout=12) as response:
            if notification:
                if response.status != 202:
                    raise ProbeError("NOTIFICATION_NOT_ACCEPTED")
                return None
            result = read_reply(response, request_id, time.monotonic() + 15)
            if method == "initialize":
                protocol = result.get("protocolVersion")
                if protocol not in PROTOCOLS:
                    raise ProbeError("UNSUPPORTED_NEGOTIATED_PROTOCOL")
                self._protocol = protocol
                session = response.headers.get("Mcp-Session-Id")
                if session and (len(session) > 4096 or not all(0x21 <= ord(c) <= 0x7E for c in session)):
                    raise ProbeError("INVALID_SESSION_HEADER")
                self._session = session
            return result


def probe(key, opener=None):
    client = Client(key, opener)
    initialized = client.send("initialize", {
        "protocolVersion": PROTOCOLS[0], "capabilities": {},
        "clientInfo": {"name": "heroverse-reference-connection-probe", "version": "0.1.0"},
    })
    if "tools" not in initialized.get("capabilities", {}):
        raise ProbeError("TOOLS_CAPABILITY_NOT_ADVERTISED")
    client.send("notifications/initialized")
    result = client.send("tools/list", {})
    tools = result.get("tools")
    if not isinstance(tools, list) or not tools:
        raise ProbeError("NO_TOOL_SCHEMAS_RECEIVED")
    # Retain only public schema labels, never headers, sessions, prompts or raw replies.
    names = []
    for tool in tools:
        name = tool.get("name") if isinstance(tool, dict) else None
        if not isinstance(name, str) or not name or len(name) > 200:
            raise ProbeError("INVALID_TOOL_NAME")
        names.append(name.replace(key, "[REDACTED]"))
    return {
        "status": "MCP_TRANSPORT_AND_TOOL_LIST_VERIFIED",
        "endpoint": ENDPOINT, "api_host": API_HOST,
        "protocol_version": client._protocol,
        "request_methods": client.methods_sent,
        "tools_in_first_page": len(names), "tool_names": names,
        "additional_tool_pages_advertised": bool(result.get("nextCursor")),
        "credential_supplied": True,
        "owner_entitlement_verified_by_this_probe": False,
        "explanation": "A schema handshake alone does not prove the key can execute a provider API call.",
        "media_jobs_submitted": 0, "tools_call_requests": 0,
        "native_video_verified": False, "native_audio_verified": False,
        "recurring_free_capacity_qualified": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    receipt = {"status": "BLOCKED", "media_jobs_submitted": 0, "tools_call_requests": 0}
    try:
        receipt = probe(os.environ.get("HERO_RAPIDAPI_KEY", ""))
        code = 0
    except HTTPError as error:
        receipt["failure_code"] = "HTTP_" + str(error.code)
        code = 2
    except (URLError, socket.timeout, TimeoutError):
        receipt["failure_code"] = "TRANSPORT_UNAVAILABLE_OR_TIMEOUT"
        code = 2
    except ProbeError as error:
        receipt["failure_code"] = str(error)
        code = 2
    except (ValueError, UnicodeError, TypeError, AttributeError):
        receipt["failure_code"] = "INVALID_PROVIDER_RESPONSE"
        code = 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n")
    print("HEROVERSE_MCP_RECEIPT=" + json.dumps(receipt, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
