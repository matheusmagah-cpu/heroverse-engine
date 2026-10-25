# Pavo MCP preparation: manual review, 2026-10-25

Historical preparation snapshot, before the owner authorized the account connection and before video
generation was implemented. Later validation is recorded in `migration/integrations/pavo/README.md`
and the subsequent Pavo review reports. The pending items below describe that earlier snapshot.

Scope: `.mcp.json`, `.github/workflows/pavo-mcp.yml`, `migration/integrations/pavo/` and the operations entry.
This is a manual code review, not a verified-security-sweep or pr-review-toolkit report. Those plugins are
not available in this execution environment; their required pre-merge reviews remain pending.

## Data and side effects

- Only two fixed HTTPS GET routes are implemented: the public model catalog and authenticated credit balance.
- The session credential comes from the process environment, goes only to the fixed Pavo API origin, and
  is never returned in previews, URLs, errors or logs. Redirects are rejected before forwarding credentials.
- Returned account fields are allowlisted. CLI probe output contains booleans only, without account details.
- Response size and timeout are bounded. Errors use fixed local codes. There are no automatic retries.
- The MCP transport is stdio, with no listening port. All four tools have read-only annotations.
- Video preparation is local and explicitly returns `submitted: false`. No generation, payment, subscription,
  publication or scheduling route exists. A catalog free label is never treated as a price quote.
- PR tests do not receive credentials. The one authenticated workflow step requires manual dispatch on main,
  runs after offline tests, and reads only the intended repository secret. Repository permissions are read-only.

## Verification and limits

- Unit tests exercise redirect refusal, credential echo, route restrictions, response parsing and fail-closed errors.
- A real official MCP SDK subprocess discovers the four tools, reports absent credentials as an MCP error,
  and prepares a local brief without contacting Pavo.
- All 65 existing test files from `pr-checks.yml` passed locally, plus 11 adapter tests and the MCP subprocess test.
  The two video suites were rerun with the required OpenCV dependency after the base interpreter lacked it.
- A fresh `uv run --script` dependency resolution was blocked here by DNS access to PyPI. The SDK subprocess
  test used the installed 2.3.0 package; clean-host dependency installation remains a CI/host check.
- The live unauthenticated catalog GET returned 14 models. No authentication or generation was tested.
- The Pavo website was unavailable in the cloud browser. `PAVO_TOKEN` was not present in repository secrets.
  Nothing was substituted for it and no secret was created.
- The unofficial reference implementations were inspected, not installed or executed. Their dry-run credential
  exposure, guessed submission payload, browser impersonation and proxy rotation are not adopted.

Do not describe this change as a connected account or working video generator. Before enabling generation,
verify the authorized account, exact model/submission contract and included-credit behavior. Keep the normal
commercial-rights, watermark, media QA and publication gates intact.
