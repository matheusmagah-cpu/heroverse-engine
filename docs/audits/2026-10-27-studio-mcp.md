# Verified security sweep: studio-mcp, 2026-10-27

## Context

Scope: the new unofficial, read-only YouTube Studio analytics MCP.
- Code: `migration/integrations/studio/studio_client.py`, `migration/integrations/studio/server.py`.
- Registration and CI: `.mcp.json` (`heroverse-studio`, `"${YT_STUDIO_COOKIES:-}"`), `.github/workflows/studio-mcp.yml`
  (new, offline), `.github/workflows/pr-checks.yml` (one test path added).
- Guard: `.claude/hookify.block-studio-cookies-shell.local.md` and its cases in `migration/ops/test_hookify_rules.py`.

Trigger: a new credential (the owner's Studio session cookies, which carry full Google-account power) and a workflow
change (CLAUDE.md: a recorded sweep when a PR touches secrets or `.github/workflows/`).

Branch: `claude/studio-mcp`. Owner decision of 2026-10-27, given after the ToS/account-flag risk was explained:
build it, read-only, limited in code. No cookie exists in this environment; no authenticated request was made.

## Delegation

The implementing session ran the sweep itself (no separate reviewer was available in this run). Categories applied:
secrets and credentials, external integrations, failure turned into a pass, workflow injection, spend. Each candidate
was checked against the code and an offline test that exercises it; nothing was accepted from reading alone.

## Verification

| Finding | Zone | Verdict | Claimed | Verified | Reservations | Proof |
|---|---|---|---|---|---|---|
| S1 cookie value leaks through an error, log, stdout/stderr or tool result | studio-mcp | FALSE POSITIVE | < 8 | Yes | Only fixed codes leave the client; transport exceptions are dropped and raised outside the `except` block (no `__cause__`/`__context__`); `scrub()` removes the cookie text and every value; titles and traffic labels holding a value become `null`/dropped; the server logs nothing (`log_level` CRITICAL, logging disabled). | `studio_client.py` `_request` (`STUDIO_TRANSPORT_ERROR`), `UrllibTransport.__call__`, `scrub`, `_text`; `server.py` `safe_call`; `test_the_cookie_never_appears_in_errors_logs_or_results` (both formats, five exception kinds, root logger at DEBUG, stdout/stderr captured), `test_http_errors_map_to_fixed_codes_and_redirects_are_refused` |
| S2 a write endpoint becomes reachable (edit, delete, upload, comment, privacy...) | studio-mcp | FALSE POSITIVE | < 8 | Yes | One `guard()` before pacing and network: exact host, four fixed read paths with one method each, fixed query, forbidden words refused even if a path is added to the table, body keys per builder. No raw-request tool; tool parameters are typed and validated. | `studio_client.py` `guard`, `ENDPOINTS`, `FORBIDDEN_WORDS`; `Allowlist` tests (each forbidden word x 4 path shapes, also after insertion into `ENDPOINTS`; 6 real write paths from the cited libraries; 12 host/URL tricks; 10 raw paths; methods, queries, bodies), `test_every_request_of_every_tool_is_on_the_allowlist`, `test_no_generic_request_surface`, `test_stdio.py` (no `url`/`path`/`body` parameter) |
| S3 cookies sent to another host or other-domain cookies sent | studio-mcp | FALSE POSITIVE | < 8 | Yes | Only cookies whose domain matches `studio.youtube.com` are kept; redirects are refused (a sign-in redirect would otherwise carry the request elsewhere). | `parse_cookies`, `NoRedirect`; `test_both_cookie_formats_and_domain_filter`, `test_sapisidhash_format_and_value` (`.google.com` and `www.youtube.com` values never sent) |
| S4 header or body injection from tool arguments or the Studio page | studio-mcp | FALSE POSITIVE | < 8 | Yes | Video ids, dates, limits validated by regex/range; page values (API key, channel id, client version, delegated id, session index) extracted by strict regexes; cookie values refused if they hold `;`, `,` or control characters; bodies serialized with `json.dumps`. | `video_id_ok`, `period`, `_ensure_config`, `_keep`; `test_inputs_are_validated_before_any_request` |
| S5 the variable is readable by every process of the session container (`env`, `/proc/*/environ`, a careless `echo`) | studio-mcp | NEEDS DEEPER REVIEW | - | Partly | Inherent to an environment variable of the cloud environment; code cannot close it. Hardening H1 below lowers the chance of an accidental print. Residual risk accepted with the owner's decision; documented in the README. | `.claude/hookify.block-studio-cookies-shell.local.md`; 8 block and 5 allow cases in `test_hookify_rules.py` |
| S6 the environment's HTTPS egress proxy terminates TLS and sees the cookie | studio-mcp | NEEDS DEEPER REVIEW | - | No | Environmental and shared by every credential used in a session (the proxy's CA bundle is installed); outside this zone. Documented in the README. | `/root/.ccr/README.md` (proxy design); README "Credentials" |
| S7 numbers for a custom date range are silently wrong (unverified request shape) | studio-mcp | NEEDS DEEPER REVIEW | - | No | Correctness, not security: the custom-range `timePeriod`, two tabs and the metric names are UNVERIFIED and marked so in every result (`unverified`) and in the README; the lifetime period and the key-metric shape are from two public sources. The live check, step 5, compares with Studio before any use. | `time_period`, `FIELDS`; README "Endpoints" and "Live check" |
| S8 account flag, challenge or sign-out from automated use and a datacenter IP | studio-mcp | ACCEPTED RISK | - | - | Owner decision 2026-10-27. Mitigations: 2.5 s + 0-1.5 s jitter between requests, 40 per session, no automatic retry, 429 stops. | `Pace`; `test_minimum_interval_and_session_budget` |
| S9 workflow injection or secret exposure in CI | studio-mcp | FALSE POSITIVE | < 8 | Yes | `studio-mcp.yml` runs on `pull_request` only, reads no secret, interpolates no `${{ }}` into `run:`, uses the pinned checkout SHA of `pavo-mcp.yml`. `pip install 'mcp==2.3.0'` has no hash pin, as in `pavo-mcp.yml` (recorded in the `actions-ci` sweep). | `.github/workflows/studio-mcp.yml` |
| H1 shell access to the cookie variable | studio-mcp | HARDENING, APPLIED | - | Yes | A hookify rule blocks commands naming `YT_STUDIO_COOKIES` (an empty assignment for tests stays allowed), bare `env`/`printenv`, `/proc/*/environ`. A guard rail, not a sandbox. | `.claude/hookify.block-studio-cookies-shell.local.md`; `test_hookify_rules.py` |

