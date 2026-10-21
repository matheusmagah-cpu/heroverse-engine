# HeroVerse daily report — 2026-10-21 12:19 UTC (day 4 of 14, max 30)

## YPP progress
Sources: [official] YouTube Data API count; [own] our calculation from YouTube Analytics rows (an estimate of
the YPP counter, which only YouTube Studio shows and which can differ); [plan] our arithmetic toward day 14.

- Subscribers [official]: **272 / 1,000** — [plan] 66.2/day to reach it by day 14
- Public long-form watch hours, last 365 d [own]: **3.3 / 4,000** — [plan] 363.3/day
- Public Shorts views, last 90 d [own]: 282 / 10,000,000 (the alternative YPP path)
- For contrast, NOT the YPP counters: all-content watch hours 365 d incl. Shorts and private/removed videos [own] 81.2 h; lifetime views of public Shorts [official] 3,155
- Classification of long vs Shorts: duration <= 180 s (Analytics content type unavailable)
- Public videos [official]: 32; total channel views 2,981

## Alerts
- ⚠ SCRIPT RUNWAY 1.9 days (< 2): write the next pilots now
- ⚠ pilot-008 review FAIL: read out/review.json
- ⚠ pilot-009 QA FAIL

## Pipeline (script runway 1.9 days)
| pilot | publishes | rendered | QA | review | uploaded | public observed | title |
|---|---|---|---|---|---|---|---|
| pilot-004 | 2026-10-20 00:00 UTC | yes | PASS | PASS | yes | yes | Night Prayer Before Sleep | Give God Your Worries, Rest in His Peace |
| pilot-005 | 2026-10-20 10:00 UTC | yes | PASS | PASS | yes | yes | Morning Prayer for Protection | Psalm 91 Over You and Your Family |
| pilot-006 | 2026-10-21 00:00 UTC | yes | PASS | PASS | yes | yes | Night Prayer for Healing | Rest Your Body and Heart in God's Care |
| pilot-007 | 2026-10-21 10:00 UTC | yes | PASS | PASS | yes | yes | Morning Prayer with Bible Verses for Peace | Start Your Day in God's Word |
| pilot-008 | 2026-10-22 00:00 UTC | yes | PASS | FAIL | no | UNKNOWN | Night Prayer with Psalm 23 | The Lord Is My Shepherd, Rest in His Care |
| pilot-009 | 2026-10-22 10:00 UTC | yes | FAIL | - | no | UNKNOWN | Powerful Morning Prayer | Put On the Whole Armor of God Today (Ephesians 6) |
| pilot-010 | 2026-10-23 00:00 UTC | yes | PASS | ERROR | no | UNKNOWN | Night Prayer for Anxiety | Cast Your Cares on God and Sleep in Peace |
| pilot-011 | 2026-10-23 10:00 UTC | no | - | - | no | UNKNOWN | Morning Prayer for Strength | They That Wait Upon the LORD (Isaiah 40:31) |
| pilot-012 | 2026-10-20 00:30 UTC | yes | PASS | PASS | yes | yes | Night Prayer of Thanksgiving | His Mercies Are New, Rest in His Faithfulness |

## Latest public videos
| published | views | watch h | avg view % | subs gained | title |
|---|---|---|---|---|---|
| 2026-10-21T10:00 | 2 | - | - | - | Morning Prayer with Bible Verses for Peace | Start Your Day in God's W |
| 2026-10-21T00:00 | 6 | - | - | - | Night Prayer for Healing | Rest Your Body and Heart in God's Care |
| 2026-10-20T21:31 | 22 | - | - | - | A Prayer for Peace in Your Relationships #shorts |
| 2026-10-20T10:00 | 1 | - | - | - | Morning Prayer for Protection | Psalm 91 Over You and Your Family |
| 2026-10-20T00:30 | 16 | - | - | - | Night Prayer of Thanksgiving | His Mercies Are New, Rest in His Faithf |
| 2026-10-19T20:17 | 194 | - | - | - | Rest for the Part of You Still Awake #shorts |
| 2026-10-19T20:16 | 17 | - | - | - | Night Prayer Before Sleep | Give God Your Worries, Rest in His Peace |
| 2026-10-18T14:00 | 260 | 4.2 | 270.1 | 5 | The Ultimate Morning Prayer for Peace #shorts |
| 2026-10-18T10:00 | 5 | 0.0 | 2.5 | 0 | Morning Prayer | God Has Already Gone Ahead of You Today |
| 2026-10-10T18:45 | 9 | 3.1 | 11.4 | 0 | Rest Is Not Giving Up | A Christian Reflection + Quiet Piano for Praye |
| 2026-09-04T18:45 | 27 | 0.2 | 17.6 | 0 | The 24-Hour Test: What To Do After You Pray |
| 2026-07-19T19:39 | 20 | 0.1 | 28.1 | 0 | The 2026 Warning: What They DON’T Want You to Know. ⚠️📖 #prophecy #chr |

