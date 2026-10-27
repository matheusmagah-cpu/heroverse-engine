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
| `pavo_quote_video` | Authenticated, read-only price calculation for one Flash video, input images, input audios (with their durations) and the `sound` flag counted. |
| `pavo_generate_video` | One private Flash video, only after a fresh, exact zero-credit quote: text only, first frame (+ optional last frame), or up to 5 reference images; with references, up to 3 input audios (`audios`, our narration); `sound` (default false). A nonzero quote refuses and reports the quoted number. |
| `pavo_job` | Read the original job and its completed media; never resubmit it. |

Generation is limited to `agnes-video-new-flash`, one output, 720p, 4–12 seconds, and the
ratios of its public capability spec (9:16, 3:4, 1:1, 4:3, 16:9, 21:9). Each call obtains a new quote and refuses
nonzero, estimated, missing or malformed prices before creating a conversation (or uploading anything); the refusal
names the quoted `required_credits`, `final_points` and `is_estimate`. It sends the same model, duration,
resolution, sound flag, input images, input audios and count to the quote and generation endpoints. There is no
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

### Input images (v0.3, 2026-10-25)

What Flash accepts (`model-capability-spec`, checked 2026-10-25): modes text_to_video, first_frame,
first_last_frame and reference_image; up to 5 images (JPEG/PNG/WebP, 15 MiB, side 256–5760 px, aspect 0.4–2.5);
up to 3 input audios (MP3/WAV, 2–12 s in total; used since v0.4, below). The adapter takes repository-relative PNG/JPEG
paths only (our approved stills and character sheets), validates them locally against that spec before any
request, and refuses paths outside the repository.

- `first_frame` (+ optional `last_frame`): Pavo's `frames_to_video`, `images` = [first, last], like the web client.
  A last frame alone is refused (the web client refuses it too).
- `references` (1–5): Pavo's `omni_to_video`, `images` plus `creative_prompt_json` blocks naming each image by
  `source_index`: the same character every time (`production/characters/`).
- Frames and references are exclusive. The quote sends the images as `inputs`, so it prices them; only an exact
  zero-credit quote lets the call upload anything. Each image then goes through Pavo's presigned upload
  (`/v1/file/presigned-url`, a PUT to the storage URL **without** the Pavo credential, `/v1/file/inspect`). A
  failed upload creates no conversation. Uploading is not a generation and costs nothing.
- The storage host of the presigned PUT is not yet observed live; if the network policy denies it, the call fails
  with `PAVO_UPLOAD_HOST_UNREACHABLE` before any job exists.

### Audio track of the output

By default the request sends `sound: false` / `gen_audio: false`, but the first live Flash clip (2026-10-25) came
with an audible AAC track (mean −15.7 dB). Without input audio, strip it (`ffmpeg -an`) before using a clip. With
our narration as input audio (v0.4), check that the output track is our narration before keeping it.
MCP account/media responses are private; do not copy them into public logs or receipts.

### Input audio and sound (v0.4, 2026-10-26)

Goal: a narrator character who speaks **our** narration on screen. Flash's spec (`input_audio`): up to 3 files,
`audio/mpeg` or `audio/wav`, 15 MiB each, each 2–12 s and 2–12 s in total. The adapter takes repository-relative
`.mp3`/`.wav` paths and checks them locally before any request: size, type, per-file and total duration. WAV duration
comes from its header (`data` size / byte rate); MP3 duration from `ffprobe`; an MP3 whose duration cannot be measured
(no ffprobe, unreadable) is refused (`INPUT_AUDIO_DURATION_UNMEASURABLE`), never estimated.

What the web client allows (chunks of 2026-10-26, see Protocol sources):
- Audio upload exists only in `omni_to_video` (references), and only when the model's `input_audio.max_count > 0`
  (Flash: 3). `frames_to_video` (first/last frame) has no audio upload, and audio without any image is refused
  (`audioOnlyUploadNotSupported`). The adapter mirrors that: `audios` needs `references` (1–5 images);
  `AUDIO_NEEDS_REFERENCES` / `AUDIO_AND_FRAMES_EXCLUSIVE` otherwise. (For the older `agnes-video` model the client
  strips audio before sending; Flash keeps it.)
- Upload: the same presigned flow as images (`purpose: "chat_attachment"`, `content_type` = the file's MIME,
  `filename`; PUT without the Pavo credential; `/v1/file/inspect`).
- Quote: each audio is one `inputs` entry `{"count": 1, "media_type": "audio", "duration_seconds": <measured>}`
  (images stay `{"count": 1, "media_type": "image"}`); the output's `gen_audio` carries the sound flag.
- Stream: `audios: [{"url", "meta_data"?}]` beside `images`, and `sound: <bool>`. In `creative_prompt_json` the client
  names a mentioned audio as `{"type": "audio", "url"}` (no `source_index`, unlike images); the adapter adds one such
  block per audio after the image blocks, as if each were mentioned in the prompt.
