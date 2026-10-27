# HeroVerse Studio MCP (unofficial, read-only)

Reads the owner's own YouTube Studio analytics (impressions, impressions CTR, views, unique viewers, average view
duration and percentage, subscribers, traffic sources, retention, real-time) through the internal endpoints the Studio
web client calls, signed in with the owner's Studio session cookies. Owner decision, 2026-10-27, after being told the
risks: "our own MCP can be limited to what we want".

- **Unofficial.** These are not public APIs. Google may change or block them at any time; a change shows up as
  `STUDIO_CONFIG_NOT_FOUND`, `STUDIO_REQUEST_REFUSED`, `STUDIO_HTTP_REFUSED` or empty metrics, never as a guess.
- **ToS and account risk, accepted by the owner on 2026-10-27.** Automated use of a logged-in session is outside
  YouTube's Terms of Service. The account could be flagged, challenged or signed out. The MCP keeps a person's pace
  (below) and reads only, but that lowers the risk; it does not remove it.
- **Read-only by construction**, not by promise (next section).
- The official YouTube Reporting API reach (impressions/CTR) for the daily report is separate work and does not
  depend on this MCP.

## Read-only by construction

Every request goes through one function, `studio_client.guard(method, url, body)`, before any pacing or network:

| Rule | Refused with `STUDIO_ENDPOINT_REFUSED` |
|---|---|
| Scheme and host exactly `https://studio.youtube.com` (no port, userinfo, fragment, other case) | any other host, `www.youtube.com`, look-alike hosts, `http://` |
| Path in a fixed table of four read endpoints, each with its one method | any other path, a trailing slash, `..`, `%`-encoding, upper case |
| No path may contain `delete`, `update`, `edit`, `set`, `upload`, `comment`, `create`, `remove`, `mutate`, `publish`, `privacy` (`creator` is the one word allowed to contain `create`) | refused even if someone adds such a path to the table |
| POST query exactly `alt=json&key=<public web key>`; GET with no query and no body | extra or reordered parameters |
| POST body: a dict with `context` and only the top-level keys that endpoint's builder sends | any other key |

There is no raw-request tool. Bodies are built inside `studio_client.py` from typed tool arguments: video ids match
`[A-Za-z0-9_-]{11}`, dates are `YYYY-MM-DD` (inclusive, at most 366 days, not before 2005-04-23 or after today) or
`start="lifetime"`, `limit` 1-50, `per_video` 0-5. Redirects are never followed (a signed-out session is redirected to
Google sign-in: `STUDIO_SIGNED_OUT_REDIRECT`). Responses are capped (4 MiB page, 3 MiB JSON).

## Tools

| Tool | Requests | Returns |
|---|---|---|
| `studio_status(verify=true)` | 0 without a usable cookie; else 2 on first use (Studio page + channel) | cookie present/parsed, SAPISID present, session verified, channel id, title, subscribers, video count, calls left. Never a cookie value. |
| `studio_video_metrics(video_id, start, end)` | 4 (+1 for the page on first use) | impressions, impressions CTR, views, unique viewers, average view duration, average percentage viewed, subscribers gained, watch time, traffic sources, every other key metric by its Studio name, card types |
| `studio_channel_metrics(start, end, limit=10, per_video=3)` | 3 + `per_video` | channel totals (overview + reach), traffic sources, real-time series, ranked table of the latest `limit` uploads (lifetime views, likes, comments; period impressions/CTR/views/unique viewers for the top `per_video`) |
| `studio_retention(video_id, start="lifetime", end="")` | 1 | retention curve points and the engagement key metrics |

Both dates empty means the last 28 full days (UTC). Each friendly field is `{"value", "metric"}` (the Studio metric
name it came from) or `null`; `metrics` and `other_metrics` hold every metric read, by its Studio name, so a name the
mapping does not know yet is still visible. **Units are UNVERIFIED** (durations may be milliseconds; CTR a percent or a
fraction) until the live check.