## Public videos with fear-bait/prophecy-style titles (5; 2.9 of the channel's watch hours)
- The 2026 Warning: What They DON’T Want You to Know. ⚠️📖 #prophecy #christianmoti — 0.1 h, 20 views
- Why God Chose YOU For This Exact Moment In History ⚔️ (Don’t Ignore This) #motiv — 1.2 h, 367 views
- The 2026 Prophecy: What They Are Hiding From You (Watch Before It’s Too Late) #f — 0.2 h, 40 views
- The 2026 Prophecy: What They Are Hiding From You (Watch Before It’s Too Late) — 0.1 h, 12 views
- God is WARNIG you: The Law of Divine Return is HERE! ⚔️🛡️ #faith #god #movie #th — 1.3 h, 23 views

Market and production directives of the day: `migration/evidence/daily-intel/` (latest file).

## Scheduler health (heartbeat.yml; GitHub drops crons, the heartbeat catches up)
- all scheduled work ran
| workflow | last run (UTC) | result |
|---|---|---|
| nightly-images.yml | 2026-10-20T14:17 | success |
| market-panel.yml | 2026-10-21T12:18 | in_progress |
| reconcile.yml | 2026-10-21T12:18 | success |
| publish-shorts.yml | 2026-10-20T21:29 | success |
| goal-report.yml | 2026-10-21T12:18 | in_progress |
| channel-privacy.yml | 2026-10-21T12:18 | pending |
| heartbeat.yml | 2026-10-21T12:18 | failure |
| runner | 2026-10-21T11:40 | in_progress |

## Actions minutes (private engine; budget 7000 min / 30 days)
- ⚠ 30-day projection 12793 min ≥ 90 % of the 7000 min budget
- last 24 h 333 · last 7 d 2985 · last 30 d 3061 · 30-day projection 12793
| workflow (30 d) | minutes | runs |
|---|---|---|
| HeroVerse pilot render (figure + backgrounds + captions) and QA | 573 | 8 |
| HeroVerse approval (automatic gates before publication) | 545 | 46 |
| HeroVerse PR checks (unit tests + pilot acceptance) | 398 | 165 |
| HeroVerse Shorts (private): Gemini selection, own edit per Short, watched review | 334 | 32 |
| HeroVerse full-structure mining (whole videos of winning channels) | 212 | 7 |
| HeroVerse pilot image generation (open-weight model, CPU) | 129 | 3 |
| HeroVerse pilot render and QA | 121 | 4 |
| HeroVerse acquire reference windows | 101 | 9 |

## Content runway (next 4 days; the engine must never run out of videos)
- ⚠ 2026-10-22 00:00 UTC (11:40:18 left): pilot-008 is at 'rendered'
- ⚠ 2026-10-22 10:00 UTC (21:40:18 left): pilot-009 is at 'rendered'
- ⚠ 2026-10-24 00:00 UTC (2 days, 11:40:18 left): NO PILOT is at 'missing'
- ⚠ 2026-10-24 10:00 UTC (2 days, 21:40:18 left): NO PILOT is at 'missing'
| slot (UTC) | pilot | stage |
|---|---|---|
| 2026-10-22T00:00Z | pilot-008 | rendered ⚠ |
| 2026-10-22T10:00Z | pilot-009 | rendered ⚠ |
| 2026-10-23T00:00Z | pilot-010 | rendered |
| 2026-10-23T10:00Z | pilot-011 | script |
| 2026-10-24T00:00Z | — | missing ⚠ |
| 2026-10-24T10:00Z | — | missing ⚠ |
| 2026-10-25T00:00Z | — | missing |
| 2026-10-25T10:00Z | — | missing |