- Sound: the client shows its "Generate audio" switch only when the spec's `output_video.audio_modes` contains
  `with_audio` (e.g. `seedance-2-0`); Flash's spec has no `audio_modes` and no `supports_generated_audio`, so the
  client never sends `sound: true` for Flash. With the switch hidden it sends `sound: "auto"` and omits `gen_audio`
  from the quote. The adapter keeps `sound: false` by default (as in v0.3) and sends `sound: true` /
  `gen_audio: true` only when asked; whether Flash honours it, and its price, is for the live quote to show.
- Lip sync: neither the spec nor the client mentions lip sync; whether Flash makes the referenced character speak the
  input audio (rather than laying it as a soundtrack) is not documented. Prompt it explicitly ("the narrator speaks
  to camera") and check the first clip.

### Image generation (v0.5, 2026-10-27)

Goal: Pavo's own free still model as the source for image-first scene stills (`production/bible/scene_stills.py`),
because the Cloudflare FLUX stills of genesis-08 fell below 9.5 (`evidence/shots/genesis-08-short/stills-review-*`).

| Tool | Behavior |
|---|---|
| `pavo_quote_image` | Authenticated, read-only price of one `agnes-image` still: ratio, resolution, reference images counted. |
| `pavo_generate_image` | One private still, only after a fresh, exact zero-credit quote; a nonzero quote refuses with the number. |
| `pavo_image_job` | Read the still's job and its image URL; an uncertain submission is checked here, never resent. |

- Model: `agnes-image` ("Agnes Image 2.5 Flash", tagged Free in `mode_support_models?mode_code=generate_image`).
  Every other image model of that catalog (GPT Image, Seedream, Qwen Image, NanoBanana...) is paid: the adapter
  sends only `agnes-image`, to the quote and to the stream alike.
- Spec (`model-capability-spec?model_code=agnes-image`, 2026-10-27): modes text_to_image and image_to_image; ratios
  9:16, 2:3, 3:4, 1:1, 4:3, 3:2, 16:9, 21:9; resolutions sd/hd/uhd (1K/2K/4K, default sd); prompt up to 10000
  characters; up to 6 input images (role `reference`, JPEG/PNG/WebP); one output (PNG/JPEG); seed supported (not sent).
- Quote (chunk 5334): `{model_code, outputs: [{count: 1, media_type: "image", resolution}], inputs?}`; no ratio and no
  duration. Stream (chunks 9821 `function A`, 4321): `mode: "generate_image"`, `model`, `ratio`, `resolution`,
  `creative_prompt_json` (text block + `{type: "image", url, source_index}` per reference), `images: [{url, meta_data?}]`;
  no `sound` or `duration`. The adapter also sends `count: 1`, as for video. References go through the same presigned
  upload as video inputs, after the free quote and before the conversation.
- Result: history `GenerationSuccess`, `results[].url` (or `image_url`), accepted only as an HTTPS `.png/.jpg/.jpeg/.webp`
  on the Pavo CDN without a query; the adapter does not fetch it.
- Live, 2026-10-27: 9:16 sd and hd quoted exactly 0 (`is_estimate: false`); six 9:16 hd stills of genesis-08 (s-dust,
  s-ridge, s-board, two each), each after its own fresh zero quote, came back as 1472x2624 JPEGs on the CDN
  (stills registry run `20261027`, `source: pavo-agnes-image-2.5-flash`, contact sheet
  `production/bible/stills/sheets/genesis-08-short-20261027.jpg`). Text-only. References live, 2026-10-27: one 9:16 hd thumbnail candidate of genesis-09 with Noah's two approved
  references (quoted exactly 0 with 2 input images) kept his approved face; the text-only twin drew another man
  (`evidence/thumbs/genesis-09-short-20261027.json`).
- Stills with references (E122): a still whose prompt names a prop (the ark; from part 9 by its phrase
  `plan_check.ARK_PHRASE` only, E123) is made with that prop's approved
  reference images (`production/characters/props.json`). `scene_stills.py prepare PLAN SHOTS N RUN OUT --engine pavo`
  lists each candidate's `references` (repository paths, at most 6): pass them as `references` to
  `pavo_quote_image` (input images counted; exact 0 only) and to `pavo_generate_image`, then read the job back with
  `pavo_image_job`. The candidate's sidecar records `references` ([{record, sha256}], from `reference_records`) and
  `pavo`: `generate` = the generate answer (`model`, `conversation_id`, `input_images`, `quote`) and `job` = the
  read-back (`conversation_id`, `status`). `finalize` and `approve` refuse a candidate whose `input_images` is not the
  number of required references (STILL_PROP_UNREFERENCED); FLUX (`scene-stills.yml`) cannot send references and
  `prepare` refuses such a still on it.

### Free image quota (E124, 2026-10-27)

A 0 quote does not mean the free quota is available. Pavo's free `agnes-image` quota ran out after ~180 stills in one
day (genesis-09 runs 2026102701-05, the ark props and probes); `pavo_quote_image` kept answering an exact 0
(`required_credits` 0.0, `is_estimate` false) and `pavo_image_job` read back only `status: failed`, with no image and no
reason, while the owner's app showed "the free model quota has been used up ... try again in 3 hours" (nothing was
charged). 31 submissions of run 2026102705 were spent on nothing. The adapter now guards it (`quota.py`, wired in
`server.py`):

