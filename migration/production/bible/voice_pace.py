"""Kokoro pace by speaker, in words a second: the one table plan_check (Shorts) and long_plan_check (longs) time a
line with. Measured locally with the hash-pinned Kokoro v1.0 model (pilot_render.py voice, the runtime episode.yml
installs); a line is its sentences from the first word to the last, the pace the words over the seconds of a voice's
lines.

- keeper am_michael 2.874, god am_onyx at 0.9 2.811, adam am_fenrir 3.975, eve af_heart 3.732: the arc-1 long, first
  run (evidence/long/20261026/arc-01-voice.json).
- noah bm_george 2.970 (lines 2.60-3.37): six lines (evidence/long/20261026/noah-scoffer-voice.json; the same run gave
  Adam and Eve the arc-1 second run's 3.798 and 3.566 to the third decimal, so the method is the same). The 8-line probe
  of evidence/voice/20261026/kokoro-pace.json gave 2.868.
- scoffer am_puck 3.55: kokoro-pace.json (its probe and the genesis-08/09 lines, 10 lines); the six lines of
  noah-scoffer-voice.json gave 3.425.
- serpent bm_fable 2.728: kokoro-pace.json's probe.
Where two runs differ the faster is kept (as for Adam and Eve): a line is judged from that pace down to SLOW_RATIO of it,
and a talking line too short for its clip is the costly miss. The Keeper's Short narration measured 2.756 over 82
lines of genesis-07 to 10 (kokoro-pace.json), so plan_check keeps WPS 2.75 for it; 2.874 here is the long's narration.

A pace belongs to its voice (MEASURED_WITH; a test keeps it equal to characters.json): give a speaker another voice and
measure it again. A talking speaker with no pace here is refused at plan time (VOICE_PACE_UNMEASURED)."""

VOICE_PACE = {"keeper": 2.874, "god": 2.811, "adam": 3.975, "eve": 3.732, "noah": 2.970, "scoffer": 3.55,
              "serpent": 2.728}
MEASURED_WITH = {"keeper": ("am_michael", 1.0), "god": ("am_onyx", 0.9), "adam": ("am_fenrir", 1.0),
                 "eve": ("af_heart", 1.0), "noah": ("bm_george", 1.0), "scoffer": ("am_puck", 1.0),
                 "serpent": ("bm_fable", 1.0)}