## Confirmed defects

None. Zero confirmed defects from nine examined candidates; one hardening applied in the PR. The findings index gets
no entry.

## Refused or unconfirmed candidates

- S5, S6: environmental; the cookie lives where the owner chose to put it. Revocation path in the README (sign out
  of the session, delete the variable).
- S7: needs the live check; until then the tools say UNVERIFIED in every response.

## Coverage

All scoped files were read in full. Checks run: `migration/integrations/studio/test_client.py` (22 tests),
`test_stdio.py` (real MCP subprocess, two cookie states), `migration/ops/test_hookify_rules.py`,
`test_errors_register.py`, `test_refusal_parity.py`, `test_project_map.py`, `test_dispatch_guard.py`, and the whole
`pr-checks.yml` list (failures only where `cv2` is missing locally and `test_shorts_edit_plan.py`, failing on main
locally too). `uv run --script` started the server and answered `initialize`. No authenticated Studio request; one
unauthenticated reachability probe of `https://studio.youtube.com/` answered 302 (to sign-in), with no cookie.
Not covered: Google's server-side behaviour, the provider proxy, the owner's browser export.

## Hand-off

Merge after CI and review. Then the owner sets `YT_STUDIO_COOKIES` in the cloud environment's settings and a new
session runs the README's live check, recording which UNVERIFIED items became verified (no account numbers).
