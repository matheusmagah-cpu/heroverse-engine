#!/usr/bin/env python3
"""Pavo's own speech for the spoken shots (owner, 27/10 ~20:40-22:50 UTC, R2 and R4; story QA v4).

A plan opts in: a long with `"criteria": "story-qa-criteria-v4"` (unless it says `"audio_route": "kokoro"`). A Short's
`"audio_route": "pavo_native"` is refused by plan_check (AUDIO_ROUTE_SHORT_UNSUPPORTED, review of #476) until a frozen
Short criteria file holds the speech-check rows. Every other plan keeps today's route (our Kokoro line as Pavo input audio, Pavo's own audio stripped).

On the native route a spoken shot (a character or the Keeper on camera, God's or the Keeper's voice-over) is generated
by Pavo with `sound: true` and the structured SOUND sentence the native-audio probe kept (PR #473, prompt A): the
plan's visual prompt word for word, then the speaker's fixed voice description (voices.json), on camera or off screen,
the exact line once, pronunciation hints for the archaic words, and "the soundtrack is only the voice and the natural
ambient sound of <the plan's ambience>" (music excluded in positive words only: no Pavo music, our owned track goes
under the cut). A non-spoken scene is generated as before (audio stripped), so its request digest does not change.

A line Pavo's prompt filter refuses goes to our Kokoro voice (R4: the hybrid route of #473), automatically:
  - predicted from the words the filter is known to refuse (evidence/pavo/prompt-blocks.json `words`: "naked",
    Genesis 3:7/3:10/3:11), so the plan, the preflight and the probe never send them;
  - learned when the adapter reads a block back (PAVO_PROMPT_BLOCKED, E129): the block is recorded by the line's words
    (`record_block`), and the probe sends that shot again on the Kokoro route at once.

Each clip that keeps its speech is judged by `speech_verdict` against story QA v4 rights.ai_video.speech_checks: exact
words (WER 0 with the pinned medium.en), one consistent voice per character against its reference clip (and distinct
from the others), lip sync / still mouth / no face by its kind, its loudness brought to the common level by one gain,
no music, no singing.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for _p in (HERE, REPO / "migration" / "production" / "characters"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
V4 = "story-qa-criteria-v4"
QA_V4 = REPO / "migration" / "production" / "qa_criteria_story_v4.json"
NATIVE = "pavo_native"
KOKORO = "kokoro"
VOICES = HERE / "voices.json"
BLOCKS = REPO / "migration" / "evidence" / "pavo" / "prompt-blocks.json"
NATIVE_BINDING = "pavo native speech (story QA v4)"   # episode_preflight's probe key for a native talking line
WORD = re.compile(r"[a-z0-9']+")
# hints the probe sent (prompt A); "gavest" was heard by medium.en on Pavo and on Kokoro
PRONOUNCE = {"thy": '"thy" rhymes with "high"', "thee": '"thee" rhymes with "see"', "thou": '"thou" rhymes with "now"',
             "wast": '"wast" rhymes with "lost"', "hast": '"hast" rhymes with "last"',
             "gavest": '"gavest" is two syllables, "GAV-est"', "hath": '"hath" rhymes with "path"'}
ON_CAMERA = "{name} speaks on camera, {pronoun} lips moving in sync with every word."
OFF_SCREEN = "{name} is heard off screen as a voice-over; no one on screen speaks, every mouth on screen stays closed."


def words(text):
    return WORD.findall(str(text or "").lower())


def criteria(path=QA_V4):
    return json.loads(Path(path).read_text())


def native_plan(plan):
    """The plan opts into Pavo's own speech: a long measured by story QA v4 (unless it says "audio_route": "kokoro",
    review of #476), or a plan that says "audio_route": "pavo_native" (a Short is refused by plan_check until a Short
    criteria file with the speech rows exists)."""
    if not isinstance(plan, dict) or plan.get("audio_route") == KOKORO:
        return False
    return plan.get("criteria") == V4 or plan.get("audio_route") == NATIVE


def load_voices(path=None):
    return json.loads(Path(path or VOICES).read_text())["voices"]


def load_blocks(path=None):
    p = Path(path or BLOCKS)
    return json.loads(p.read_text()) if p.exists() else {"words": [], "lines": []}


def line_digest(text):
    return hashlib.sha256(" ".join(words(text)).encode()).hexdigest()


def blocked_words(text, blocks=None):
    """The words of a line Pavo's prompt filter is known to refuse (prompt-blocks.json `words`)."""
    blocks = load_blocks() if blocks is None else blocks
    found = set(words(text)) & {w.lower() for w in blocks.get("words", [])}
    return sorted(found)


