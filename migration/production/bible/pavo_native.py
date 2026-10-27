#!/usr/bin/env python3
"""Pavo's own speech for the spoken shots (owner, 27/10 ~20:40-22:50 UTC, R2 and R4; story QA v4).

A plan opts in: a long with `"criteria": "story-qa-criteria-v4"`, a Short with `"audio_route": "pavo_native"`. Every
other plan keeps today's route (our Kokoro line as Pavo input audio, Pavo's own audio stripped).

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
    """The plan opts into Pavo's own speech: a long measured by story QA v4, or a Short that says so."""
    return isinstance(plan, dict) and (plan.get("criteria") == V4 or plan.get("audio_route") == NATIVE)


def load_voices(path=VOICES):
    return json.loads(Path(path).read_text())["voices"]


def load_blocks(path=BLOCKS):
    p = Path(path)
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


def native_request(req, plan, shot, index, chars=None, voices=None):
    """The native request from the build's own request: the same references and frames, the plan's prompt word for
    word (no audio binding clause: no input audio) with the SOUND sentence, Pavo's sound on, no input audio."""
    out = dict(req)
    out["prompt"] = f"{shot['prompt'].rstrip()} {sound_sentence(plan, shot, index, chars, voices)}"
    out["audios"] = None
    out["sound"] = True
    return out


def record_block(shot_id, line, reason, conversation_id, path=BLOCKS, today=None):
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
        Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return data


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


def speech_verdict(measures, line, crit=None):
    """Flags of one Pavo speech clip under story QA v4 (empty: it passes). `measures`: asr {model_bin_sha256, text},
    voice {reference (sha256 or None), same (cosine to its character's reference), others (cosines to the other
    characters' references)}, lufs (integrated, the clip's speech), music, singing (YAMNet shares), lips (the flags of
    lipsync_check / --still-mouth / --faces by its kind). A missing measure is a flag, never a pass."""
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
    if not voice.get("reference"):
        flags.append("VOICE_REFERENCE_MISSING")
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


def speech_span(measures):
    """(onset, end) of the clip's speech in seconds, from its ASR span: the cut and the voice layout use them."""
    span = (measures.get("asr") or {}).get("speech_span")
    if not (isinstance(span, (list, tuple)) and len(span) == 2 and all(isinstance(x, (int, float)) for x in span)
            and 0 <= span[0] < span[1]):
        raise SystemExit("SPEECH_SPAN_UNKNOWN (the approved clip records no ASR speech span)")
    return float(span[0]), float(span[1])
