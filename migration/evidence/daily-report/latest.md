# HeroVerse daily report — 2026-10-22 10:36 UTC (day 5 of 14, max 30)

## YPP progress
Sources: [official] YouTube Data API count; [own] our calculation from YouTube Analytics rows (an estimate of
the YPP counter, which only YouTube Studio shows and which can differ); [plan] our arithmetic toward day 14.

- Subscribers [official]: **272 / 1,000** — [plan] 72.8/day to reach it by day 14
- Public long-form watch hours, last 365 d [own]: **5.5 / 4,000** — [plan] 399.4/day
- Public Shorts views, last 90 d [own]: 444 / 10,000,000 (the alternative YPP path)
- For contrast, NOT the YPP counters: all-content watch hours 365 d incl. Shorts and private/removed videos [own] 84.6 h; lifetime views of public Shorts [official] 3,168
- Classification of long vs Shorts: duration <= 180 s (Analytics content type unavailable)
- Public videos [official]: 32; total channel views 3,305

## Alerts
- ⚠ SCRIPT RUNWAY 1.0 days (< 2): write the next pilots now
- ⚠ pilot-008 review FAIL: read out/review.json
- ⚠ pilot-009 QA FAIL
- ⚠ pilot-011 QA FAIL

## Pipeline (script runway 1.0 days)
| pilot | publishes | rendered | QA | review | uploaded | public observed | title |
|---|---|---|---|---|---|---|---|
| pilot-006 | 2026-10-21 00:00 UTC | yes | PASS | PASS | yes | yes | Night Prayer for Healing | Rest Your Body and Heart in God's Care |
| pilot-007 | 2026-10-21 10:00 UTC | yes | PASS | PASS | yes | yes | Morning Prayer with Bible Verses for Peace | Start Your Day in God's Word |
| pilot-008 | 2026-10-22 00:00 UTC | yes | PASS | FAIL | no | UNKNOWN | Night Prayer with Psalm 23 | The Lord Is My Shepherd, Rest in His Care |
| pilot-009 | 2026-10-22 10:00 UTC | yes | FAIL | - | no | UNKNOWN | Powerful Morning Prayer | Put On the Whole Armor of God Today (Ephesians 6) |
| pilot-010 | 2026-10-23 00:00 UTC | yes | PASS | ERROR | no | UNKNOWN | Night Prayer for Anxiety | Cast Your Cares on God and Sleep in Peace |
| pilot-011 | 2026-10-23 10:00 UTC | yes | FAIL | - | no | UNKNOWN | Morning Prayer for Strength | They That Wait Upon the LORD (Isaiah 40:31) |

## Latest public videos
| published | views | watch h | avg view % | subs gained | title |
|---|---|---|---|---|---|
| 2026-10-21T10:00 | 21 | - | - | - | Morning Prayer with Bible Verses for Peace | Start Your Day in God's W |
| 2026-10-21T00:00 | 9 | - | - | - | Night Prayer for Healing | Rest Your Body and Heart in God's Care |
| 2026-10-20T21:31 | 24 | - | - | - | A Prayer for Peace in Your Relationships #shorts |
| 2026-10-20T10:00 | 5 | - | - | - | Morning Prayer for Protection | Psalm 91 Over You and Your Family |
| 2026-10-20T00:30 | 10 | 1.7 | 33.0 | 0 | Night Prayer of Thanksgiving | His Mercies Are New, Rest in His Faithf |
| 2026-10-19T20:17 | 130 | 0.8 | 175.4 | 2 | Rest for the Part of You Still Awake #shorts |
| 2026-10-19T20:16 | 2 | 0.4 | 43.4 | 0 | Night Prayer Before Sleep | Give God Your Worries, Rest in His Peace |
| 2026-10-18T14:00 | 292 | 4.6 | 267.1 | 5 | The Ultimate Morning Prayer for Peace #shorts |
| 2026-10-18T10:00 | 12 | 0.1 | 2.2 | 0 | Morning Prayer | God Has Already Gone Ahead of You Today |
| 2026-10-10T18:45 | 9 | 3.1 | 11.4 | 0 | Rest Is Not Giving Up | A Christian Reflection + Quiet Piano for Praye |
| 2026-09-04T18:45 | 27 | 0.2 | 17.6 | 0 | The 24-Hour Test: What To Do After You Pray |
| 2026-07-19T19:39 | 21 | 0.1 | 28.1 | 0 | The 2026 Warning: What They DON’T Want You to Know. ⚠️📖 #prophecy #chr |

