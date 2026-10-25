# HeroVerse Pavo MCP (unofficial, account connection pending)

Owner authorization, 2026-10-25: use the existing paid Pavo subscription for HeroVerse.
No upgrade, new subscription, card, credit purchase or additional charge is authorized.
The site is https://app.pavo-ai.work/; an Agnes API key does not authenticate this account.

## What is implemented

The repository's `.mcp.json` registers a private stdio server using the official Python MCP SDK, pinned
to 2.3.0 through `uv run --script`. It runs wherever the MCP host checks out this repository; no public
server, paid hosting or inbound network port is required. It is not an always-on hosted MCP endpoint.

| Tool | Behavior |
|---|---|
| `pavo_status` | Local configuration status. A present credential is not a verified login. |
| `pavo_account` | One authenticated GET for the plan label and credit balance; unknown fields remain null. |
| `pavo_models` | One public GET for video model names and free labels; these are not price quotes. |
| `pavo_prepare_video` | Local creative brief only; explicitly returns `submitted: false`. |

**Video generation is not implemented or enabled.** The unofficial candidate's submission does not bind
a model or quoted price and its successful video path is unproven. The paid subscription does not resolve
those technical gaps. No guessed POST is sent. This module is not connected to the production or publishing queue.

## Credentials and running

`PAVO_TOKEN` must be injected into the MCP process environment by the authorized host's secret store.
Never place its value in `.mcp.json`, source files, `.env`, command arguments, receipts, screenshots or logs.
This integration does not extract browser storage, request a password, or send credentials to the repository author.
For Actions, the only intended storage is the `PAVO_TOKEN` repository secret in `matheusmagah-cpu/heroverse-engine`.
A GitHub Actions secret is **not automatically available** to Claude Code or any other MCP host.

With `uv` installed, open this repository in a compatible MCP host or run:

```sh
uv run --script migration/integrations/pavo/server.py
```

Stdlib CLI, without the MCP SDK:

```sh
python3 migration/integrations/pavo/client.py          # local status only
python3 migration/integrations/pavo/client.py --models # one public catalog read
python3 migration/integrations/pavo/client.py --probe  # one authenticated read; summary only
```

The manual `Pavo MCP checks and connection` workflow uses the repository secret only on `main`.
It prints fixed status codes and booleans; no balance, account identifier, response body, token or headers.

## Validation and completion boundary

Offline tests cover token echo, redirects, route allowlisting, absent/invalid credentials, bounded errors,
malformed responses and absence of generation/spending. `test_stdio.py` connects to a real MCP subprocess.
On 2026-10-25 the unauthenticated catalog probe returned 14 models. This verifies only the public read route,
not account access, prices, a subscription entitlement or successful generation.

The initial connection is pending: the cloud browser showed `Site Unavailable` for the exact Pavo URL;
the repository secret was absent. Local tests cannot validate the account, subscription, a live price or a video.
Resume with an authorized credential source, one read-only account probe, then verified submission and price
contracts before adding generation. Never evade access restrictions, rotate proxies or impersonate a browser.
Any eventual clip remains a review artifact until commercial rights, watermark, media QA and the normal gates pass.

Research references (reviewed 2026-10-25; no third-party package was installed):
- https://github.com/rsfree/pavo-ai — observed route names;
  its dry-run header exposure and unverified generation payload are not adopted.
- https://github.com/yanzhao77/pavo-ai-agent — a separate Agnes API storyboard application, not this account integration.
- https://py.sdk.modelcontextprotocol.io/ — official MCP SDK.
