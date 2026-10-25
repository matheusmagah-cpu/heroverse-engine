"""Bounded, unofficial Flash generation. A fresh, exact zero-credit quote is mandatory.

The request contract was checked against Pavo's own web client. This module never
extracts browser credentials, retries a submission, buys credits, or publishes.
"""
import json
import re
import socket
import threading
import time
from contextlib import contextmanager
from decimal import Decimal, DecimalException
from urllib.error import HTTPError, URLError
from urllib.request import Request
from urllib.parse import urlsplit

from client import MAX_BYTES, ORIGIN, PavoClient, PavoError, number
import images

MODEL = "agnes-video-new-flash"
STREAM_SECONDS = 30
PATHS = {
    "quote": "/v1/aigc/credits/calculate",
    "create": "/v1/chat/conversation",
    "stream": "/v1/chat/stream",
    "history": "/v1/chat/conversation/history?conversation_id=",
    "upload": "/v1/file/presigned-url",
    "inspect": "/v1/file/inspect",
}
UPLOAD_HEADERS = re.compile(r"[A-Za-z0-9-]{1,64}")


def conversation_id(value):
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,24}", value):
        raise PavoError("INVALID_CONVERSATION_ID")
    return value


def price(value):
    if isinstance(value, bool) or value is None:
        raise PavoError("PAVO_QUOTE_SCHEMA_CHANGED")
    try:
        exact = Decimal(str(value))
        if not exact.is_finite() or exact < 0 or exact > 1000000000:
            raise PavoError("PAVO_QUOTE_SCHEMA_CHANGED")
        shown = float(exact)
        if exact != 0 and shown == 0:
            raise PavoError("PAVO_QUOTE_SCHEMA_CHANGED")
        return exact, shown
    except (DecimalException, ValueError, TypeError, OverflowError):
        raise PavoError("PAVO_QUOTE_SCHEMA_CHANGED") from None


