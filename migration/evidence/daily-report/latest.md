# HeroVerse daily report — 2026-10-25 12:17 UTC (day 8 of 14, max 30)

## YPP progress
Sources: [official] YouTube Data API count; [own] our calculation from YouTube Analytics rows (an estimate of
the YPP counter, which only YouTube Studio shows and which can differ); [plan] our arithmetic toward day 14.

- Subscribers [official]: **281 / 1,000** — [plan] 102.7/day to reach it by day 14
- Public long-form watch hours, last 365 d [own]: **13.4 / 4,000** — [plan] 569.5/day
- Public Shorts views, last 90 d [own]: 538 / 10,000,000 (the alternative YPP path)
- For contrast, NOT the YPP counters: all-content watch hours 365 d incl. Shorts and private/removed videos [own] 93.4 h; lifetime views of public Shorts [official] 3,538
- Classification of long vs Shorts: duration <= 180 s (Analytics content type unavailable)
- Public videos [official]: 36; total channel views 3,418

## Alerts
- ⚠ SCRIPT RUNWAY 1.9 days (< 2): write the next pilots now

## Pipeline (script runway 1.9 days)
| pilot | publishes | rendered | QA | review | uploaded | public observed | title |
|---|---|---|---|---|---|---|---|
| pilot-008 | 2026-10-27 00:00 UTC | yes | PASS | AWAITING_REVIEW | no | UNKNOWN | Before You Sleep, Let Your Shepherd Carry Today 🌙 | Night Prayer with Psalm 23 |
| pilot-009 | 2026-10-27 10:00 UTC | yes | PASS | PASS | no | UNKNOWN | Before You Walk Out the Door, Put On God's Armor 🙏 | Morning Prayer (Ephesians 6) |
| pilot-010 | 2026-10-24 00:00 UTC | yes | PASS | PASS | yes | yes | Before You Sleep, Give God the Worry You Can't Fix 🌙 | Night Prayer for Anxiety |
| pilot-011 | 2026-10-25 10:00 UTC | yes | PASS | PASS | yes | yes | When You Wake Up Tired, Wait on the Lord 🌅 | Morning Prayer for Strength (Isaiah 40:31) |
| pilot-013 | 2026-10-26 00:00 UTC | yes | PASS | AWAITING_REVIEW | no | UNKNOWN | Before You Sleep, Let God's Mercy Wash Today Away 🌙 | Night Prayer for Forgiveness |
| pilot-014 | 2026-10-26 10:00 UTC | yes | PASS | PASS | yes | no | Before Your Family's Day Begins, Cover Them in Prayer 🙏 | Morning Prayer for Your Family |

## Latest public videos
| published | views | watch h | avg view % | subs gained | title |
|---|---|---|---|---|---|
| 2026-10-25T10:00 | 0 | - | - | - | When You Wake Up Tired, Wait on the Lord 🌅 | Morning Prayer for Streng |
| 2026-10-24T23:30 | 242 | - | - | - | God Breathed Into the Dust 🌿 | Garden of Eden Bible Story (KJV) #short |
| 2026-10-24T14:44 | 123 | - | - | - | Before There Was Light, God Spoke ✨ | Genesis 1 Bible Story (KJV) #sho |
| 2026-10-24T00:00 | 18 | - | - | - | Before You Sleep, Give God the Worry You Can't Fix 🌙 | Night Prayer fo |
| 2026-10-21T10:00 | 38 | 4.5 | 30.7 | 1 | Morning Prayer with Bible Verses for Peace | Start Your Day in God's W |
| 2026-10-21T00:00 | 8 | 0.5 | 15.8 | 0 | Night Prayer for Healing | Rest Your Body and Heart in God's Care |
| 2026-10-20T21:31 | 25 | 0.1 | 106.3 | 1 | A Prayer for Peace in Your Relationships #shorts |
| 2026-10-20T10:00 | 6 | 0.4 | 20.6 | 0 | Morning Prayer for Protection | Psalm 91 Over You and Your Family |
| 2026-10-20T00:30 | 22 | 2.2 | 38.9 | 0 | Night Prayer of Thanksgiving | His Mercies Are New, Rest in His Faithf |
| 2026-10-19T20:17 | 208 | 1.6 | 189.9 | 4 | Rest for the Part of You Still Awake #shorts |
| 2026-10-19T20:16 | 35 | 1.6 | 21.8 | 0 | Night Prayer Before Sleep | Give God Your Worries, Rest in His Peace |
| 2026-10-18T14:00 | 291 | 4.6 | 262.6 | 5 | The Ultimate Morning Prayer for Peace #shorts |