def line_blocked(text, blocks=None):
    """True when the filter is known to refuse this line: one of its words, or this exact line read back blocked."""
    blocks = load_blocks() if blocks is None else blocks
    return bool(blocked_words(text, blocks)) or line_digest(text) in {x.get("line_sha256") for x in blocks.get("lines", [])}


def spoken(shot):
    import plan_check
    return plan_check.talking(shot) or plan_check.speaking(shot) or plan_check.voiceover(shot)


def shot_line(plan, index):
    import plan_check
    items, carried = plan_check.sequence(plan)
    return " ".join(items[k]["text"] for k in carried[index])


def speaker(shot):
    import characters as ch
    return ch.NARRATOR if shot.get("kind") == "keeper" else shot.get("speaker")


def route(plan, shot, index, blocks=None):
    """None for a shot that speaks no line; on a native plan "pavo_native", or "kokoro" for a line the filter
    refuses; on any other plan "kokoro" (today's route)."""
    if not spoken(shot):
        return None
    if not native_plan(plan):
        return KOKORO
    return KOKORO if line_blocked(shot_line(plan, index), blocks) else NATIVE


def ambience(plan, shot):
    return str(shot.get("ambience") or plan.get("ambience") or "").strip().rstrip(".")


def sound_sentence(plan, shot, index, chars=None, voices=None):
    """The SOUND part of a native request (the probe's prompt A)."""
    import characters as ch
    import plan_check
    chars = chars if chars is not None else ch.registry()
    voices = load_voices() if voices is None else voices
    who = speaker(shot)
    entry = voices.get(who) or {}
    if not entry.get("pavo_voice"):
        raise SystemExit(f"PAVO_VOICE_UNDESCRIBED {shot['id']} {who} (production/bible/voices.json)")
    place = ambience(plan, shot)
    if not place:
        raise SystemExit(f"AMBIENCE_MISSING {shot['id']} (the plan's `ambience`: the natural sound under the voice)")
    name = {ch.NARRATOR: "The narrator", ch.GOD: "God"}.get(who) or (chars.get(who) or {}).get("name") or who
    pronoun = (chars.get(who) or {}).get("pronoun") or "his"
    camera = ON_CAMERA if plan_check.talking(shot) else OFF_SCREEN
    line = shot_line(plan, index)
    hints = [PRONOUNCE[w] for w in dict.fromkeys(words(line)) if w in PRONOUNCE]
    parts = [f"SOUND. {name}'s voice: {entry['pavo_voice']}.", camera.format(name=name, pronoun=pronoun),
             f'{name} says exactly these words and nothing else, once, in English: "{line}"']
    if hints:
        parts.append("Pronunciation: " + "; ".join(hints) + ".")
    parts.append(f"The soundtrack is only the voice and the natural ambient sound of {place}.")
    return " ".join(parts)


# Pavo's own pace, measured on the native-audio probe (PR #473, medium.en speech spans): the Keeper 2.63-2.83 words/s,
# Adam 3.36, God 1.77; the first word came at 0-1.5 s. A native clip is asked long enough for its line at that pace.
NATIVE_PACE = {"keeper": 2.6, "god": 1.75}
NATIVE_PACE_DEFAULT = 2.6
NATIVE_ONSET_S = 1.5
CLIP_SECONDS = (4, 12)   # the adapter's clip range (plan_check.TALK_CLIP)


