# TikTok local runner (owner's PC)

Owner, 2026-10-28: every comment on our TikTok videos answered coherently and liked, automatically, by Claude.
TikTok refuses datacenter IPs, so this runs on the owner's Windows PC (device "Matheus"), reached by the main clock
through Desktop Commander (`mcp__Remote_Desktop_Commander__*`). Installed at `C:\HeroVerse\tiktok-runner`.

## What it is
- `runner.py`: Python + Playwright driving the installed Chrome (`channel="chrome"`) on its **own** profile
  (`C:\HeroVerse\tiktok-runner\profile`). It never opens, copies or reads the owner's everyday Chrome/Edge
  profiles, and never reads a cookie value or a password: only the presence of the `sessionid` cookie's name.
- `tiktok_core.py`: the rules (caps, pacing, ledger, parsing of TikTok's own JSON), tested by
  `test_tiktok_core.py` on every PR.
- `selectors.json`: the page selectors. When TikTok changes its page, `runner.py probe VIDEO_ID` shows which ones
  still match; fix them here.
- `vendor/`: the repository's reply gate (`reply_policy.py`, `kjv_check.py`, the KJV), installed by `deploy.py`. A
  reply that fails it is refused on the PC too; without it the runner answers nothing.
- `ledger.json` (comment id → ATTEMPTING / REPLIED / UNCERTAIN / SKIPPED), `out/`, `logs/runner.log`: local state,
  not in git. `ATTEMPTING` is written before the first click, so a run that dies never acts twice.

## Commands (PowerShell, in `C:\HeroVerse\tiktok-runner`)
| Command | Does |
|---|---|
| `.venv\Scripts\python deploy.py <commit or branch>` | install/update from the public repository |
| `.venv\Scripts\python runner.py login` | opens a Chrome window at TikTok's login; **the owner logs in by hand once** |
| `.venv\Scripts\python runner.py status` | `LOGGED_IN` / `NOT_LOGGED_IN` |
| `.venv\Scripts\python runner.py comments` | our videos (@heroverse.official) and their viewers' undecided comments → `out\comments.json`; read-only |
| `.venv\Scripts\python runner.py reply --in out\replies.json [--dry-run]` | likes and answers each REPLY, records each SKIP |
| `.venv\Scripts\python runner.py probe <video id>` | selector check on one of our video pages; read-only |
| `.venv\Scripts\python runner.py story <video id>` | `STORY_WEB_UNSUPPORTED` (below); does nothing |

`out\replies.json`: `{"replies": [{"comment_id", "video_id", "author", "comment_text", "decision": "REPLY",
"text", "verse": {"reference", "quote"}?} | {..., "decision": "SKIP", "reason": "spam|hate|provocation|..."}]}`
(the same decision format and gate as YouTube's `migration/publish/comment_replies.json`).

Every REPLY requires the original `comment_id`, `video_id`, profile `author` handle and full `comment_text`.
The runner accepts only one visible container with an explicit matching comment id, exact profile link and full
text (layout whitespace may differ). Missing ids, changed selectors, duplicate targets or mismatched text stop
before a like/reply. `_comment_id_attributes` in selectors.json lists accepted DOM attributes; their availability
has **not** been validated on the owner's live page. If TikTok does not expose one, the runner reports
`COMMENT_IDENTITY_UNVERIFIABLE` and needs a verified identity adapter; it never falls back to a text prefix.

Immediately before either write leaves the browser, a route guard also checks its video id and comment/parent id
(and like action or exact reply text), aborting missing, ambiguous or mismatched fields. Only a response containing
the expected parent, video, account, text and a new reply id becomes REPLIED; incomplete confirmation stays
UNCERTAIN and cannot be retried automatically. No real post was used to validate this contract.

## Pacing and limits (owner)
One comment at a time; 4-15 s between the steps on one comment, 45-240 s between comments; at most 3 a run, 20 a
day, and 20 min after the last action of an earlier run. Only our own videos (the page must be
`/@heroverse.official/video/<id>` and the id must be in the last `comments` listing). No captcha solving, no
fingerprint or webdriver masking, no proxy: a challenge page stops the run (`CHALLENGE`) for the owner to look at.
A visible window by default (`--headless` exists but TikTok challenges it sooner).

## Stories
`story` posts nothing: TikTok Stories are created in the mobile app; the web upload (TikTok Studio) has no Story
option. Checked 2026-10-28 from the PC: TikTok's help page "TikTok Stories" (faq_detail?id=7605444292726905364)
gives one way to post a Story, "In the TikTok app, tap the Add post + button", and no computer steps. If TikTok adds it on the web, this command is where it goes.

## Discovery (2026-10-28)
No browser profile on the PC is logged in to TikTok (read-only check, counts only: Chrome Default has 9 tiktok.com
cookies and no login cookie and no www.tiktok.com page in its history; Chrome "Profile 1" and "Profile 3" and Edge
Default have no TikTok history). The runner therefore uses its own profile, which the owner logs into once with
`runner.py login`.

Dry run the same day, logged out and headless: our profile page loaded (HeroVerse, 1070 followers) but TikTok put a
"Drag the slider to fit the puzzle" challenge over the video list, so `comments` stops with CHALLENGE (exit 4,
E142). Whether a logged-in, visible window gets through without a puzzle is the first thing to see after the login.