## Public videos with fear-bait/prophecy-style titles (5; 2.9 of the channel's watch hours)
- The 2026 Warning: What They DON’T Want You to Know. ⚠️📖 #prophecy #christianmoti — 0.1 h, 19 views
- Why God Chose YOU For This Exact Moment In History ⚔️ (Don’t Ignore This) #motiv — 1.2 h, 367 views
- The 2026 Prophecy: What They Are Hiding From You (Watch Before It’s Too Late) #f — 0.2 h, 40 views
- The 2026 Prophecy: What They Are Hiding From You (Watch Before It’s Too Late) — 0.1 h, 12 views
- God is WARNIG you: The Law of Divine Return is HERE! ⚔️🛡️ #faith #god #movie #th — 1.3 h, 23 views

Market and production directives of the day: `migration/evidence/daily-intel/` (latest file).

## Scheduler health (heartbeat.yml; GitHub drops crons, the heartbeat catches up)
- all scheduled work ran
| workflow | last run (UTC) | result |
|---|---|---|
| nightly-images.yml | 2026-10-24T14:50 | success |
| market-panel.yml | 2026-10-25T09:15 | success |
| reconcile.yml | 2026-10-25T12:17 | success |
| publish-shorts.yml | 2026-10-20T21:29 | success |
| goal-report.yml | 2026-10-25T12:17 | in_progress |
| channel-privacy.yml | 2026-10-25T09:15 | success |
| heartbeat.yml | 2026-10-25T12:16 | success |
| runner | 2026-10-25T10:07 | in_progress |

## Actions minutes (private engine; budget 7000 min / 30 days)
- ⚠ last 24 h used 1894 min (target 233/day)
- ⚠ 30-day projection 24146 min ≥ 90 % of the 7000 min budget
- last 24 h 1894 · last 7 d 5634 · last 30 d 7090 · 30-day projection 24146
| workflow (30 d) | minutes | runs |
|---|---|---|
| HeroVerse pilot render (figure + backgrounds + captions) and QA | 2448 | 24 |
| HeroVerse PR checks (unit tests + pilot acceptance) | 812 | 287 |
| HeroVerse approval (automatic gates before publication) | 769 | 72 |
| HeroVerse pilot preview (opening + every footage clip + thumbnail, before the full render) | 458 | 18 |
| HeroVerse Shorts (private): Gemini selection, own edit per Short, watched review | 391 | 37 |
| HeroVerse footage library (licensed real footage, no paid call) | 272 | 6 |
| HeroVerse render smoke (a ~1 minute cut through the whole render path) | 223 | 15 |
| HeroVerse full-structure mining (whole videos of winning channels) | 212 | 7 |

## Content runway (next 4 days; the engine must never run out of videos)
- ⚠ 2026-10-26 00:00 UTC (11:41:50 left): pilot-013 is at 'rendered'
- ⚠ 2026-10-28 00:00 UTC (2 days, 11:41:50 left): NO PILOT is at 'missing'
- ⚠ 2026-10-28 10:00 UTC (2 days, 21:41:50 left): NO PILOT is at 'missing'
| slot (UTC) | pilot | stage |
|---|---|---|
| 2026-10-26T00:00Z | pilot-013 | rendered ⚠ |
| 2026-10-26T10:00Z | pilot-014 | uploaded |
| 2026-10-27T00:00Z | pilot-008 | rendered |
| 2026-10-27T10:00Z | pilot-009 | rendered |
| 2026-10-28T00:00Z | — | missing ⚠ |
| 2026-10-28T10:00Z | — | missing ⚠ |
| 2026-10-29T00:00Z | — | missing |
| 2026-10-29T10:00Z | — | missing |
