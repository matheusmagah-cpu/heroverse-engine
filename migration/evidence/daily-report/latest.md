# HeroVerse daily report — 2026-10-24 11:33 UTC (day 7 of 14, max 30)

## YPP progress
Sources: [official] YouTube Data API count; [own] our calculation from YouTube Analytics rows (an estimate of
the YPP counter, which only YouTube Studio shows and which can differ); [plan] our arithmetic toward day 14.

- Subscribers [official]: **274 / 1,000** — [plan] 90.8/day to reach it by day 14
- Public long-form watch hours, last 365 d [own]: **9.3 / 4,000** — [plan] 498.8/day
- Public Shorts views, last 90 d [own]: 559 / 10,000,000 (the alternative YPP path)
- For contrast, NOT the YPP counters: all-content watch hours 365 d incl. Shorts and private/removed videos [own] 89.3 h; lifetime views of public Shorts [official] 3,169
- Classification of long vs Shorts: duration <= 180 s (Analytics content type unavailable)
- Public videos [official]: 33; total channel views 3,366

## Alerts
- ⚠ pilot-008 review FAIL: read out/review.json
- ⚠ pilot-011 QA FAIL

## Pipeline (script runway 2.9 days)
| pilot | publishes | rendered | QA | review | uploaded | public observed | title |
|---|---|---|---|---|---|---|---|
| pilot-008 | 2026-10-25 00:00 UTC | yes | PASS | FAIL | no | UNKNOWN | Before You Sleep, Let Your Shepherd Carry Today 🌙 | Night Prayer with Psalm 23 |
| pilot-009 | 2026-10-27 10:00 UTC | yes | PASS | PASS | no | UNKNOWN | Before You Walk Out the Door, Put On God's Armor 🙏 | Morning Prayer (Ephesians 6) |
| pilot-010 | 2026-10-24 00:00 UTC | yes | PASS | PASS | yes | yes | Before You Sleep, Give God the Worry You Can't Fix 🌙 | Night Prayer for Anxiety |
| pilot-011 | 2026-10-25 10:00 UTC | yes | FAIL | - | no | UNKNOWN | When You Wake Up Tired, Wait on the Lord 🌅 | Morning Prayer for Strength (Isaiah 40:31) |
| pilot-013 | 2026-10-26 00:00 UTC | no | - | - | no | UNKNOWN | Before You Sleep, Let God's Mercy Wash Today Away 🌙 | Night Prayer for Forgiveness |
| pilot-014 | 2026-10-26 10:00 UTC | no | - | - | no | UNKNOWN | Before Your Family's Day Begins, Cover Them in Prayer 🙏 | Morning Prayer for Your Family |

## Latest public videos
| published | views | watch h | avg view % | subs gained | title |
|---|---|---|---|---|---|
| 2026-10-24T00:00 | 6 | - | - | - | Before You Sleep, Give God the Worry You Can't Fix 🌙 | Night Prayer fo |
| 2026-10-21T10:00 | 21 | 2.2 | 26.4 | 0 | Morning Prayer with Bible Verses for Peace | Start Your Day in God's W |
| 2026-10-21T00:00 | 9 | 0.0 | 1.4 | 0 | Night Prayer for Healing | Rest Your Body and Heart in God's Care |
| 2026-10-20T21:31 | 25 | 0.1 | 94.9 | 1 | A Prayer for Peace in Your Relationships #shorts |
| 2026-10-20T10:00 | 4 | 0.0 | 0.2 | 0 | Morning Prayer for Protection | Psalm 91 Over You and Your Family |
| 2026-10-20T00:30 | 19 | 1.7 | 25.6 | 0 | Night Prayer of Thanksgiving | His Mercies Are New, Rest in His Faithf |
| 2026-10-19T20:17 | 217 | 1.6 | 178.4 | 4 | Rest for the Part of You Still Awake #shorts |
| 2026-10-19T20:16 | 27 | 1.6 | 20.4 | 0 | Night Prayer Before Sleep | Give God Your Worries, Rest in His Peace |
| 2026-10-18T14:00 | 295 | 4.6 | 260.5 | 5 | The Ultimate Morning Prayer for Peace #shorts |
| 2026-10-18T10:00 | 38 | 0.6 | 5.5 | 0 | Morning Prayer | God Has Already Gone Ahead of You Today |
| 2026-10-10T18:45 | 9 | 3.1 | 11.4 | 0 | Rest Is Not Giving Up | A Christian Reflection + Quiet Piano for Praye |
| 2026-09-04T18:45 | 27 | 0.2 | 17.6 | 0 | The 24-Hour Test: What To Do After You Pray |