class PavoVideoClient(PavoClient):
    def status(self):
        result = super().status()
        result.update(generation_enabled=self._valid_token(),
                      generation_policy="fresh_exact_zero_credit_quote",
                      generation_blocker=None if self._valid_token() else "PAVO_CREDENTIAL_REQUIRED")
        return result

    def account(self):
        result = super().account()
        result.update(generation_enabled=True, price_verified=False)
        return result

    def prepare_video(self, prompt, seconds=5, aspect_ratio="9:16"):
        result = super().prepare_video(prompt, seconds, aspect_ratio)
        result["blocker"] = "FRESH_ZERO_CREDIT_QUOTE_REQUIRED"
        return result

    def _video_request(self, route, body=None, job=None):
        if route not in PATHS:
            raise PavoError("ROUTE_NOT_ALLOWED")
        if not self._valid_token():
            raise PavoError("PAVO_CREDENTIAL_REQUIRED")
        path = PATHS[route]
        if route == "history":
            path += conversation_id(job)
            if body is not None:
                raise PavoError("ROUTE_NOT_ALLOWED")
        elif body is None:
            raise PavoError("INVALID_PAVO_REQUEST")
        headers = {
            "Authorization": "Bearer " + self._token,
            "User-Agent": "HeroVerse-Pavo-MCP/0.3",
            "Accept": "text/event-stream" if route == "stream" else "application/json",
            "Content-Type": "application/json",
            "X-Platform": "1",
            "X-App-Timezone": "America/Sao_Paulo",
            "X-Client-Time-Ms": str(int(time.time() * 1000)),
            "X-User-Language": "en",
            "Cache-Control": "no-cache",
        }
        return Request(ORIGIN + path, headers=headers,
                       data=json.dumps(body).encode() if body is not None else None,
                       method="GET" if route == "history" else "POST")

    def _video_json(self, route, body=None, job=None):
        request = self._video_request(route, body, job)
        try:
            with self._opener.open(request, timeout=15) as response:
                if response.status != 200:
                    raise PavoError("UPSTREAM_HTTP_REFUSED")
                raw = response.read(MAX_BYTES + 1)
        except PavoError:
            raise
        except HTTPError as exc:
            code = {401: "PAVO_SESSION_EXPIRED", 403: "PAVO_ACCESS_REFUSED",
                    429: "PAVO_RATE_LIMITED"}.get(exc.code, "UPSTREAM_HTTP_REFUSED")
            exc.close()
            raise PavoError(code) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise PavoError("PAVO_UNREACHABLE") from None
        if len(raw) > MAX_BYTES:
            raise PavoError("RESPONSE_TOO_LARGE")
        try:
            payload = json.loads(raw, parse_float=Decimal)
        except (ValueError, UnicodeError, RecursionError, DecimalException):
            raise PavoError("INVALID_PAVO_RESPONSE") from None
        if not isinstance(payload, dict) or payload.get("code") != "000000":
            raise PavoError("PAVO_REQUEST_REFUSED")
        return payload.get("data")

    def quote_video(self, seconds=5, aspect_ratio="9:16", first_frame="", last_frame="", references=None):
        # Reuse the local brief's strict duration/ratio validation without any write.
        self.prepare_video("Price check", seconds, aspect_ratio)
        mode, inputs = images.plan(first_frame, last_frame, references)
        return self._quote(seconds, aspect_ratio, mode, len(inputs))

    def _quote(self, seconds, aspect_ratio, mode, input_images):
        # Input images are priced too (the web client sends them as `inputs`).
        body = {"model_code": MODEL, "outputs": [{"count": 1, "media_type": "video",
                "resolution": "hd", "duration_seconds": seconds, "gen_audio": False}]}
        if input_images:
            body["inputs"] = [{"count": 1, "media_type": "image"} for _ in range(input_images)]
        data = self._video_json("quote", body)
        if not isinstance(data, dict) or type(data.get("is_estimate")) is not bool:
            raise PavoError("PAVO_QUOTE_SCHEMA_CHANGED")
        exact_credits, credits = price(data.get("required_credits"))
        final_points, _ = price(data.get("final_points"))
        return {"model": MODEL, "seconds": seconds, "aspect_ratio": aspect_ratio, "mode": mode,
                "input_images": input_images, "resolution": "720p", "audio": False, "count": 1,
                "required_credits": credits, "is_estimate": data["is_estimate"],
                "zero_cost_confirmed": exact_credits == 0 and final_points == 0 and not data["is_estimate"],
                "permanent_free_access_verified": False}

    def _upload(self, item):
        """One image into Pavo's attachment storage (presigned PUT, then inspect). Never generates."""
        data = self._video_json("upload", {"purpose": "chat_attachment", "content_type": item["mime"],
                                           "filename": item["filename"]})
        if not isinstance(data, dict):
            raise PavoError("PAVO_UPLOAD_SCHEMA_CHANGED")
        public, target, headers, meta = (data.get("public_url"), data.get("upload_url"),
                                         data.get("required_headers") or {}, data.get("meta_data"))
        for url in (public, target):
            if not isinstance(url, str) or len(url) > 4096 or (self._token and self._token in url):
                raise PavoError("PAVO_UPLOAD_SCHEMA_CHANGED")
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise PavoError("PAVO_UPLOAD_SCHEMA_CHANGED")
        if urlsplit(public).query or not isinstance(headers, dict) or not all(
                isinstance(k, str) and UPLOAD_HEADERS.fullmatch(k) and k.lower() != "authorization"
                and isinstance(v, str) and len(v) <= 1024 for k, v in headers.items()):
            raise PavoError("PAVO_UPLOAD_SCHEMA_CHANGED")
        if meta is not None and (not isinstance(meta, dict) or len(json.dumps(meta)) > 4096):
            raise PavoError("PAVO_UPLOAD_SCHEMA_CHANGED")
        # The presigned PUT goes to storage, never with the Pavo credential.
        put = Request(target, data=item["data"], headers=dict(headers), method="PUT")
        try:
            with self._opener.open(put, timeout=60) as response:
                if not 200 <= response.status < 300:
                    raise PavoError("PAVO_UPLOAD_REFUSED")
        except PavoError:
            raise
        except HTTPError as exc:
            exc.close()
            raise PavoError("PAVO_UPLOAD_REFUSED") from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise PavoError("PAVO_UPLOAD_HOST_UNREACHABLE") from None
        self._video_json("inspect", {"content_type": item["mime"], "url": public})
        return {"url": public, **({"meta_data": meta} if meta else {})}

    def _start_stream(self, job, prompt, seconds, aspect_ratio, mode="frames_to_video", uploaded=()):
        body = {
            "conversation_id": int(job), "prompt": prompt, "mode": mode,
            "model": MODEL, "ratio": aspect_ratio, "duration": seconds,
            "resolution": "hd", "sound": False, "count": 1,
        }
        if uploaded:
            # frames_to_video: [first, last]; omni_to_video: references, also named in the prompt blocks
            body["images"] = list(uploaded)
        if mode == "omni_to_video":
            blocks = [{"type": "text", "content": prompt}]
            blocks += [{"type": "image", "url": u["url"], "source_index": i} for i, u in enumerate(uploaded, 1)]
            body["creative_prompt_json"] = json.dumps(blocks)
        request = self._video_request("stream", body)
        # Closing after GenerationStart leaves the job running on Pavo. Read its
        # history afterwards; never create a replacement just because a read timed out.
        with self._opener.open(request, timeout=15) as response, self._stream_timeout(response):
            if response.status != 200:
                raise PavoError("PAVO_SUBMISSION_STATE_UNKNOWN")
            event, parts = "message", []
            for line in self._stream_lines(response):
                text = line.decode("utf-8").rstrip("\r\n")
                if text.startswith("event:"):
                    event = text[6:].strip()
                elif text.startswith("data:"):
                    parts.append(text[5:].lstrip())
                elif not text:
                    data = json.loads("\n".join(parts)) if parts else {}
                    kind = data.get("type", event) if event == "message" and isinstance(data, dict) else event
                    if kind.lower() == "error" or kind in ("GenerationFailed", "TaskFailed"):
                        return False
                    if kind == "GenerationStart":
                        if not isinstance(data, dict) or data.get("model_code") != MODEL:
                            raise PavoError("PAVO_SUBMISSION_STATE_UNKNOWN")
                        return True
                    event, parts = "message", []
        raise PavoError("PAVO_SUBMISSION_STATE_UNKNOWN")

    @staticmethod
    @contextmanager
    def _stream_timeout(response):
        # CPython HTTPResponse can block inside chunk-header readline even when
        # read1 is used. Shutdown interrupts that read without waiting for its lock.
        sock = response.fp.raw._sock
        def interrupt():
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                return  # Normal completion may already have closed the socket.
        timer = threading.Timer(STREAM_SECONDS, interrupt)
        timer.daemon = True
        timer.start()
        try:
            yield
        finally:
            timer.cancel()
            timer.join()

    @staticmethod
    def _stream_lines(response):
        total, buffer = 0, b""
        deadline = time.monotonic() + STREAM_SECONDS
        while time.monotonic() < deadline:
            # read1 makes one buffered/network read; readline can keep waiting
            # indefinitely for a terminator while bytes trickle in.
            chunk = response.read1(4096)
            total += len(chunk)
            if time.monotonic() >= deadline or total > MAX_BYTES:
                raise PavoError("PAVO_SUBMISSION_STATE_UNKNOWN")
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if len(line) > 16384:
                    raise PavoError("PAVO_SUBMISSION_STATE_UNKNOWN")
                yield line
            if len(buffer) > 16384:
                raise PavoError("PAVO_SUBMISSION_STATE_UNKNOWN")

    def generate_video(self, prompt, seconds=5, aspect_ratio="9:16", first_frame="", last_frame="", references=None):
        prompt = self.prepare_video(prompt, seconds, aspect_ratio)["brief"]["prompt"]
        mode, inputs = images.plan(first_frame, last_frame, references)
        quote = self._quote(seconds, aspect_ratio, mode, len(inputs))
        if not quote["zero_cost_confirmed"]:
            raise PavoError("PAVO_ZERO_CREDIT_QUOTE_REQUIRED")
        # Uploads happen after the free quote and before any conversation: a failed upload creates no job.
        uploaded = [self._upload(item) for item in inputs]
        data = self._video_json("create", {
            "title": json.dumps([{"type": "text", "content": "HeroVerse MCP preview"}]),
            "folder_id": "", "kb_strict": False,
        })
        if not isinstance(data, dict):
            raise PavoError("PAVO_CONVERSATION_SCHEMA_CHANGED")
        job = conversation_id(data.get("conversation_id"))
        result = {"conversation_id": job, "model": MODEL, "mode": mode, "input_images": len(inputs),
                  "quoted_credits": 0, "retry_submission": False, "published": False}
        try:
            accepted = self._start_stream(job, prompt, seconds, aspect_ratio, mode, uploaded)
        except Exception as exc:
            if isinstance(exc, HTTPError):
                exc.close()
            # Preserve the recoverable job ID, not the response/exception (which
            # may contain credentials). A lost acknowledgement is not a failed job.
            return {**result, "status": "unknown", "submitted": None,
                    "next_action": "Call pavo_job with this conversation_id; do not resubmit."}
        return {**result, "status": "submitted" if accepted else "rejected", "submitted": accepted,
                "next_action": "Call pavo_job with this conversation_id."}

    def job(self, job):
        job = conversation_id(job)
        if self._token and self._token in job:
            raise PavoError("CREDENTIAL_IN_CONVERSATION_ID_REFUSED")
        data = self._video_json("history", job=job)
        if not isinstance(data, dict) or type(data.get("is_running")) is not bool or not isinstance(data.get("turns"), list):
            raise PavoError("PAVO_HISTORY_SCHEMA_CHANGED")
        videos, failed = [], False
        turns = data["turns"]
        if turns:
            turn = turns[-1]
            if not isinstance(turn, dict) or not isinstance(turn.get("assistant", []), list):
                raise PavoError("PAVO_HISTORY_SCHEMA_CHANGED")
            for block in turn.get("assistant", []):
                if not isinstance(block, dict):
                    continue
                kind = block.get("type")
                if kind in ("Error", "error", "GenerationFailed", "GenerationFailure", "TaskFailed"):
                    failed = True
                if kind != "GenerationSuccess":
                    continue
                wrapper = block.get("data")
                payload = wrapper.get("data") if isinstance(wrapper, dict) else None
                if not isinstance(payload, dict) or payload.get("model_code") != MODEL or not isinstance(payload.get("results"), list):
                    raise PavoError("PAVO_RESULT_SCHEMA_CHANGED")
                for item in payload["results"][:8]:
                    if not isinstance(item, dict):
                        raise PavoError("PAVO_RESULT_SCHEMA_CHANGED")
                    url = item.get("url")
                    if not isinstance(url, str) or len(url) > 2048 or (self._token and self._token in url):
                        raise PavoError("PAVO_MEDIA_URL_REFUSED")
                    try:
                        parsed = urlsplit(url)
                        valid = (parsed.scheme == "https" and parsed.hostname == "cos-aigc-default.agnes-ai.space"
                                 and parsed.port in (None, 443) and not parsed.username and not parsed.password
                                 and not parsed.query and not parsed.fragment
                                 and re.fullmatch(r"/[A-Za-z0-9_./%+-]+\.mp4", parsed.path))
                    except ValueError:
                        valid = False
                    if not valid:
                        raise PavoError("PAVO_MEDIA_URL_REFUSED")
                    videos.append({"url": url, "seconds": number(item.get("duration")),
                                   "width": number(item.get("width")), "height": number(item.get("height"))})
        status = "running" if data["is_running"] else "completed" if videos else "failed" if failed else "incomplete"
        return {"conversation_id": job, "running": data["is_running"], "status": status, "videos": videos,
                "turn_count": len(data["turns"]), "published": False,
                "conversation_url": "https://app.pavo-ai.work/chat?conversationId=" + job}
