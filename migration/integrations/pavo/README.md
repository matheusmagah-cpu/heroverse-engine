# HeroVerse Pavo MCP (unofficial)

Uses the owner's existing Pavo account at https://app.pavo-ai.work/.
No upgrade, subscription, card, credit purchase or additional charge is authorized.
An Agnes API key does not authenticate this account.

## Tools and generation boundary

The private stdio server uses the official Python MCP SDK, pinned to 2.3.0 via `uv run --script`.

| Tool | Behavior |
|---|---|
| `pavo_status` | Local configuration status; a configured token is not a verified login. |
| `pavo_account` | Authenticated plan and credit balance read. |
| `pavo_models` | Public video catalog; a Free label is not a price quote. |
| `pavo_prepare_video` | Local brief only, `submitted: false`. |
| `pavo_quote_video` | Authenticated, read-only price calculation for one Flash video. |
| `pavo_generate_video` | One private Flash video, only after a fresh, exact zero-credit quote. |
| `pavo_job` | Read the original job and its completed media; never resubmit it. |

Generation is limited to `agnes-video-new-flash`, one output, 720p, no audio, 4–12 seconds,
and the supported local brief ratios (9:16, 16:9, 1:1). Each call obtains a new quote and refuses
nonzero, estimated, missing or malformed prices before creating a conversation. It sends the same
model, duration, resolution, audio and count to the quote and generation endpoints. There is no
purchase, upgrade, scheduler or publishing endpoint. The quote is not a guarantee of permanent
free access, nor an atomic provider-side price lock.

A submission timeout returns `status: unknown` with the original `conversation_id` and
`retry_submission: false`. Call `pavo_job` for that ID. Never repeat a generation just because
acknowledgement was lost. A socket watchdog cancels stream-body reads after 30 seconds, including
incomplete HTTP chunk metadata. Connection setup uses a 15-second socket timeout; there is no
single deadline for the full quote/create/stream operation. A finished conversation without an
accepted media URL is `incomplete`.
Only HTTPS `.mp4` URLs on the observed Pavo CDN, without query credentials, are returned.
The adapter does not fetch or validate the media content.
MCP account/media responses are private; do not copy them into public logs or receipts.

## Credentials and running

`PAVO_TOKEN` was saved and its name confirmed in the repository secrets on 2026-10-25 after
explicit owner authorization. Its value never entered repository files, chat, screenshots or logs.
The adapter itself does not extract browser credentials: the host injects `PAVO_TOKEN` into its
process environment. Never put the value in `.mcp.json`, `.env`, source, command arguments or reports.
A session token can expire or be revoked; no automatic credential refresh is implemented.

The repository's `.mcp.json` registers the stdio command for a compatible host opening this checkout:

```sh
uv run --script migration/integrations/pavo/server.py
```

This is not an always-on remote MCP URL. A GitHub Actions secret is **not automatically available**
to Claude Code or another MCP host. That host must supply its own authorized environment injection.
The manual `Pavo MCP checks and connection` workflow reads the repository secret only on `main`;
it runs a read-only account probe and prints booleans/fixed error codes, never account details or media.
The stdlib `client.py --probe` and `client.py --models` commands remain read-only.

## Verification, 2026-10-25

- Authenticated account GET passed using the authorized Windows session, with credentials in memory only.
- Flash 5 seconds, 720p, no audio: official price calculation returned required_credits=0,
  final_points=0 and is_estimate=false. The generation quota record also required 0 credits. This verifies that configuration at test time only.
- One private test completed as `GenerationSuccess`, 5 seconds, 720×1280; the resulting CDN resource
  returned HTTP 200, video/mp4 and a nonempty body length. It was not published or scheduled.
- The live test used equivalent PowerShell requests, not this Python adapter. Offline adapter tests and
  the real MCP subprocess test cover its transport and boundaries. Hosted authenticated adapter validation
  remains a separate deployment check.
- Initial submissions omitted official platform/time metadata and returned error 009999 without a
  generation turn or credit-balance change. Adding the verified headers succeeded. The regression is
  guarded by `test_video.py` and recorded as E82 in `migration/ops/ERRORS.json`.
- Commercial rights, watermark behavior and normal media QA/publication gates have not been waived.

## Protocol sources

The request and result contracts were checked against Pavo's public frontend and the live test:

- https://app.pavo-ai.work/_next/static/chunks/9570-bf5e24bf57211f96.js — account, quote and history routes.
- https://app.pavo-ai.work/_next/static/chunks/5334-7f25cc63607fde64.js — exact quote output schema.
- https://app.pavo-ai.work/_next/static/chunks/4321.a585e914ad1fa6c5.js — stream body, metadata headers and SSE.
- https://api.pixa-ai.work/api/v1/aigc/model-capability-spec?model_code=agnes-video-new-flash — public capabilities.
- https://github.com/maoshuhua/pavo-cli/tree/1dbd922ff03447601715fb542d9afcea687345d3 — inspected, not installed;
  its regional test endpoints and on-disk credential store are not adopted.
- https://py.sdk.modelcontextprotocol.io/ — official MCP SDK.