## Public videos with fear-bait/prophecy-style titles (5; 2.9 of the channel's watch hours)
- The 2026 Warning: What They DON’T Want You to Know. ⚠️📖 #prophecy #christianmoti — 0.1 h, 21 views
- Why God Chose YOU For This Exact Moment In History ⚔️ (Don’t Ignore This) #motiv — 1.2 h, 369 views
- The 2026 Prophecy: What They Are Hiding From You (Watch Before It’s Too Late) #f — 0.2 h, 42 views
- The 2026 Prophecy: What They Are Hiding From You (Watch Before It’s Too Late) — 0.1 h, 12 views
- God is WARNIG you: The Law of Divine Return is HERE! ⚔️🛡️ #faith #god #movie #th — 1.3 h, 23 views

Market and production directives of the day: `migration/evidence/daily-intel/` (latest file).

## Scheduler health (heartbeat.yml; GitHub drops crons, the heartbeat catches up)
- all scheduled work ran
| workflow | last run (UTC) | result |
|---|---|---|
| nightly-images.yml | 2026-10-24T06:24 | success |
| market-panel.yml | 2026-10-24T11:32 | in_progress |
| reconcile.yml | 2026-10-24T11:32 | success |
| publish-shorts.yml | 2026-10-20T21:29 | success |
| goal-report.yml | 2026-10-24T11:32 | in_progress |
| channel-privacy.yml | 2026-10-24T11:32 | pending |
| heartbeat.yml | 2026-10-24T11:32 | success |
| runner | 2026-10-24T09:05 | in_progress |

## Actions minutes (private engine; budget 7000 min / 30 days)
- ⚠ last 24 h used 1637 min (target 233/day)
- ⚠ 30-day projection 19187 min ≥ 90 % of the 7000 min budget
- last 24 h 1637 · last 7 d 4477 · last 30 d 5026 · 30-day projection 19187
| workflow (30 d) | minutes | runs |
|---|---|---|
| HeroVerse pilot render (figure + backgrounds + captions) and QA | 1480 | 18 |
| HeroVerse approval (automatic gates before publication) | 703 | 60 |
| HeroVerse PR checks (unit tests + pilot acceptance) | 632 | 231 |
| HeroVerse Shorts (private): Gemini selection, own edit per Short, watched review | 363 | 34 |
| HeroVerse full-structure mining (whole videos of winning channels) | 212 | 7 |
| HeroVerse footage library (licensed real footage, no paid call) | 185 | 5 |
| HeroVerse images to 1440p+ (AI super-resolution of existing stills, no paid call) | 172 | 6 |
| HeroVerse pilot image generation (open-weight model, CPU) | 129 | 3 |

## Content runway (next 4 days; the engine must never run out of videos)
- ⚠ 2026-10-25 00:00 UTC (12:26:13 left): pilot-008 is at 'rendered'
- ⚠ 2026-10-25 10:00 UTC (22:26:13 left): pilot-011 is at 'rendered'
- ⚠ 2026-10-27 00:00 UTC (2 days, 12:26:13 left): NO PILOT is at 'missing'
| slot (UTC) | pilot | stage |
|---|---|---|
| 2026-10-25T00:00Z | pilot-008 | rendered ⚠ |
| 2026-10-25T10:00Z | pilot-011 | rendered ⚠ |
| 2026-10-26T00:00Z | pilot-013 | script |
| 2026-10-26T10:00Z | pilot-014 | script |
| 2026-10-27T00:00Z | — | missing ⚠ |
| 2026-10-27T10:00Z | pilot-009 | rendered |
| 2026-10-28T00:00Z | — | missing |
| 2026-10-28T10:00Z | — | missing |