def native_seconds(shot, index, plan):
    """Clip seconds a native spoken shot asks Pavo for: its words at the speaker's measured Pavo pace plus the onset,
    whole seconds, 4-12."""
    import math
    n = len(words(shot_line(plan, index)))
    pace = NATIVE_PACE.get(speaker(shot), NATIVE_PACE_DEFAULT)
    return int(min(CLIP_SECONDS[1], max(CLIP_SECONDS[0], math.ceil(n / pace + NATIVE_ONSET_S - 1e-6))))


def native_request(req, plan, shot, index, chars=None, voices=None):
    """The native request from the build's own request: the same references and frames, the plan's prompt word for
    word (no audio binding clause: no input audio) with the SOUND sentence, Pavo's sound on, no input audio."""
    out = dict(req)
    out["prompt"] = f"{shot['prompt'].rstrip()} {sound_sentence(plan, shot, index, chars, voices)}"
    out["audios"] = None
    out["sound"] = True
    return out


def record_block(shot_id, line, reason, conversation_id, path=None, today=None):
    """A read-back PAVO_PROMPT_BLOCKED, kept by the line's words so no plan sends that line to Pavo's speech again
    (route() sends it to Kokoro). The reason code only; never the block's text."""
    import time
    data = load_blocks(path)
    data.setdefault("lines", [])
    digest = line_digest(line)
    if not any(x.get("line_sha256") == digest for x in data["lines"]):
        data["lines"].append({"line_sha256": digest, "shot": shot_id, "reason": reason,
                              "conversation_id": str(conversation_id),
                              "date": today or time.strftime("%Y-%m-%d", time.gmtime())})
        Path(path or BLOCKS).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return data


def merge_blocks(record, path=None):
    """shot-probe.yml's record job (review of #476): the blocks a probe run learned (its record's `prompt_blocks`)
    into evidence/pavo/prompt-blocks.json, committed with the record, so the next run, the preflight (which binds the
    file) and verify-preflight all send that line to Kokoro. Returns the digests added."""
    data = load_blocks(path)
    data.setdefault("lines", [])
    have = {x.get("line_sha256") for x in data["lines"]}
    added = []
    for b in record.get("prompt_blocks") or []:
        digest = b.get("line_sha256")
        if not (isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)) or digest in have:
            continue
        reason = str(b.get("reason") or "unknown")
        shot, cid = str(b.get("shot") or ""), str(b.get("conversation_id") or "")
        # sweep H2 (review of #476): the record comes from the probe job's artifact; only plain ids are copied
        data["lines"].append({"line_sha256": digest, "shot": shot if re.fullmatch(r"[a-z0-9-]{1,80}", shot) else "",
                              "reason": reason if re.fullmatch(r"[a-z_]{1,60}", reason) else "unknown",
                              "conversation_id": cid if re.fullmatch(r"[A-Za-z0-9_-]{1,40}", cid) else "",
                              "run_id": str(record.get("run_id") or "")})
        have.add(digest)
        added.append(digest)
    if added:
        Path(path or BLOCKS).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return added


def blocks_sha256(path=None):
    """The prompt-blocks file's sha256 (the preflight binds it: a new block changes routes and request digests)."""
    p = Path(path or BLOCKS)
    return sha256_file(p) if p.exists() else None


# ---------- the clip's checks (story QA v4 rights.ai_video.speech_checks) ----------

def wer(reference, heard):
    """Word error rate of the heard words against the line (lower case, punctuation ignored)."""
    r, h = words(reference), words(heard)
    d = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        prev, d[0] = d[0], i
        for j, hw in enumerate(h, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (rw != hw))
    return d[len(h)] / max(1, len(r))