**Responses are private.** They are the owner's account data: never copy them into public logs, workflow output,
receipts, `migration/evidence/` or a PR.

## Pace

At least 2.5 s plus a random 0-1.5 s between two requests, and at most 40 requests per server process (one MCP
session): `STUDIO_CALL_BUDGET_EXHAUSTED` after that; restart the session to read more. An upstream 429 is
`STUDIO_RATE_LIMITED`: stop for the day. Nothing is retried automatically.

## Credentials

`YT_STUDIO_COOKIES` holds either the content of a Netscape `cookies.txt` export or a `name=value; name=value` header
string. Only cookies whose domain matches `studio.youtube.com` (`.youtube.com`, `studio.youtube.com`) are sent; expired
lines are dropped. The Authorization header is the Studio web client's
`SAPISIDHASH <unix seconds>_<sha1("<unix seconds> <SAPISID> https://studio.youtube.com")>` (SAPISID, or
`__Secure-3PAPISID` when SAPISID is absent), with `X-Origin: https://studio.youtube.com`.

**These cookies grant full power over the Google account**, not just analytics. So:

- They live only in the cloud environment's settings as the environment variable `YT_STUDIO_COOKIES`, which the
  host injects into this server's process (`.mcp.json`: `"${YT_STUDIO_COOKIES:-}"`). Never in chat, a file, `.env`,
  `.mcp.json`, a command line, an issue, a log or a GitHub secret read by a workflow (no workflow uses them).
- The code never logs, echoes or writes them. Every error is a fixed code; `scrub()` removes the cookie text and
  every cookie value from any message that leaves the process; transport exceptions are dropped (not chained), and
  a remote title that contains a cookie value is returned as `null`. Tests assert all of this with synthetic cookies.
- An environment variable of the cloud environment is visible to every process of the session container, not only
  to this server. The hookify rule `.claude/hookify.block-studio-cookies-shell.local.md` blocks shell commands that
  name `YT_STUDIO_COOKIES`, bare `env`/`printenv` dumps and `/proc/*/environ` (tested in
  `migration/ops/test_hookify_rules.py`); it is a guard rail against mistakes, not a sandbox.
- The cloud environment's HTTPS egress goes through its agent proxy, like every other credential used in a session.
  If that network policy does not allow `studio.youtube.com`, every call answers `STUDIO_UNREACHABLE` (or the
  proxy's 403 as `STUDIO_ACCESS_REFUSED`): allow the host in the environment's network settings.
- To revoke: sign out of that browser session (or "Sign out of all other sessions" in the Google account), then
  delete the variable.

### How the owner activates it

1. In a desktop browser, sign in to https://studio.youtube.com with the channel's account (select the HeroVerse
   channel if the account has several).
2. Export the cookies of `studio.youtube.com` in Netscape `cookies.txt` format with a local cookies.txt exporter
   extension (one that exports to a file, without uploading anywhere). Only the youtube.com cookies are needed.
3. Open the file, copy its whole content, and paste it as the value of a new **environment variable**
   `YT_STUDIO_COOKIES` in the cloud environment's settings (the cloud environment menu in the session's title bar,
   then Edit; an environment variable, because the server reads it from its process environment). Never paste it in
   the chat. Delete the local file afterwards.
4. Start a new session (environment variables are read at start), then ask Claude to run `studio_status`.

**A cloud datacenter IP may trigger a Google security check** ("Was this you?", a sign-out of that session, or an
e-mail about a new sign-in). If `studio_status` answers `STUDIO_SIGNED_OUT_REDIRECT`, `STUDIO_SESSION_EXPIRED` or
`STUDIO_CONFIG_NOT_FOUND`, open Studio in the browser, confirm any security prompt, export the cookies again and replace
the variable. Cookies also expire on their own; no automatic refresh exists.

## Endpoints

