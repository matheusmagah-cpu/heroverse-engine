#!/usr/bin/env python3
"""Kokoro pace by voice, words a second: the one table plan_check (Shorts) and long_plan_check (the long) time their
lines with (E104). A character speaks ~35 % faster than the narrator, so one pace for every line let a Short plan pass
with a talking line its build then refused (TALK_LINE_RETIME_OVER).

Each pace is the words of a voice's lines over their measured lengths (first word to last word of each line, as
episode_build lines cuts them), voiced locally with the hash-pinned Kokoro v1.0 model episode.yml installs:
- keeper (am_michael), god (am_onyx at 0.9), adam (am_fenrir), eve (af_heart): the arc-1 long voiced line by line
  (evidence/long/20261026/arc-01-voice.json, PR #418, first run);
- the Keeper's narration in a Short: the genesis-07 to 10 Short plans voiced in full, 82 lines, 2.756 (lines 1.99-3.63;
  2.75 measured on genesis-07 before): a Short's narration is slower than the long's (shorter sentences, each with
  its pause), so a Short times it at SHORT_NARRATION_PACE;
- noah (bm_george), scoffer (am_puck), serpent (bm_fable): 8 representative spoken lines each (the scoffer's also its 2
  lines in the genesis-08/09 plans) (evidence/voice/20261026/kokoro-pace.json).
A line is judged from its voice's pace to the slowest, the pace * SLOW_RATIO (the narrator's measured spread,
WPS_SLOWEST / WPS). A speaker missing here has no measured pace: plan_check refuses its talking line until it is
measured and added here (SPEAKER_PACE_UNMEASURED).
"""

NARRATOR = "keeper"                 # characters.NARRATOR (no import: long_plan_check and plan_check both load this)
WPS = 2.75                          # the Short narration's pace (am_michael over a whole Short track)
WPS_SLOWEST = 2.25                  # its slowest measured stretch: the spread every voice is judged over
SLOW_RATIO = WPS_SLOWEST / WPS
SHORT_NARRATION_PACE = WPS
VOICE_PACE = {"keeper": 2.874, "god": 2.811, "adam": 3.975, "eve": 3.732,
              "noah": 2.868, "scoffer": 3.55, "serpent": 2.728}


def pace(speaker=None, short=True):
    """Words a second of the voice that speaks a line (no speaker: the Keeper's narration), or None when that voice
    has not been measured. short: a Short's narration (SHORT_NARRATION_PACE), else the long's."""
    who = speaker or NARRATOR
    if who == NARRATOR and short:
        return SHORT_NARRATION_PACE
    return VOICE_PACE.get(who)


def slowest(speaker=None, short=True):
    """The slowest pace a line in that voice is judged at."""
    p = pace(speaker, short)
    return p * SLOW_RATIO if p else None