def clip_gain_db(lufs, checks):
    """One static gain to the common voice level, at most clip_gain_db_max (None when the clip cannot reach it)."""
    if lufs is None:
        return None
    gain = checks["clip_voice_lufs_target"] - lufs
    return round(gain, 2) if gain <= checks["clip_gain_db_max"] + 1e-9 else None


def voice_reference(speaker_id, voices=None):
    """The clip sha256 voices.json holds as this speaker's reference (episode_build.py voice-reference), or None."""
    voices = load_voices() if voices is None else voices
    ref = (voices.get(speaker_id) or {}).get("reference")
    return ref.get("clip_sha256") if isinstance(ref, dict) else None


def voice_binding(speaker_id, voices=None):
    """Review of #476: what a speech clip's voice must be measured against, from voices.json only: this speaker's
    reference clip sha256 and every other speaker's reference sha256 (the "others" the margin is judged on)."""
    voices = load_voices() if voices is None else voices
    others = sorted(r for w in voices if w != speaker_id for r in [voice_reference(w, voices)] if r)
    return {"reference": voice_reference(speaker_id, voices), "others": others}


def speech_verdict(measures, line, crit=None, binding=None):
    """Flags of one Pavo speech clip under story QA v4 (empty: it passes). `measures`: asr {model_bin_sha256, text},
    voice {reference (sha256 or None), same (cosine to its character's reference), others (cosines to the other
    characters' references)}, lufs (integrated, the clip's speech), music, singing (YAMNet shares), lips (the flags of
    lipsync_check / --still-mouth / --faces by its kind). A missing measure is a flag, never a pass. `binding`
    (voice_binding, review of #476): the voice is measured against exactly the speaker's reference in voices.json
    (VOICE_REFERENCE_MISSING / VOICE_REFERENCE_MISMATCH) and against every other speaker's reference there, none
    missing and none extra (VOICE_OTHERS_MISSING when there is none: distinct from no one is not distinct)."""
    crit = criteria() if crit is None else crit
    checks = crit["rights"]["ai_video"]["speech_checks"]
    pinned = crit["speech"]["asr_model"]["model_bin_sha256"]
    flags = []
    asr = measures.get("asr") or {}
    if asr.get("model_bin_sha256") != pinned:
        flags.append("ASR_MODEL_NOT_PINNED")
    elif asr.get("text") is None:
        flags.append("SPEECH_NOT_HEARD")
    elif wer(line, asr["text"]) > checks["exact_words_wer_max"] + 1e-9:
        flags.append("SPEECH_WORDS_NOT_EXACT")
    voice = measures.get("voice") or {}
    binding = binding or {}
    others, measured = voice.get("others") or [], voice.get("others_references") or []
    if not voice.get("reference") or not binding.get("reference"):
        flags.append("VOICE_REFERENCE_MISSING")
    elif voice["reference"] != binding["reference"]:
        flags.append("VOICE_REFERENCE_MISMATCH")
    elif not binding.get("others") or not others:   # distinct from whom? every other speaker's reference is measured
        flags.append("VOICE_OTHERS_MISSING")
    elif sorted(measured) != sorted(binding["others"]) or len(others) != len(measured):
        flags.append("VOICE_OTHERS_MISMATCH")
    elif not isinstance(voice.get("same"), (int, float)) or voice["same"] < checks["voice_same_character_cosine_min"]:
        flags.append("VOICE_NOT_CONSISTENT")
    elif max(voice.get("others") or [-1.0]) > voice["same"] - checks["voice_other_character_margin_min"] + 1e-9:
        flags.append("VOICE_NOT_DISTINCT")
    if clip_gain_db(measures.get("lufs"), checks) is None:
        flags.append("SPEECH_LEVEL_UNREACHABLE")
    music, singing = measures.get("music"), measures.get("singing")
    if not isinstance(music, (int, float)) or music > checks["music_presence_max"] + 1e-9:
        flags.append("PAVO_MUSIC")
    if not isinstance(singing, (int, float)) or singing > checks["singing_presence_max"] + 1e-9:
        flags.append("PAVO_SINGING")
    lips = measures.get("lips")
    if lips is None:
        flags.append("LIPS_NOT_CHECKED")
    else:
        flags += list(lips)
    return flags


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def measure(clip, whisper_dir, yamnet, references, speaker_id, lips, run=None):
    """The measures speech_verdict judges, on one native clip (episode_build.py speech-check; Claude's session or a
    runner with faster-whisper 1.2.1, resemblyzer 0.1.4 and the YAMNet model): the pinned ASR's words and speech span,
    YAMNet's music and singing shares, the speech span's integrated loudness, the speaker cosines against every
    reference clip in `references` ({speaker: wav}), and `lips` (the flags of its lips / still-mouth / face check)."""
    import subprocess
    run = run or subprocess.run
    sys.path.insert(0, str(REPO / "migration" / "diagnostics" / "av-semantic"))
    import av_semantic
    from faster_whisper import WhisperModel
    model = WhisperModel(str(whisper_dir), device="cpu", compute_type="int8", local_files_only=True)
    segments, _ = model.transcribe(str(clip), language="en", beam_size=5, condition_on_previous_text=False)
    segments = list(segments)
    text = " ".join(s.text.strip() for s in segments)
    span = [round(segments[0].start, 3), round(segments[-1].end, 3)] if segments else None
    shares = av_semantic.analyze(str(clip), str(yamnet))["presence_fraction"]
    lufs = None
    if span:
        done = run(["ffmpeg", "-nostdin", "-v", "info", "-i", str(clip), "-af",
                    f"atrim={span[0]}:{span[1]},ebur128", "-f", "null", "-"], capture_output=True, text=True)
        found = re.findall(r"I:\s+(-?[0-9.]+) LUFS", done.stderr)
        lufs = float(found[-1]) if found else None
    voice = {"reference": None, "same": None, "others": []}
    if references.get(speaker_id):
        from resemblyzer import VoiceEncoder, preprocess_wav
        enc = VoiceEncoder("cpu")
        mine = enc.embed_utterance(preprocess_wav(str(clip)))

        def cos(path):
            other = enc.embed_utterance(preprocess_wav(str(path)))
            return round(float((mine * other).sum()), 4)   # embeddings are L2-normalised
        rest = [p for who, p in sorted(references.items()) if who != speaker_id]
        voice = {"reference": sha256_file(references[speaker_id]), "same": cos(references[speaker_id]),
                 "others": [cos(p) for p in rest], "others_references": [sha256_file(p) for p in rest]}
    return {"asr": {"model_bin_sha256": sha256_file(Path(whisper_dir) / "model.bin"), "text": text,
                    "speech_span": span},
            "music": shares.get("music"), "singing": shares.get("singing"), "lufs": lufs, "voice": voice,
            "lips": list(lips) if lips is not None else None}