| Path (on `https://studio.youtube.com`) | Use | Status | Sources |
|---|---|---|---|
| `GET /` | the page's `ytcfg`: `INNERTUBE_API_KEY`, `CHANNEL_ID`, `INNERTUBE_CONTEXT_CLIENT_VERSION`, `DELEGATED_SESSION_ID`, `SESSION_INDEX` (read by regex, no JavaScript is run) | verified in sources, live UNVERIFIED | [1] `getConfig`, [3] |
| `POST /youtubei/v1/creator/get_creator_channels` | channel title, subscribers, video count; body `channelIds`, `mask{channelId,title,metric{all}}` | verified in sources, live UNVERIFIED | [3] |
| `POST /youtubei/v1/creator/list_creator_videos` | uploads: `filter` (channelIdIs + VIDEO_ORIGIN_UPLOAD), `order` VIDEO_ORDER_DISPLAY_TIME_DESC, `pageSize`, `mask` (videoId, title, contentType, lengthSeconds, timePublishedSeconds, publicMetrics); `publicMetrics.externalViewCount/likeCount/commentCount` | verified in sources, live UNVERIFIED | [1] `getVideos`, [2] `listVideos`, [3] |
| `POST /youtubei/v1/analytics_data/get_screen` | analytics: `screenConfig{entity{videoId or channelId}, timePeriod, currency, timeZoneOffsetSecs}`, `desktopState{tabId}`, `fetchingType` | path and body verified in sources, live UNVERIFIED | [4], [5] |

Request details shared by the POSTs: `?alt=json&key=<INNERTUBE_API_KEY>` and a body `context` with
`client{clientName: 62, clientVersion}`, `user.delegationContext{externalChannelId, roleType OWNER}` and
`onBehalfOfUser` when the page has a delegated session id ([1], [3]); headers `Authorization: SAPISIDHASH …`,
`X-Origin`, `X-Goog-AuthUser`, `X-YouTube-Client-Name`/`-Version` ([1], [2], [3]).

What `get_screen` returns, and what is still UNVERIFIED:

| Item | Status |
|---|---|
| `cards[].keyMetricCardData.keyMetricTabs[].primaryContent{metric, total}` | verified in sources: [4] reads impressions as the REACH tab's first total; [5] reads `metric == "VIEWS"` on OVERVIEW |
| Tabs `ANALYTICS_TAB_ID_OVERVIEW`, `ANALYTICS_TAB_ID_REACH` | verified in sources ([5], [4]) |
| `timePeriodType: ANALYTICS_TIME_PERIOD_TYPE_LIFETIME` | verified in source [5] |
| Tabs `ANALYTICS_TAB_ID_ENGAGEMENT`, `ANALYTICS_TAB_ID_AUDIENCE` | UNVERIFIED |
| Custom range `ANALYTICS_TIME_PERIOD_TYPE_CUSTOM` + `startDate`/`endDate` `{year, month, day}` | UNVERIFIED (one function, `time_period`) |
| Metric names (`VIDEO_THUMBNAIL_IMPRESSIONS`, `…_VTR`, `EXTERNAL_VIEWS`, `UNIQUE_VIEWERS`, `AVERAGE_WATCH_TIME`, `AVERAGE_PERCENTAGE_WATCHED`, `SUBSCRIBERS_NET_CHANGE`, `EXTERNAL_WATCH_TIME`, in `FIELDS`) and their units | UNVERIFIED except `VIEWS` |
| Traffic-source rows, retention curve, real-time series (found by key words `trafficSource`, `retention`, `realtime` and bounded numeric shapes) | UNVERIFIED |

Endpoints the sources also show and this MCP refuses: `video_manager/metadata_update`, `video/delete`,
`upload/createvideo`, `video_editor/edit_video`, `playlist/create`, `creator/list_creator_received_claims`,
`creator/get_creator_videos` (not needed), `creator/get_creator_endscreens`.

Sources (read as text on 2026-10-27; none installed or run; none of their cookies or keys reused):

1. adasq/youtube-studio, `src/youtube-studio-api.js` at `05c6a2652ce4a2db0c243cc1a0aa5742c57f960c`:
   https://github.com/adasq/youtube-studio/blob/master/src/youtube-studio-api.js
