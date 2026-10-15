# Official iframe access diagnostic

Diagnostic only; not an adopted recurring AV backend. The source is the exact code deployed in private Site source commit b73790a8beb637ce962a0f6a762f8cfe7817457c. One registered reference and opening window are tested. Actual parent origin and browser referrer policy are used; no credentials, media downloads, proxy or private content.

On 2026-10-15 the correctly hosted iframe reached player-ready but delivered no native image/audio. Do not replay unchanged as a proposed fix. Full observation, scope, source clock, unknown audio counters and private Site identity are in ../../evidence/cloud-video-player-20261015/hosted-embed-observation.json. All approval fields remain false.

Syntax check: node --check player.js. No native production code or completed QA was rerun.