def speech_record(clip_sha, measures, line, crit=None, binding=None):
    """What approve-shot copies into a native clip's approval: the verdict recomputed from the measures (never a
    recorded `flags` field), the speech span and the one gain to the common level."""
    crit = criteria() if crit is None else crit
    flags = speech_verdict(measures, line, crit, binding)
    onset, end = speech_span(measures) if not flags else ((measures.get("asr") or {}).get("speech_span") or [None, None])
    return {"clip_sha256": clip_sha, "flags": flags, "onset": onset, "end": end, "lufs": measures.get("lufs"),
            "gain_db": clip_gain_db(measures.get("lufs"), crit["rights"]["ai_video"]["speech_checks"]),
            "criteria": crit["version"]}


# ---------- the mix (story QA v4 grammar.spoken_audio_mix; the #473 "mix b" that measured -15.0 LUFS, LRA 5.9) ----------

XFADE_S = 0.08        # a short fade at each end of a speech clip: no click at the cut (<= audio_crossfade_seconds_max)
BED_DB = -30.0        # brown noise 60-900 Hz under every cut, about -40 dBFS: no cut drops to digital silence
BED_BAND = (60, 900)


def placements(plan, layout, spans, clips, approvals):
    """Each native speech clip's audio in the voice track: from its speech onset to its end, at its run's first line,
    with its approval's one gain to the common level."""
    out = []
    for sid, (idx, onset, end) in sorted(spans.items(), key=lambda kv: kv[1][0][0]):
        gain = ((approvals.get(sid) or {}).get("speech") or {}).get("gain_db")
        if not isinstance(gain, (int, float)):
            raise SystemExit(f"SPEECH_UNCHECKED {sid} (no gain recorded with its approval)")
        if sid not in clips or not Path(clips[sid]).is_file():
            raise SystemExit(f"NATIVE_CLIP_MISSING {sid} (the approved clip with its own audio)")
        out.append({"shot": sid, "clip": str(clips[sid]), "at": float(layout["lines"][idx[0]]["start"]),
                    "src_start": onset, "seconds": round(end - onset, 3), "gain_db": float(gain)})
    return out


