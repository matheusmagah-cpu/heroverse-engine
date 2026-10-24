# Live intelligence: the daily loop (owner, 2026-10-24: "a inteligência viva precisa começar a trabalhar")

Runs once a day from the hourly clock (first run after 16:00 UTC), at most 20 vidIQ credits, every spend in the ledger.

1. **Measure our videos.** `vidiq_channel_analytics` by video (last 14 d) and by traffic source; `vidiq_get_videos_by_ids`
   for anything published in the last 48 h (Analytics lags about 48 h).
2. **Verdict at 48 h and 7 d.** Each video is good, weak/bad or neutral against the series median at the same age;
   under 48 h it stays inconclusive. Record it in `evidence/learning/<YYYYMMDD>.json` (same schema as 20261024).
3. **Turn it into one change.** Name the single change the next episodes make (hook, title pattern, length, visual,
   end card, slot), the stage it touches and how it will be measured. Write it into `production/bible/SERIES.md` or
   `PROMPT_GUIDE.md` so production uses it; the next day's run checks whether it worked.
4. **Tell the owner only when there is a verdict or a change.** Two lines: what the numbers show, what changes.