2. yusufusta/ytstudio, `ytstudio/__init__.py` at `1abbd642ccc064c06f15a461a117f3216a0f89c6`:
   https://github.com/yusufusta/ytstudio/blob/master/ytstudio/__init__.py
3. leeguooooo/iphone-use, `PhoneSiteCatalog.json` (studio.youtube.com adapter) at
   `b374f0d7dcfa5e810a95cd874d764cf1c308cd95`:
   https://github.com/leeguooooo/iphone-use/blob/b374f0d7dcfa5e810a95cd874d764cf1c308cd95/apps/ios/IPhoneUseRemote/Resources/PhoneSiteCatalog.json
4. Benjamin-Loison/YouTube-operational-API, `videos.php` (`impressions`) at
   `70a31fb1bc193b7dbac2bdeee71ad3413ca76541`:
   https://github.com/Benjamin-Loison/YouTube-operational-API/blob/70a31fb1bc193b7dbac2bdeee71ad3413ca76541/videos.php
5. Rehike/Rehike, `modules/Rehike/Helper/ChannelUtils.php` (`getOwnerData`) at
   `4626d0ed23d8486d298bd685c6169cad6115ace7`:
   https://github.com/Rehike/Rehike/blob/4626d0ed23d8486d298bd685c6169cad6115ace7/modules/Rehike/Helper/ChannelUtils.php
6. Official MCP Python SDK: https://py.sdk.modelcontextprotocol.io/

The analytics path is `analytics_data/get_screen` in both sources; the `yta_web/...` names seen in some write-ups were
not found in any public source and are not used.

## Live check (once the variable is set; nothing here was run live)

Run in a new session, one step at a time, and stop at the first error. Do not paste results into the repository.

1. `studio_status(verify=false)`: `cookies_parsed` and `sapisid_present` true (no request).
2. `studio_status()`: `session_verified` true and the channel id is HeroVerse's. Errors: `STUDIO_SIGNED_OUT_REDIRECT`
   or `STUDIO_CONFIG_NOT_FOUND` = re-export; `STUDIO_REQUEST_REFUSED` = the channel body changed.
3. `studio_retention(<a published video id>)` (lifetime, 1 request): check `card_types` and `retention`.
4. `studio_video_metrics(<same id>, start="lifetime")`: compare impressions, CTR, views and AVD with the video's
   Studio analytics page (lifetime). This confirms metric names, units and the ENGAGEMENT/AUDIENCE tabs.
5. `studio_video_metrics(<same id>, "<a 28-day range>", "...")`: compare with Studio for that custom range. If
   Studio's numbers differ (or the call is refused), the custom-range shape is wrong: in the browser, open DevTools →
   Network on that analytics page, find the `get_screen` request and copy **only the request payload's `timePeriod`**
   (never headers or cookies), then fix `time_period()` and its test in a PR.
6. `studio_channel_metrics(limit=5, per_video=1)`: check the ranked table and `traffic_sources`.
7. Record the result in this README (which items moved from UNVERIFIED to verified, the date) without any numbers
   from the account; correct `FIELDS`, units and parsers in the same PR with a synthetic fixture.

## Running and tests

`.mcp.json` registers `uv run --script migration/integrations/studio/server.py` (official MCP Python SDK 2.3.0) as
`heroverse-studio`, like `heroverse-pavo`. It is a private stdio server, not a remote endpoint.

- `python3 -I -B migration/integrations/studio/test_client.py`: allowlist refusals (each forbidden word, also after
  being added to the table; other hosts; raw paths; methods; queries; body keys), no refused request reaches the
  network or the budget, every request of every tool is on the allowlist, no generic request surface, cookie absent
  from every error, log, stdout/stderr and result, SAPISIDHASH value, cookie formats and domain filter, parsing of
  synthetic responses, input validation, pace and budget, HTTP error codes. In `pr-checks.yml`.
- `test_stdio.py`: the real MCP subprocess (four read-only tools, local refusals, no network). In `studio-mcp.yml`.
