"""Kokoro pace by speaker, in words a second: the one table plan_check (Shorts) and long_plan_check (longs) time a
line with. Measured locally with the hash-pinned Kokoro v1.0 model (pilot_render.py voice, the runtime episode.yml
installs); a line is its sentences from the first word to the last, the pace the words over the seconds of a voice's
lines.

- keeper am_michael 2.874, god am_onyx at 0.9 2.811, adam am_fenrir 3.975, eve af_heart 3.732: the arc-1 long, first
  run (evidence/long/20261026/arc-01-voice.json).
- noah bm_george 2.970 (lines 2.60-3.37): six lines (evidence/long/20261026/noah-scoffer-voice.json; the same run gave
  Adam and Eve the arc-1 second run's 3.798 and 3.566 to the third decimal, so the method is the same); the 8-line
  probe of evidence/voice/20261026/kokoro-pace.json gave 2.868.
- scoffer am_puck 3.579 (kokoro-pace.json's probe; 3.425 in noah-scoffer-voice.json), serpent bm_fable 2.728 (the
  probe).
- God in a Short (SHORT_PACE) 3.072: his 9 lines voiced in the genesis-07 to 10 Shorts (kokoro-pace.json short_god);
  the long keeps the arc-1 2.811.

Two bounds a speaker (E104, review of #421). VOICE_PACE is the fastest measured run: a talking line too short for its
clip is judged there. VOICE_SLOWEST is the slower of the slowest run x SLOW_RATIO (2.25 / 2.75) and the slowest line
measured: a line too long for its clip, or where no clip reaches, is judged there. The fastest run slowed by SLOW_RATIO
gave Eve 3.05 words a second, but her lines reach 2.85: a 35-word line passed and would measure ~12.3 s. A test
derives both bounds from the evidence files, so neither is ever looser than the measurements. The narration keeps its
own rule: plan_check WPS 2.75 / WPS_SLOWEST 2.25 (the Keeper's Short narration measured 2.756 over 82 lines,
kokoro-pace.json), long_plan_check 2.874 here x SLOW_RATIO.

A pace belongs to its voice (MEASURED_WITH; a test keeps it equal to characters.json): give a speaker another voice and
measure it again. A talking speaker with no pace here is refused at plan time (VOICE_PACE_UNMEASURED)."""

VOICE_PACE = {"keeper": 2.874, "god": 2.811, "adam": 3.975, "eve": 3.732, "noah": 2.970, "scoffer": 3.579,
              "serpent": 2.728}
SHORT_PACE = {"god": 3.072}          # a Short-measured pace where it differs from the long's
#               min(slowest run x SLOW_RATIO, slowest line)
VOICE_SLOWEST = {"god": 2.128,      # min(2.776 x 0.818 = 2.271, arc-1 line 2.128)
                 "adam": 3.076,     # min(3.760 x 0.818, line 3.277)
                 "eve": 2.797,      # min(3.419 x 0.818, line 2.853)
                 "noah": 2.347,     # min(2.868 x 0.818, line 2.450)
                 "scoffer": 2.802,  # min(3.425 x 0.818, line 2.835)
                 "serpent": 2.230}  # min(2.728 x 0.818 = 2.232, line 2.230)
MEASURED_WITH = {"keeper": ("am_michael", 1.0), "god": ("am_onyx", 0.9), "adam": ("am_fenrir", 1.0),
                 "eve": ("af_heart", 1.0), "noah": ("bm_george", 1.0), "scoffer": ("am_puck", 1.0),
                 "serpent": ("bm_fable", 1.0)}
