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
# The three allowed methods share their wire shape across these handshake
# revisions. Do not infer support for a new revision from its date alone.
PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
MAX_RESPONSE_BYTES = 1024 * 1024
ALLOWED_METHODS = frozenset(("initialize", "notifications/initialized", "tools/list"))


class ProbeError(Exception):
    pass


class ProtocolNegotiationError(ProbeError):
    def __init__(self, version):
        super().__init__("UNSUPPORTED_NEGOTIATED_PROTOCOL")
        # Only a known public identifier can enter a receipt. Arbitrary server
        # strings might contain credentials or other private response content.
        self.server_protocol_version = (
            version if version == "2026-07-28" else "UNRECOGNIZED_OR_MISSING"
        )


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
        self.http_responses = []
        self.notification_acknowledgement = None
        self.notification_rpc_error_code = None

    def public_trace(self):
        return {
            "request_methods": self.methods_sent,
            "http_responses": self.http_responses,
            "protocol_version": self._protocol,
            "notification_acknowledgement": self.notification_acknowledgement,
            "notification_rpc_error_code": self.notification_rpc_error_code,
        }

    def accept_notification(self, response):
        if response.status == 202:
            self.notification_acknowledgement = "HTTP_202_STANDARD"
            return
        if response.status not in (200, 204):
            raise ProbeError("NOTIFICATION_NOT_ACCEPTED")
        # Some hosted bridges acknowledge notifications with 200/204. Treat
        # this only as an explicit compatibility mode, never strict conformance.
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProbeError("RESPONSE_TOO_LARGE")
        if not raw.strip():
            self.notification_acknowledgement = "HTTP_" + str(response.status) + "_EMPTY_COMPATIBILITY"
            return
        if response.status == 200:
            value = json.loads(raw)
            if isinstance(value, dict) and "error" in value:
                error = value["error"]
                code = error.get("code") if isinstance(error, dict) else None
                if type(code) is int and -32768 <= code <= -32000:
                    self.notification_rpc_error_code = code
                # A response to an id-less notification is unsolicited. Only
                # the exact method-not-found case can continue to catalogue
                # discovery; this is not a successful/standard initialized ack.
                if (value.get("jsonrpc") == "2.0" and value.get("id") is None
                        and "result" not in value and code == -32601):
                    self.notification_acknowledgement = "HTTP_200_METHOD_NOT_FOUND_COMPATIBILITY"
                    return
                raise ProbeError("NOTIFICATION_RPC_ERROR")
            if (isinstance(value, dict) and value.get("jsonrpc") == "2.0"
                    and value.get("id") is None and "result" in value
                    and value["result"] in (None, {})):
                self.notification_acknowledgement = "HTTP_200_NULL_RESULT_COMPATIBILITY"
                return
        raise ProbeError("INVALID_NOTIFICATION_ACKNOWLEDGEMENT")

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
            self.http_responses.append({"method": method, "status": response.status})
            if notification:
                self.accept_notification(response)
                return None
            result = read_reply(response, request_id, time.monotonic() + 15)
            if method == "initialize":
                protocol = result.get("protocolVersion")
                if protocol not in PROTOCOLS:
                    raise ProtocolNegotiationError(protocol)
                self._protocol = protocol
                session = response.headers.get("Mcp-Session-Id")
                if session and (len(session) > 4096 or not all(0x21 <= ord(c) <= 0x7E for c in session)):
                    raise ProbeError("INVALID_SESSION_HEADER")
                self._session = session
            return result


def probe(key, opener=None, evidence=None):
    client = Client(key, opener)
    try:
        initialized = client.send("initialize", {
            "protocolVersion": PROTOCOLS[0], "capabilities": {},
            "clientInfo": {"name": "heroverse-reference-connection-probe", "version": "0.1.3"},
        })
        if "tools" not in initialized.get("capabilities", {}):
            raise ProbeError("TOOLS_CAPABILITY_NOT_ADVERTISED")
        client.send("notifications/initialized")
        result = client.send("tools/list", {})
    finally:
        if evidence is not None:
            evidence.update(client.public_trace())
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
        "http_responses": client.http_responses,
        "notification_acknowledgement": client.notification_acknowledgement,
        "notification_rpc_error_code": client.notification_rpc_error_code,
        "standard_notification_acknowledgement": client.notification_acknowledgement == "HTTP_202_STANDARD",
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
        receipt = probe(os.environ.get("HERO_RAPIDAPI_KEY", ""), evidence=receipt)
        code = 0
    except HTTPError as error:
        receipt["failure_code"] = "HTTP_" + str(error.code)
        code = 2
    except (URLError, socket.timeout, TimeoutError):
        receipt["failure_code"] = "TRANSPORT_UNAVAILABLE_OR_TIMEOUT"
        code = 2
    except ProtocolNegotiationError as error:
        receipt["failure_code"] = str(error)
        receipt["server_protocol_version"] = error.server_protocol_version
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