def premix_filter(places, total):
    """The ffmpeg graph: input 0 our voice track (silence where Pavo speaks), inputs 1.. the speech clips; each clip's
    speech trimmed, one static gain, XFADE_S fades, delayed to its place; a continuous low ambience bed; summed with
    no normalisation (the build's two-pass loudnorm comes after the music)."""
    parts, labels = ["[0:a]aresample=48000,aformat=channel_layouts=stereo[v]"], ["[v]"]
    for k, p in enumerate(places, start=1):
        d = p["seconds"]
        ms = int(round(p["at"] * 1000))
        parts.append(f"[{k}:a]atrim=start={p['src_start']:.3f}:duration={d:.3f},asetpts=PTS-STARTPTS,"
                     f"aresample=48000,aformat=channel_layouts=stereo,volume={p['gain_db']:.2f}dB,"
                     f"afade=t=in:d={XFADE_S},afade=t=out:st={max(0.0, d - XFADE_S):.3f}:d={XFADE_S},"
                     f"adelay={ms}|{ms}[s{k}]")
        labels.append(f"[s{k}]")
    parts.append(f"anoisesrc=color=brown:sample_rate=48000:duration={total:.3f},highpass=f={BED_BAND[0]},"
                 f"lowpass=f={BED_BAND[1]},volume={BED_DB}dB,aformat=channel_layouts=stereo[bed]")
    labels.append("[bed]")
    parts.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,"
                 f"atrim=duration={total:.3f}[a]")
    return ";".join(parts)


def premix(voice_wav, places, out_wav, total, run=None):
    """Our voice track with Pavo's speech laid in and the bed under it, to out_wav (48 kHz stereo PCM)."""
    import subprocess
    run = run or subprocess.run
    args = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(voice_wav)]
    for p in places:
        args += ["-i", p["clip"]]
    args += ["-filter_complex", premix_filter(places, total), "-map", "[a]", "-c:a", "pcm_s16le", str(out_wav)]
    done = run(args, capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"PREMIX_FAILED {done.stderr.strip()[-400:]}")
    return out_wav


def speech_span(measures):
    """(onset, end) of the clip's speech in seconds, from its ASR span: the cut and the voice layout use them."""
    span = (measures.get("asr") or {}).get("speech_span")
    if not (isinstance(span, (list, tuple)) and len(span) == 2 and all(isinstance(x, (int, float)) for x in span)
            and 0 <= span[0] < span[1]):
        raise SystemExit("SPEECH_SPAN_UNKNOWN (the approved clip records no ASR speech span)")
    return float(span[0]), float(span[1])
