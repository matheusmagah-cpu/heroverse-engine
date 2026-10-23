# HeroVerse daily report — 2026-10-23 10:29 UTC (day 6 of 14, max 30)

## YPP progress
Sources: [official] YouTube Data API count; [own] our calculation from YouTube Analytics rows (an estimate of
the YPP counter, which only YouTube Studio shows and which can differ); [plan] our arithmetic toward day 14.

- Subscribers [official]: **272 / 1,000** — [plan] 80.9/day to reach it by day 14
- Public long-form watch hours, last 365 d [own]: **6.7 / 4,000** — [plan] 443.7/day
- Public Shorts views, last 90 d [own]: 541 / 10,000,000 (the alternative YPP path)
- For contrast, NOT the YPP counters: all-content watch hours 365 d incl. Shorts and private/removed videos [own] 86.6 h; lifetime views of public Shorts [official] 3,169
- Classification of long vs Shorts: duration <= 180 s (Analytics content type unavailable)
- Public videos [official]: 32; total channel views 3,335

## Alerts
- ⚠ pilot-008 review FAIL: read out/review.json
- ⚠ pilot-009 QA FAIL
- ⚠ pilot-011 QA FAIL

## Pipeline (script runway 3.0 days)
| pilot | publishes | rendered | QA | review | uploaded | public observed | title |
|---|---|---|---|---|---|---|---|
| pilot-008 | 2026-10-25 00:00 UTC | yes | PASS | FAIL | no | UNKNOWN | Night Prayer with Psalm 23 | The Lord Is My Shepherd, Rest in His Care |
| pilot-009 | 2026-10-24 10:00 UTC | yes | FAIL | - | no | UNKNOWN | Powerful Morning Prayer | Put On the Whole Armor of God Today (Ephesians 6) |
| pilot-010 | 2026-10-24 00:00 UTC | yes | PASS | ERROR | no | UNKNOWN | Night Prayer for Anxiety | Cast Your Cares on God and Sleep in Peace |
| pilot-011 | 2026-10-25 10:00 UTC | yes | FAIL | - | no | UNKNOWN | Morning Prayer for Strength | They That Wait Upon the LORD (Isaiah 40:31) |
| pilot-013 | 2026-10-26 00:00 UTC | no | - | - | no | UNKNOWN | Night Prayer for Forgiveness | Let God's Mercy Wash Away Today Before You Sleep |
| pilot-014 | 2026-10-26 10:00 UTC | no | - | - | no | UNKNOWN | Morning Prayer for Your Family | Lord, Build Our Home and Keep Us Today (Psalm 127) |

## Latest public videos
| published | views | watch h | avg view % | subs gained | title |
|---|---|---|---|---|---|
| 2026-10-21T10:00 | 1 | 0.0 | 0.8 | 0 | Morning Prayer with Bible Verses for Peace | Start Your Day in God's W |
| 2026-10-21T00:00 | 6 | 0.0 | 1.6 | 0 | Night Prayer for Healing | Rest Your Body and Heart in God's Care |
| 2026-10-20T21:31 | 20 | 0.1 | 99.5 | 1 | A Prayer for Peace in Your Relationships #shorts |
| 2026-10-20T10:00 | 1 | 0.0 | 0 | 0 | Morning Prayer for Protection | Psalm 91 Over You and Your Family |
| 2026-10-20T00:30 | 18 | 1.7 | 25.6 | 0 | Night Prayer of Thanksgiving | His Mercies Are New, Rest in His Faithf |
| 2026-10-19T20:17 | 199 | 1.5 | 188.8 | 4 | Rest for the Part of You Still Awake #shorts |
| 2026-10-19T20:16 | 18 | 1.6 | 21.9 | 0 | Night Prayer Before Sleep | Give God Your Worries, Rest in His Peace |
| 2026-10-18T14:00 | 299 | 4.6 | 257.3 | 5 | The Ultimate Morning Prayer for Peace #shorts |
| 2026-10-18T10:00 | 15 | 0.1 | 2.0 | 0 | Morning Prayer | God Has Already Gone Ahead of You Today |
| 2026-10-10T18:45 | 9 | 3.1 | 11.4 | 0 | Rest Is Not Giving Up | A Christian Reflection + Quiet Piano for Praye |
| 2026-09-04T18:45 | 27 | 0.2 | 17.6 | 0 | The 24-Hour Test: What To Do After You Pray |
| 2026-07-19T19:39 | 22 | 0.1 | 28.1 | 0 | The 2026 Warning: What They DON’T Want You to Know. ⚠️📖 #prophecy #chr |

