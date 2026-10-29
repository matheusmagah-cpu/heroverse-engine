# E215: repair the brief before another still attempt

Base: `eacffdf50e2b33e464e08da2d49363149aad17e3`.
Run `40793104573` completed successfully and stored three DRAFT candidates on
`claude/stills-genesis-09-short-40793104573`, exact commit
`0c450321504d482b932196b3c2778da8319ddc16`. All three JPEG hashes and 1080x1920
dimensions were checked against their records. This proves file delivery, not quality.

The current ChatGPT Work session opened all three complete images. These are
visual triage findings, not a qualified Claude/Astra approval, numerical score or
audiovisual review:

| Shot | Exact JPEG SHA-256 | Observed mismatch |
| --- | --- | --- |
| s-noah-door | 66e4d22a4fb067910af6ffd1b6664bcc1b1b53a587d2426eb9b15e46836b0030 | Spectacles and a turned head; a horizontal beam interrupts the doorway opening. |
| s-rock | 50885dfe446b2ba71bc8294fb03366b2eb1dcbfdff940cd58f4a070742c0c4be | Visible dry feet above the flood; a distant craft is not the specified empty flood background. |
| s-noah-lamp | 6296cc16da0a853cd2533148e1c940c06f557b5d6c55c987bfcd607c271d2342 | Required lamp is not visible; the lamb is cut by the crop and the scene is too dark to establish the intended action. |

The three existing prompts already named the desired objects. This failure does
not prove that adding a word guarantees success. The repair strengthens spatial
and exposure instructions: a symmetric direct rear view, a continuous doorway
opening reaching the floor, water visibly intersecting shins, and the illuminated
lamp/lamb explicitly inside the central portrait crop. The static regression
failed eleven clauses before the edit and passes after it. Its scope is brief
intent, not pixel detection or a replacement quality gate.

The existing material preflight accepted the revised prompts. It first refused
the incidental term `waterline` under E123; the brief now says `surface`, without
changing the prop rule. Sent prompt lengths with style are 1129/1017/1219,
below the existing 2048-character provider cut. No approved still, shot, source,
script, voice, thumbnail, reviewer allowlist or frozen QA is edited.

One new request is a deliberate corrected-input attempt, one candidate per shot,
not a replay of an uncertain result. The prior request is acknowledged and its
three exact outputs are known. The live guard must still pass daily allocation,
capacity and concurrency. No Pavo/Buzzy spend or paid fallback is enabled.
Monitor the resulting run and hashes; do not duplicate it. Old candidates retain
their DRAFT records and cannot be approved against a changed prompt by the
existing `STILL_PROMPT_CHANGED` check. No candidate is approved in this PR.

Manual diff review: only the three briefs, the static regression, E215, this audit
and the single bounded request change. No unavailable review plugin is claimed.
Full canonical validation and remote CI must be recorded separately before merge.