- `PAVO_DAILY_CAP`: at most 120 images a UTC day (env `PAVO_IMAGE_DAILY_CAP`, or `daily_cap` in the ledger), counted
  for every submission that created a conversation, refused before the quote (nothing is sent).
- `PAVO_FREE_QUOTA_SUSPECTED`: two read-backs in a row that end `failed` with no image (each job once) suspend
  generation for 3 hours; then exactly one probe may go, and every other call is refused until that probe reads back:
  failed suspends again at once, completed lifts it. Only a job submitted after the suspension began can lift it.
- `PAVO_LEDGER_UNREADABLE`: a ledger that cannot be read (merge-conflict markers, a naive or garbage time, a
  non-integer count) fails closed; fix it by PR. A missing ledger is a fresh one.
- The ledger is `migration/evidence/pavo/image-ledger.json` (env `PAVO_IMAGE_LEDGER`): day counts, the failed streak,
  recent failed conversation ids and `suspended_until`; no credential or URL. Commit it with the run's evidence.
- Read back every job before submitting many more: a `failed` read-back is a stop signal, not noise.

## Authorization

Standing owner authorization (2026-10-25): generations need no per-clip approval in the chat; every limit above
stays. Pavo is the first source of AI video for the project (`strategy/DECISIONS.md`). `PAVO_RATE_LIMITED` is refused
before any job exists; send that call again later.

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
- The v0.4 audio request shape (`audios`, audio `inputs` with `duration_seconds`, `sound`/`gen_audio` true) comes
  from the public web client of 2026-10-26 (chunks 9821, 4321, 5334, 8736, 9570); it is covered offline by
  `test_video.py` and not yet verified live.
- Commercial rights, watermark behavior and normal media QA/publication gates have not been waived.
- 2026-10-25, through this MCP: one 6-second 9:16 Flash clip after a fresh exact zero-credit quote completed
  (720×1280, 24 fps, 6.59 s, no visible watermark, clip_check clean, audible audio despite `sound: false`):
  `migration/evidence/pavo/20261025/` on branch `claude/pavo-test-20261025`. 12 s 9:16, 10 s 16:9 and 4 s 1:1
  quoted exactly 0 the same evening.
- The frames/reference request shape comes from the public web client (chunks 9821, 4321, 5334, 9570 of
  2026-10-25: `function A` send params, worker stream body, `inputs` pricing, presigned upload); it is covered
  offline by `test_video.py` and not yet verified live.

## Protocol sources

The request and result contracts were checked against Pavo's public frontend and the live test:

- https://app.pavo-ai.work/_next/static/chunks/9570-bf5e24bf57211f96.js — account, quote and history routes;
  `getCreativePromptBlocks` (image blocks with `source_index`, audio blocks `{type: "audio", url}`).
- https://app.pavo-ai.work/_next/static/chunks/9821-634c397c0baec9f9.js — module 1426 `function A` (send params:
  `images` = image materials, `audios` = audio materials `{url, meta_data?}`, `sound: settings.generateAudio ?? "auto"`,
  `creative_prompt_json` outside frames mode); `L` = `audioOnlyUploadNotSupported`; capability mapping (`audio_modes`
  from `output_video.audio_modes`, `supports_audio_generation` from `supports_generated_audio`,
  `supports_custom_audio_upload` from `input_audio.max_count`); upload check `c()`: audio only in `omni_to_video`.
- https://app.pavo-ai.work/_next/static/chunks/5334-7f25cc63607fde64.js — quote hook (`inputs` built from materials:
  audio/video carry `duration_seconds`; `gen_audio` only when `generateAudio` is set); the "Generate audio" switch is
  shown only for `audio_modes` containing `with_audio`.
- https://app.pavo-ai.work/_next/static/chunks/8736-8c5d1d01f45dc336.js — upload: audio duration read from browser
  metadata, then `presigned-url` (`purpose: "chat_attachment"`), PUT, `inspect`.
- https://app.pavo-ai.work/_next/static/chunks/5334-7f25cc63607fde64.js — exact quote output schema.
- https://app.pavo-ai.work/_next/static/chunks/4321.a585e914ad1fa6c5.js — stream body, metadata headers and SSE
  (`audios` passed through when nonempty, `sound` when defined).
- https://api.pixa-ai.work/api/v1/aigc/model-capability-spec?model_code=agnes-video-new-flash — public capabilities.
- https://github.com/maoshuhua/pavo-cli/tree/1dbd922ff03447601715fb542d9afcea687345d3 — inspected, not installed;
  its regional test endpoints and on-disk credential store are not adopted.
- https://py.sdk.modelcontextprotocol.io/ — official MCP SDK.
