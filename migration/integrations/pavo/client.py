"""Unofficial Pavo account adapter. Only explicit, bounded GETs are implemented.

The website subscription and Agnes API are different credential/billing paths.
No browser storage is read and no generation or purchase endpoint is exposed.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ORIGIN = "https://api.pixa-ai.work/api"
WEBSITE = "https://app.pavo-ai.work/"
MAX_BYTES = 256 * 1024
ROUTES = {
    "credits": "/v3/subscription/credits-balance",
    "models": "/v1/pixa/mode_support_models?mode_code=generate_video",
}


class PavoError(Exception):
    """Only locally defined error codes may leave this boundary."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PavoError("REDIRECT_REFUSED")


def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) and 0 <= result <= 1e9 else None


class PavoClient:
    def __init__(self, token=None, opener=None):
        self._token = os.environ.get("PAVO_TOKEN", "") if token is None else token
        self._opener = opener or build_opener(NoRedirect())

    def _valid_token(self):
        return (isinstance(self._token, str) and 1 <= len(self._token) <= 8192
                and all(33 <= ord(c) <= 126 for c in self._token))

    def status(self):
        return {
            "website": WEBSITE,
            "credential_configured": self._valid_token(),
            "account_verified": False,
            "transport": "stdio",
            "generation_enabled": False,
            "generation_blocker": "PAVO_SUBMISSION_AND_PRICE_CONTRACT_UNVERIFIED",
            "additional_spend_allowed": False,
        }

    def _get(self, route):
        if route not in ROUTES:
            raise PavoError("ROUTE_NOT_ALLOWED")
        headers = {"Accept": "application/json", "User-Agent": "HeroVerse-Pavo-MCP/0.1"}
        if route == "credits":
            if not self._valid_token():
                raise PavoError("PAVO_CREDENTIAL_REQUIRED")
            headers["Authorization"] = "Bearer " + self._token
        # The token never enters a URL, body, exception message or preview.
        request = Request(ORIGIN + ROUTES[route], headers=headers, method="GET")
        try:
            with self._opener.open(request, timeout=12) as response:
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
            payload = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            raise PavoError("INVALID_PAVO_RESPONSE") from None
        if not isinstance(payload, dict):
            raise PavoError("INVALID_PAVO_RESPONSE")
        if payload.get("code") == "000501":
            raise PavoError("PAVO_SESSION_EXPIRED")
        if payload.get("code") != "000000":
            raise PavoError("PAVO_REQUEST_REFUSED")
        return payload.get("data")

    def _text(self, value, limit=100):
        if not isinstance(value, str) or len(value) > limit:
            return None
        if any(ord(c) < 32 for c in value) or (self._token and self._token in value):
            return None
        # Do not let remote aliases carry URLs, bearer values or secret-shaped data.
        if re.search(r"https?://|bearer\s|[A-Za-z0-9_+/=-]{48,}", value, re.I):
            return None
        return value

    def account(self):
        data = self._get("credits")
        if not isinstance(data, dict) or not any(k in data for k in ("level_name", "total_balance")):
            raise PavoError("PAVO_BALANCE_SCHEMA_CHANGED")
        # These fields stay in the MCP client's private response, never in a public receipt.
        return {"authenticated": True, "plan": self._text(data.get("level_name"), 40),
                "credits": {key: number(data.get(key)) for key in
                            ("total_balance", "subscription_credits", "daily_free_credits")},
                "generation_enabled": False, "additional_spend_allowed": False}

    def models(self):
        data = self._get("models")
        rows = data if isinstance(data, list) else data.get("models") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise PavoError("PAVO_MODELS_SCHEMA_CHANGED")
        result = []
        for row in rows[:100]:
            if not isinstance(row, dict):
                continue
            code = self._text(row.get("code", row.get("model_code")))
            if not code or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,99}", code):
                continue
            tags = row.get("tags")
            free = isinstance(tags, list) and any(t == "free" or
                   (isinstance(t, dict) and t.get("code") == "free") for t in tags)
            result.append({"code": code, "name": self._text(row.get("name", row.get("alias", row.get("model_alias")))),
                           "free_label": free,
                           "verified_price_credits": None})
        if rows and not result:
            raise PavoError("PAVO_MODELS_SCHEMA_CHANGED")
        return {"models": result, "price_verified": False,
                "notice": "A free label or an existing subscription is not a per-request price quote."}

    def prepare_video(self, prompt, seconds=5, aspect_ratio="9:16"):
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 4000:
            raise PavoError("INVALID_PROMPT")
        if self._token and self._token in prompt:
            raise PavoError("CREDENTIAL_IN_PROMPT_REFUSED")
        if type(seconds) is not int or seconds not in range(4, 13):
            raise PavoError("INVALID_DURATION")
        if aspect_ratio not in ("9:16", "16:9", "1:1"):
            raise PavoError("INVALID_ASPECT_RATIO")
        # A local creative brief, NOT a guessed upstream generation payload.
        # No POST, quote, credit debit or publication is attempted.
        return {"prepared": True, "submitted": False,
                "brief": {"prompt": prompt.strip(), "requested_seconds": seconds,
                          "requested_aspect_ratio": aspect_ratio,
                          "preferred_model": "agnes-video-new-flash"},
                "estimated_credits": None, "additional_spend_allowed": False,
                "blocker": "PAVO_SUBMISSION_AND_PRICE_CONTRACT_UNVERIFIED"}


def main():
    parser = argparse.ArgumentParser(description="Pavo connection probe; no generation or spending.")
    parser.add_argument("--probe", action="store_true", help="One authenticated read; no account details logged")
    parser.add_argument("--models", action="store_true", help="One public catalog read; no credential sent")
    args = parser.parse_args()
    client = PavoClient()
    try:
        if args.probe:
            data = client.account()
            result = {"connected": data["authenticated"], "plan_returned": data["plan"] is not None,
                      "generation_enabled": False}
        elif args.models:
            data = client.models()
            result = {"catalog_available": True, "model_count": len(data["models"]),
                      "price_verified": False, "generation_enabled": False}
        else:
            result = client.status()
    except PavoError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "generation_enabled": False}))
        return 2
    except Exception:
        print('{"ok":false,"error":"PAVO_INTERNAL_ERROR","generation_enabled":false}')
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