## Public videos with fear-bait/prophecy-style titles (5; 2.9 of the channel's watch hours)
- The 2026 Warning: What They DON’T Want You to Know. ⚠️📖 #prophecy #christianmoti — 0.1 h, 22 views
- Why God Chose YOU For This Exact Moment In History ⚔️ (Don’t Ignore This) #motiv — 1.2 h, 369 views
- The 2026 Prophecy: What They Are Hiding From You (Watch Before It’s Too Late) #f — 0.2 h, 42 views
- The 2026 Prophecy: What They Are Hiding From You (Watch Before It’s Too Late) — 0.1 h, 12 views
- God is WARNIG you: The Law of Divine Return is HERE! ⚔️🛡️ #faith #god #movie #th — 1.3 h, 23 views

Market and production directives of the day: `migration/evidence/daily-intel/` (latest file).

## Scheduler health (heartbeat.yml; GitHub drops crons, the heartbeat catches up)
- ⚠ heartbeat.yml: no run for 2:35:32
| workflow | last run (UTC) | result |
|---|---|---|
| nightly-images.yml | 2026-10-20T14:17 | success |
| market-panel.yml | 2026-10-23T07:54 | success |
| reconcile.yml | 2026-10-22T22:43 | success |
| publish-shorts.yml | 2026-10-20T21:29 | success |
| goal-report.yml | 2026-10-23T10:29 | in_progress |
| channel-privacy.yml | 2026-10-22T10:35 | success |
| heartbeat.yml | 2026-10-23T07:54 | success ⚠ |
| runner | 2026-10-23T10:08 | in_progress |

## Actions minutes (private engine; budget 7000 min / 30 days)
- ⚠ 30-day projection 13423 min ≥ 90 % of the 7000 min budget
- last 24 h 180 · last 7 d 3132 · last 30 d 3307 · 30-day projection 13423
| workflow (30 d) | minutes | runs |
|---|---|---|
| HeroVerse approval (automatic gates before publication) | 614 | 53 |
| HeroVerse pilot render (figure + backgrounds + captions) and QA | 573 | 8 |
| HeroVerse PR checks (unit tests + pilot acceptance) | 473 | 181 |
| HeroVerse Shorts (private): Gemini selection, own edit per Short, watched review | 353 | 33 |
| HeroVerse full-structure mining (whole videos of winning channels) | 212 | 7 |
| HeroVerse pilot image generation (open-weight model, CPU) | 129 | 3 |
| HeroVerse pilot render and QA | 121 | 4 |
| HeroVerse images on Cloudflare Workers AI (free allocation) | 119 | 33 |

## Content runway (next 4 days; the engine must never run out of videos)
- ⚠ 2026-10-24 00:00 UTC (13:29:46 left): pilot-010 is at 'rendered'
- ⚠ 2026-10-24 10:00 UTC (23:29:46 left): pilot-009 is at 'rendered'
| slot (UTC) | pilot | stage |
|---|---|---|
| 2026-10-24T00:00Z | pilot-010 | rendered ⚠ |
| 2026-10-24T10:00Z | pilot-009 | rendered ⚠ |
| 2026-10-25T00:00Z | pilot-008 | rendered |
| 2026-10-25T10:00Z | pilot-011 | rendered |
| 2026-10-26T00:00Z | pilot-013 | script |
| 2026-10-26T10:00Z | pilot-014 | script |
| 2026-10-27T00:00Z | — | missing |
| 2026-10-27T10:00Z | — | missing |
