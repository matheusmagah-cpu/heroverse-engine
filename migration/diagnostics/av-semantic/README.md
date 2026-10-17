# Free offline semantic audio layer

`av_semantic.py MEDIA YAMNET_TFLITE [WHISPER_DIR]` labels what is heard:

- **Coarse classes** every 0.48 s: speech, singing, music, other sound, silence. It uses YAMNet (hash-pinned, preserved in the private release). A frame below 0.30 confidence is `UNCERTAIN`, never forced into a class. An all-zero frame is silence by measurement.
- **Words with timestamps** from the preserved faster-whisper `base.en` model. A word is accepted only if its probability is ≥ 0.5 **and** YAMNet hears speech or singing at that moment. Both models must agree, which removed hallucinated words on tones, noise and silence.

Timing, count and sync stay with `../av-event-meter` (deterministic). Models are never the authority for those.

**Qualification** (`criteria.json` frozen before code; CI run 38995242464): 9/9 PASS. Digital silence, tones and pink noise give zero words and zero speech. Clean known speech gives WER 0.12. Known speech over each of the five real openings gives WER 0.04–0.24 (limit 0.30). The five openings without added speech show music in 100% of frames.

Limits: English only. Instrument and lyric accuracy are not measured. Not a perceptual quality approval.
