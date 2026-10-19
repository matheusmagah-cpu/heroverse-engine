# Dot capability test — 2026-10-19 (BLOCKED)

Scope: issue #183 and SPEC-FIX 1. No publication or approval.

## Verified environment

- Python: 3.12.14 (`python3 --version`).
- ffmpeg: 7.1.5-0+deb13u1, GCC 14; libx264 and libass listed in configuration. Rendering not yet tested.
- Workspace disk at inspection: 25 GiB available (`df -h /workspace`). Capacity is not a guaranteed file-size limit.
- Maximum task runtime, input size, output size and image quota: unknown.
- Image model name: unknown. Generation not yet attempted; no claim to a particular or best model.

## A: reference acquisition blocker

On 2026-10-19 at approximately 15:40 UTC, the first direct request for `https://i.ytimg.com/vi/OuqwfEgNavE/maxresdefault.jpg` returned 195 bytes of HTML, not a JPEG: `Site Unavailable` / `Unable to access this site.` The web-open tool also reported that URL inaccessible. The cloud browser displayed the same Site Unavailable page. The user's computer was not used. No visual facts were inferred from these failures.

Exact question for Claude: Can you attach the six original winner thumbnail JPGs as accessible repository files or public release assets, keeping their video IDs and source URLs, so I can inspect actual pixels before generating A? The inaccessible image is OuqwfEgNavE; the other five have not been inspected. I have not invented their composition or skipped the mandatory reference step.

## Delivery and status

Git clone succeeded. Direct git push failed with `fatal: could not read Username for 'https://github.com': No such device or address`. This initial report and draft branch were created through the connected GitHub contents API; binary delivery has not yet been tested. No image or video deliverable exists yet. No paid external API job was started. Work is paused under DOT_PROTOCOL pending the reference input. No acceptance or quality claim is made.
