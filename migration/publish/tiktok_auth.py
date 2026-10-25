#!/usr/bin/env python3
"""One-time TikTok authorization for tiktok_publish.py (owner, 2026-10-25).

  url      -> prints the TikTok consent link for the owner (client_key is public; it is part of every consent link)
  exchange -> trades the one-time code (env TIKTOK_CODE, from tiktok-callback.html) for tokens and stores the refresh
              token in the repository secret TIKTOK_REFRESH_TOKEN (stdin through `gh secret set`, GH_SECRETS_PAT);
              prints only the granted scopes, never a token
usage: tiktok_auth.py url|exchange
"""
import json
import os
from pathlib import Path
import secrets
import sys
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tiktok_publish as tp  # noqa: E402

REDIRECT = "https://matheusmagah-cpu.github.io/heroverse-oauth-compliance/tiktok-callback.html"
SCOPES = "user.info.basic,video.upload,video.publish"
NEEDED = {"video.upload", "video.publish"}


def consent_url(client_key, state=None):
    return "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode({
        "client_key": client_key, "scope": SCOPES, "response_type": "code", "redirect_uri": REDIRECT,
        "state": state or secrets.token_urlsafe(12)})


def exchange(env=os.environ, call=tp.http, store=tp.store_refresh_token):
    code = env.get("TIKTOK_CODE", "").strip()
    if not code:
        raise SystemExit("TIKTOK_CODE_MISSING")
    form = urllib.parse.urlencode({"client_key": env["TIKTOK_CLIENT_KEY"], "client_secret": env["TIKTOK_CLIENT_SECRET"],
                                   "code": urllib.parse.unquote(code), "grant_type": "authorization_code",
                                   "redirect_uri": REDIRECT}).encode()
    r = call("POST", tp.API + "oauth/token/", data=form, headers={"Content-Type": "application/x-www-form-urlencoded"})
    if not r.get("refresh_token"):
        raise SystemExit(f"TIKTOK_CODE_EXCHANGE_FAILED {r.get('error', '')} {r.get('error_description', '')[:160]}")
    granted = set((r.get("scope") or "").replace(" ", "").split(","))
    store(r["refresh_token"])
    missing = sorted(NEEDED - granted)
    print(json.dumps({"tiktok_auth": "STORED", "scopes": sorted(granted), "missing": missing}))
    return 1 if missing else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["url"]:
        print(consent_url(os.environ["TIKTOK_CLIENT_KEY"]))
    elif sys.argv[1:] == ["exchange"]:
        sys.exit(exchange())
    else:
        raise SystemExit(__doc__)