## Public videos with fear-bait/prophecy-style titles (5; 2.9 of the channel's watch hours)
- The 2026 Warning: What They DON’T Want You to Know. ⚠️📖 #prophecy #christianmoti — 0.1 h, 21 views
- Why God Chose YOU For This Exact Moment In History ⚔️ (Don’t Ignore This) #motiv — 1.2 h, 368 views
- The 2026 Prophecy: What They Are Hiding From You (Watch Before It’s Too Late) #f — 0.2 h, 41 views
- The 2026 Prophecy: What They Are Hiding From You (Watch Before It’s Too Late) — 0.1 h, 12 views
- God is WARNIG you: The Law of Divine Return is HERE! ⚔️🛡️ #faith #god #movie #th — 1.3 h, 23 views

Market and production directives of the day: `migration/evidence/daily-intel/` (latest file).

## Scheduler health (heartbeat.yml; GitHub drops crons, the heartbeat catches up)
- ⚠ runner: no run for 3:06:21
| workflow | last run (UTC) | result |
|---|---|---|
| nightly-images.yml | 2026-10-20T14:17 | success |
| market-panel.yml | 2026-10-22T10:35 | in_progress |
| reconcile.yml | 2026-10-22T10:35 | success |
| publish-shorts.yml | 2026-10-20T21:29 | success |
| goal-report.yml | 2026-10-22T10:35 | in_progress |
| channel-privacy.yml | 2026-10-22T10:35 | pending |
| heartbeat.yml | 2026-10-22T10:35 | success |
| runner | 2026-10-22T07:29 | success ⚠ |

## Actions minutes (private engine; budget 7000 min / 30 days)
- ⚠ 30-day projection 12874 min ≥ 90 % of the 7000 min budget
- last 24 h 83 · last 7 d 3004 · last 30 d 3129 · 30-day projection 12874
| workflow (30 d) | minutes | runs |
|---|---|---|
| HeroVerse approval (automatic gates before publication) | 573 | 50 |
| HeroVerse pilot render (figure + backgrounds + captions) and QA | 573 | 8 |
| HeroVerse PR checks (unit tests + pilot acceptance) | 398 | 165 |
| HeroVerse Shorts (private): Gemini selection, own edit per Short, watched review | 353 | 33 |
| HeroVerse full-structure mining (whole videos of winning channels) | 212 | 7 |
| HeroVerse pilot image generation (open-weight model, CPU) | 129 | 3 |
| HeroVerse pilot render and QA | 121 | 4 |
| HeroVerse acquire reference windows | 101 | 9 |

## Content runway (next 4 days; the engine must never run out of videos)
- ⚠ 2026-10-23 00:00 UTC (13:23:25 left): pilot-010 is at 'rendered'
- ⚠ 2026-10-23 10:00 UTC (23:23:25 left): pilot-011 is at 'rendered'
- ⚠ 2026-10-24 00:00 UTC (1 day, 13:23:25 left): NO PILOT is at 'missing'
- ⚠ 2026-10-24 10:00 UTC (1 day, 23:23:25 left): NO PILOT is at 'missing'
- ⚠ 2026-10-25 00:00 UTC (2 days, 13:23:25 left): NO PILOT is at 'missing'
- ⚠ 2026-10-25 10:00 UTC (2 days, 23:23:25 left): NO PILOT is at 'missing'
| slot (UTC) | pilot | stage |
|---|---|---|
| 2026-10-23T00:00Z | pilot-010 | rendered ⚠ |
| 2026-10-23T10:00Z | pilot-011 | rendered ⚠ |
| 2026-10-24T00:00Z | — | missing ⚠ |
| 2026-10-24T10:00Z | — | missing ⚠ |
| 2026-10-25T00:00Z | — | missing ⚠ |
| 2026-10-25T10:00Z | — | missing ⚠ |
| 2026-10-26T00:00Z | — | missing |
| 2026-10-26T10:00Z | — | missing |
