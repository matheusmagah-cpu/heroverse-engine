#!/usr/bin/env python3
"""Build a Short from its plan with no chat session (owner, 2026-10-26): it opens on the conflict spoken by a
character or God's voice, the characters speak their own lines lip-synced, the story is acted out by the character
bible's people, the Keeper closes with our insight; everything generated free on Pavo, composed by the engine and
checked. episode.yml runs the steps in order; Claude only writes the plan and reviews the result. Nothing here
publishes: the composed file, a 20-frame sheet and a per-shot report go to Claude's review (>= 9.5), who then writes
the episode record and dispatches publish-episode.yml.

  episode_build.py voice-script PLAN WORK        WORK/voice-script.json for pilot_render.py voice (one segment a line
                                                 of plan_check.sequence; a spoken line in its speaker's own voice)
  episode_build.py lines PLAN WORK               per-line WAVs, each talking line retimed (atempo, <= +-10 %) to fit
                                                 a 4-12 s clip 0.25-0.65 s longer than its speech (E95), the voice
                                                 track rebuilt from them in order, each talking clip's input audio
                                                 (the Keeper's lines, a character's line; mono 44.1 kHz),
                                                 WORK/layout.json; refuses TALK_LINE_RETIME_OVER, a Keeper share or a
                                                 lesson share > 25 % and a length outside the part's range (170-179 s
                                                 from part 7)
  episode_build.py refs PLAN WORK                approved reference images (release asset or repository file, sha256
                                                 checked), as JPEG <= 1536 px in WORK/refs; a talking speaker's
                                                 `talk_refs` speaking frame as "<id>:talk" (E95)
  episode_build.py generate PLAN WORK LIP_PYTHON FACE_MODEL
                                                 one Pavo generation per shot, in order (PAVO_TOKEN from the env):
                                                 fresh exact 0-credit quote (the adapter refuses any other price),
                                                 poll job() until completed/failed, download from the Pavo CDN only,
                                                 clip_check on every clip, lipsync_check on every talking clip (the
                                                 Keeper, a character speaking; not God's voice-over shot), the
                                                 still-mouth check on a voice-over Keeper clip (plan B, `"voiceover":
                                                 true`: his line plays from the voice track); a failed shot is
                                                 regenerated as a NEW generation at most 2 times, then the run fails
                                                 naming the shot
  episode_build.py compose PLAN WORK MUSIC OUT   short_engine.py (cuts only, captions, owned music, -14 LUFS), then
                                                 clip_check --composed; WORK/report.json gets the timeline and checks
  episode_build.py sheet VIDEO SHEET.jpg         20 frames of the composed Short on one sheet (5 x 4)

WORK must be inside the repository: the Pavo adapter reads input images and audio only from repository paths.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import wave

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "migration" / "production" / "characters"))
sys.path.insert(0, str(REPO / "migration" / "production" / "footage"))
sys.path.insert(0, str(REPO / "migration" / "integrations" / "pavo"))
import plan_check  # noqa: E402
import characters as ch  # noqa: E402

VOICE = {"voice_id": "am_michael", "speed": 1.0}   # the pinned engine voice (qa_pilot.voice_model_pinned)
LINE_GAP = plan_check.LINE_GAP
TAIL = plan_check.TAIL
CUT_MAX = 4.0              # a scene cut every 2-4 s (DECISIONS 2026-10-26)
ESTABLISHING_HOLD = plan_check.ESTABLISHING_HOLD
MAX_SLOW = 1.3             # short_engine.MAX_SLOW
ATTEMPTS = 3               # one generation and at most 2 regenerations
# E98: a talking clip passes the lips check about 4 times in 10 (evidence/pavo/20261026/keeper-lipsync-rate.json):
# 3 generations lost a three-Keeper-shot run about half the time; 6 keep a shot at ~95 % (Pavo at 0 credits)
TALK_ATTEMPTS = 6
POLL_S = 15
JOB_TIMEOUT_S = 25 * 60
INCOMPLETE_POLLS = 8       # history can be empty just after submission; then "incomplete" means failed
RATE_LIMIT_WAITS = (60, 120, 240, 480)
# E93: Pavo unreachable for minutes killed a 25-of-33-shot run. generate_video raises it only before a generation
# starts (quote, upload, conversation create; a lost acknowledgement comes back as status unknown instead), so the
# call is sent again after a wait: about 33 min in all before the run gives up
OUTAGE_WAITS = (60, 120, 300, 600, 900)
TRANSIENT = {"PAVO_RATE_LIMITED": RATE_LIMIT_WAITS, "PAVO_UNREACHABLE": OUTAGE_WAITS,
             "PAVO_UPLOAD_HOST_UNREACHABLE": OUTAGE_WAITS}
REF_SIDE = 1536
LUFS = (-15.0, -13.0)
FADE_OUT = 0.8             # short_engine.FADE_OUT
RETIME_TRIM_MAX = 0.02     # atempo's few-ms miss cut or padded after a retime, never more (review of #412)
HOLD_MARGIN = 0.01         # a talking clip's held last frame is written this much longer than the time it covers


class ShotFailed(Exception):
    pass


def load(path):
    return json.loads(Path(path).read_text())


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def run(args, **kw):
    done = subprocess.run([str(a) for a in args], capture_output=True, text=True, **kw)
    if done.returncode:
        raise SystemExit(f"COMMAND_FAILED {Path(str(args[0])).name}: {done.stderr.strip()[-400:]}")
    return done.stdout


def rel(path):
    """Repository-relative path (the Pavo adapter takes only those)."""
    target = Path(path).resolve()
    if REPO.resolve() not in target.parents:
        raise SystemExit(f"WORK_OUTSIDE_REPOSITORY {path}")
    return str(target.relative_to(REPO.resolve()))


# ---------- voice ----------

def voice_script(plan, chars=None):
    """One segment a line of the voice track (plan_check.sequence): the narration in the Keeper's voice, each spoken
    line in its speaker's own voice (characters.voice; God's is the deep voice-over)."""
    items, _ = plan_check.sequence(plan)
    segments = []
    for k, x in enumerate(items):
        seg = {"id": f"n{k:02d}", "text": x["text"], "pause_after": 0.0}
        if x.get("speaker"):
            v = ch.voice(x["speaker"], chars)
            if not v:
                raise SystemExit(f"SPEAKER_NO_VOICE {x['speaker']}")
            seg.update(v, speaker=x["speaker"])
        segments.append(seg)
    return {"voice": dict(VOICE), "segments": segments}


def talk_record(layout, shot):
    """The line a talking shot's clip carries (input audio, lipsync_check): the Keeper's or a character's."""
    return layout["keeper"][shot["id"]] if shot["kind"] == "keeper" else layout["speakers"][shot["id"]]


def line_layout(durations, gap=LINE_GAP):
    """Lines laid end to end from 0 s with `gap` between them: [(start, end)]. The Keeper's hook starts at 0."""
    out, t = [], 0.0
    for d in durations:
        out.append((round(t, 3), round(t + d, 3)))
        t += d + gap
    return out


def keeper_span(lines, layout):
    return layout[lines[0]][0], layout[lines[-1]][1]


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        return w.getparams(), w.readframes(w.getnframes())


def write_wav(path, params, frames):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setparams(params)
        w.writeframes(frames)


def lines_step(plan, work):
    """Cut each line of the voice track out of pilot_render's voice.wav, rebuild the track from the line WAVs in
    order, write each talking clip's input audio (the Keeper's lines, a character's spoken line) and the compose
    timeline; measure the Short against the plan's rules again."""
    work = Path(work)
    items, carried = plan_check.sequence(plan)
    timeline = load(work / "timeline.json")
    params, frames = read_wav(work / "voice.wav")
    if params.sampwidth != 2:   # retime() reads atempo's pcm_s16le back under these params (review of #412)
        raise SystemExit(f"VOICE_SAMPLE_WIDTH {params.sampwidth * 8}-bit voice.wav (16-bit PCM only)")
    rate, width = params.framerate, params.sampwidth * params.nchannels
    n = len(items)
    by_line = {k: [s for s in timeline["sentences"] if s["segment"] == f"n{k:02d}"] for k in range(n)}
    if any(not v for v in by_line.values()):
        raise SystemExit("VOICE_LINE_MISSING " + " ".join(f"n{k:02d}" for k, v in by_line.items() if not v))
    pieces, durations = [], []
    for k in range(n):
        a = int(round(by_line[k][0]["start"] * rate)) * width
        b = int(round(by_line[k][-1]["end"] * rate)) * width
        pieces.append(frames[a:b])
        durations.append(len(frames[a:b]) / width / rate)
    # E95: a talking clip keeps our audio only when it is 0.25-0.65 s longer than the speech; a talking line that
    # misses that window is retimed (atempo, pitch kept, at most +-10 %) before anything is laid out, so the track,
    # the captions, the input audio and the lips check all use the same retimed words
    retimes, problems = {}, []
    scale = [1.0] * n
    for i, s in enumerate(plan["shots"]):
        if not plan_check.talking(s):
            continue
        idx = carried[i]
        gaps = LINE_GAP * (len(idx) - 1)
        words = sum(durations[k] for k in idx)
        speech = words + gaps
        found = plan_check.talk_retime(words, gaps)   # the cap is on the words atempo stretches, not on the gaps
        if found is None:
            problems.append(f"TALK_LINE_RETIME_OVER {s['id']} {speech:.2f} s (no {plan_check.TALK_CLIP[0]}-"
                            f"{plan_check.TALK_CLIP[1]} s clip within +-{plan_check.TALK_RETIME_MAX:.0%} of its words)")
            continue
        target, stretch = found
        if stretch == 1.0:
            continue
        factor = 1 / stretch                                       # atempo > 1 speeds the words up
        for k in idx:
            piece = retime(pieces[k], params, factor, work / "lines" / f"n{k:02d}")
            scale[k] = (len(piece) / width / rate) / durations[k]
            pieces[k], durations[k] = piece, len(piece) / width / rate
        retimes[s["id"]] = {"speech": round(speech, 3), "retimed": round(sum(durations[k] for k in idx) + gaps, 3),
                            "atempo": round(factor, 4)}
    for k in range(n):
        write_wav(work / "lines" / f"n{k:02d}.wav", params, pieces[k])
    layout = line_layout(durations)
    silence = b"\x00" * (int(round(LINE_GAP * rate)) * width)
    track = silence.join(pieces)
    write_wav(work / "narration.wav", params, track)
    voice_seconds = round(len(track) / width / rate, 3)
    sentences = []
    for k in range(n):
        first = by_line[k][0]["start"]
        who = {"speaker": items[k]["speaker"]} if items[k].get("speaker") else {}
        sentences += [dict({"segment": f"n{k:02d}", "text": s["text"],
                            "start": round(layout[k][0] + (s["start"] - first) * scale[k], 3),
                            "end": round(layout[k][0] + (s["end"] - first) * scale[k], 3)}, **who) for s in by_line[k]]
        sentences[-1]["end"] = round(layout[k][1], 3)
    save(work / "compose-timeline.json", {"voice_seconds": voice_seconds, "sentences": sentences,
                                          "voice_id": VOICE["voice_id"], "speed": VOICE["speed"], "sample_rate": rate})
    total = round(voice_seconds + TAIL, 3)
    keeper, speakers, voice_over, keeper_seconds = {}, {}, {}, 0.0
    shots = plan["shots"]
    refused = {p.split()[1] for p in problems}
    for i, s in enumerate(shots):
        if (s["kind"] != "keeper" and not plan_check.speaking(s)) or s["id"] in refused:
            continue
        start, end = keeper_span(carried[i], layout)
        seconds = end - start
        talks = plan_check.talking(s)
        if s["kind"] == "keeper":
            keeper_seconds += seconds
            low, code, folder, into = plan_check.KEEPER_AUDIO[0], "KEEPER_AUDIO", "keeper", keeper
        else:
            low, code, folder = plan_check.SPEAKER_AUDIO[0], "SPEAKER_AUDIO", "speakers"
            into = speakers if talks else voice_over
        # one talking ceiling (plan_check.TALK_LINE_MAX: the retime brings every talking line under it; 1 ms is the
        # layout's rounding); God's voice-over fills one scene clip
        limit = (plan_check.TALK_LINE_MAX if talks else plan_check.VO_LINE_MAX if plan_check.voiceover(s)
                 else plan_check.SPEAKER_AUDIO[1])
        if not low <= seconds <= limit + (1e-3 if talks else 0.0):
            problems.append(f"{code} {s['id']} {seconds:.2f} s ({low:.0f}-{limit:.2f} s)")
            continue
        if talks:
            # its clip is ceil(speech) seconds with the speech 0.25-0.65 s shorter (E95): refused here, before any
            # Pavo clip, when no 4-12 s clip can carry it
            need = talk_need(seconds)
            if need > plan_check.TALK_CLIP_MAX or not talk_fits(seconds):
                problems.append(f"TALK_LINE_TOO_LONG {s['id']} {seconds:.2f} s (needs a {need} s clip; Pavo keeps our "
                                f"audio in a {plan_check.TALK_CLIP[0]}-{plan_check.TALK_CLIP[1]} s clip 0.25-0.65 s "
                                "longer than the speech)")
                continue
        record = {"start": start, "end": end, "seconds": round(seconds, 3)}
        if plan_check.voiceover(s):     # plan B: no input audio, no lipsync; his line is narration in the track
            keeper[s["id"]] = dict(record, voiceover=True)
            continue
        if s["kind"] != "keeper":
            record["speaker"] = s["speaker"]
        if into is voice_over:          # God: mixed as a voice-over in the track; no clip audio, no lipsync check
            voice_over[s["id"]] = record
            continue
        native = work / folder / f"{s['id']}-native.wav"
        a, b = int(round(start * rate)) * width, int(round(end * rate)) * width
        write_wav(native, params, track[a:b])
        out = work / folder / f"{s['id']}.wav"
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", native, "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le",
             out])
        into[s["id"]] = dict(record, wav=rel(out))
    share = keeper_seconds / total
    if share > plan_check.KEEPER_SHARE_MAX:
        problems.append(f"KEEPER_SHARE {share:.3f} > {plan_check.KEEPER_SHARE_MAX} (measured)")
    lesson = sorted({k for i, s in enumerate(shots) for k in carried[i]
                     if s["kind"] == "keeper" or items[k].get("kind") in plan_check.LESSON_KINDS})
    lesson_seconds = sum(layout[k][1] - layout[k][0] for k in lesson) + LINE_GAP * max(len(lesson) - 1, 0)
    lesson_share = lesson_seconds / total
    if lesson_share > plan_check.LESSON_SHARE_MAX:
        problems.append(f"LESSON_SHARE {lesson_share:.3f} > {plan_check.LESSON_SHARE_MAX} (measured)")
    low, high = plan_check.publish_episode.short_length(plan.get("part", 0))
    if not low <= total <= high:
        problems.append(f"SHORT_LENGTH {total} s ({low:.0f}-{high:.0f}, measured)")
    result = {"lines": [{"start": a, "end": b} for a, b in layout], "voice_seconds": voice_seconds, "total": total,
              "keeper": keeper, "speakers": speakers, "voice_over": voice_over, "keeper_share": round(share, 3),
              "lesson_share": round(lesson_share, 3), "retimed": retimes, "problems": problems}
    save(work / "layout.json", result)
    print(json.dumps({k: result[k] for k in ("voice_seconds", "total", "keeper_share", "lesson_share", "problems")}))
    if problems:
        raise SystemExit("LINES_REFUSED " + "; ".join(problems))
    return result


# ---------- reference images ----------

def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def reference_records(cid, chars=None, images_dir=ch.HERE / "images", field="refs"):
    """The kept reference images of one APPROVED character, in characters.json order: [(record id, record)].
    field "talk_refs": its speaking frames (E95: a mouth-closed front view broke the lip tracking), [] when none."""
    chars = chars if chars is not None else ch.registry()
    c = chars.get(cid)
    if not c or c.get("status") != "APPROVED" or not c.get("refs"):
        raise SystemExit(f"CHARACTER_NOT_APPROVED {cid}")
    out = []
    for shot in c.get(field) or []:
        rec = Path(images_dir) / f"ch-{cid}-{shot}.json"
        m = load(rec) if rec.exists() else {}
        if not m.get("sha256") or not (m.get("release_asset") or m.get("repo_path")):
            raise SystemExit(f"REFERENCE_RECORD_MISSING ch-{cid}-{shot}")
        out.append((f"ch-{cid}-{shot}", m))
    return out


def fetch_release_asset(name, dst):
    run(["bash", REPO / "migration" / "ci" / "assets.sh", "download", "--pattern", name, "-O", dst, "--clobber"])


def refs_step(plan, work, fetch=fetch_release_asset, chars=None):
    """Every reference a shot needs, verified by sha256 and resized to <= 1536 px JPEG (Flash takes up to 15 MiB)."""
    work = Path(work)
    needed, talkers = [], []
    for s in plan["shots"]:
        for cid in (["keeper"] if s["kind"] == "keeper" else s.get("characters", [])):
            if cid not in needed:
                needed.append(cid)
        if (plan_check.talking(s) or plan_check.voiceover(s)) and speaker_of(s) not in talkers:
            talkers.append(speaker_of(s))
    out = {}
    wanted = [(cid, cid, "refs") for cid in needed] + [(f"{cid}:talk", cid, "talk_refs") for cid in talkers]
    for key, cid, field in wanted:
        records = reference_records(cid, chars, field=field)
        if not records:
            continue
        out[key] = []
        for rid, m in records:
            raw = work / "refs" / "raw" / rid
            raw.parent.mkdir(parents=True, exist_ok=True)
            if m.get("repo_path"):
                src = (REPO / m["repo_path"]).resolve()
                if REPO.resolve() not in src.parents or not src.is_file():
                    raise SystemExit(f"REFERENCE_PATH_REFUSED {rid}")
                shutil.copyfile(src, raw)
            else:
                if not re.fullmatch(r"[A-Za-z0-9._-]+\.(png|jpg|jpeg)", m["release_asset"]):
                    raise SystemExit(f"REFERENCE_ASSET_NAME_REFUSED {rid}")
                fetch(m["release_asset"], raw)
            if sha256(raw) != m["sha256"]:
                raise SystemExit(f"REFERENCE_SHA256_MISMATCH {rid}")
            jpg = work / "refs" / f"{rid}.jpg"
            run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", raw, "-vf",
                 f"scale='min({REF_SIDE},iw)':'min({REF_SIDE},ih)':force_original_aspect_ratio=decrease",
                 "-q:v", "2", "-frames:v", "1", jpg])
            out[key].append(rel(jpg))
    save(work / "refs.json", out)
    print(json.dumps({c: len(v) for c, v in out.items()}))
    return out


# ---------- generation ----------

talk_need = plan_check.talk_need     # plan and build share the talking-clip rules (E95)
talk_fits = plan_check.talk_fits


def retime(piece, params, factor, stem):
    """One line's PCM through ffmpeg atempo (pitch kept): factor > 1 shortens it. The result is cut or padded with
    silence to round(frames / factor), since atempo misses by a few ms (11.7 s -> 11.553 s for 11.55 s) and a line
    retimed to the ceiling would else be refused by it; a miss over RETIME_TRIM_MAX is refused (RETIME_TRIM_OVER).
    16-bit PCM only (lines_step refuses any other voice.wav): the frames come back as pcm_s16le under its params."""
    src, dst = Path(f"{stem}-native.wav"), Path(f"{stem}-retimed.wav")
    write_wav(src, params, piece)
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-af", f"atempo={factor:.5f}", "-ar",
         str(params.framerate), "-ac", str(params.nchannels), "-c:a", "pcm_s16le", dst])
    frames = read_wav(dst)[1]
    width = params.sampwidth * params.nchannels
    want = int(round(len(piece) / width / factor)) * width
    miss = abs(len(frames) - want) / width / params.framerate
    if miss > RETIME_TRIM_MAX:
        raise SystemExit(f"RETIME_TRIM_OVER {Path(stem).name} {miss * 1000:.0f} ms from its target "
                         f"(atempo misses by a few ms; at most {RETIME_TRIM_MAX * 1000:.0f} ms is cut or padded)")
    return frames[:want] + b"\x00" * max(0, want - len(frames))


def vo_after(index, plan):
    """The time a voice-over Keeper clip covers after his line: the gap before the next line, or the closing tail."""
    return TAIL if index == len(plan["shots"]) - 1 else LINE_GAP


def shot_seconds(shot, index, plan, layout):
    if plan_check.voiceover(shot):
        return plan_check.vo_clip_seconds(layout["keeper"][shot["id"]]["seconds"], vo_after(index, plan))
    if not plan_check.talking(shot):
        return shot["seconds"]
    return min(plan_check.TALK_CLIP[1], talk_need(talk_record(layout, shot)["seconds"]))


BOUND_AUDIO = "speaks the words of the audio clip, {pronoun} lips moving in sync with the voice"
UNBOUND_SPEECH = re.compile(r"speaks to the camera, (his|her|its) lips moving clearly with every word")


def speaker_of(shot):
    return ch.NARRATOR if shot["kind"] == "keeper" else shot["speaker"]


def bind_prompt(prompt, who, chars=None):
    """E95: Pavo kept our line in the Keeper's lips only when the prompt named the reference as the speaker ("Image 1
    is the narrator") and tied the speech to the audio clip ("speaks the words of the audio clip, his lips moving in
    sync with the voice"). The plan's "speaks to the camera, his lips moving clearly with every word" is replaced by
    that clause, else the clause is added."""
    chars = chars if chars is not None else ch.registry()
    c = chars.get(who) or {}
    pronoun = c.get("pronoun", "his")
    label = "the narrator" if who == ch.NARRATOR else c.get("name", who)
    clause = BOUND_AUDIO.format(pronoun=pronoun)
    if "Image 1" not in prompt:
        prompt = f"Image 1 is {label}. {prompt}"
    if clause not in prompt:
        if UNBOUND_SPEECH.search(prompt):
            prompt = UNBOUND_SPEECH.sub(clause, prompt, count=1)
        else:
            subject = {"his": "He", "her": "She", "its": "It"}.get(pronoun, "He")
            prompt = f"{prompt.rstrip()} {subject} {clause}."
    return prompt


def request(shot, index, plan, layout, refs, chars=None):
    """The Pavo call for one shot: references from the approved images (<= 5); a talking shot (the Keeper, a character
    speaking) sends its own line as input audio. God's voice-over shot sends none: no one speaks on screen. A
    voice-over Keeper shot (plan B) sends his `talk_refs` frame alone (keeper-vo/calibration.json: with the
    mouth-closed front view the landmarker found his face in 2-27 % of the frames, FACE_NOT_FOUND in 4 of 4; with
    the talking frame, facing the lens, 100 %), no audio and no speech clause."""
    ids = ["keeper"] if shot["kind"] == "keeper" else shot.get("characters", [])
    talks = plan_check.talking(shot)
    prompt = shot["prompt"]
    if talks:   # E95: the speaker is Image 1 and the prompt binds it to the audio clip. Its `talk_refs` speaking frame
        # is sent in place of its approved refs, not before them: the direct Pavo tests that passed (lips 0.578, face
        # 0.98) sent storyteller-ref.jpg alone, and no test sent it beside the mouth-closed front view that failed
        who = speaker_of(shot)
        ids = [who] + [c for c in ids if c != who]
        references = list(refs.get(f"{who}:talk") or refs[who]) + [p for cid in ids[1:] for p in refs[cid]]
        prompt = bind_prompt(prompt, who, chars)
    elif plan_check.voiceover(shot):
        references = list(refs.get(f"{ch.NARRATOR}:talk") or refs[ch.NARRATOR])
    else:
        references = [p for cid in ids for p in refs[cid]]
    if len(references) > ch.MAX_REFS:
        raise SystemExit(f"REFERENCES_OVER_{ch.MAX_REFS} {shot['id']}")
    audios = [talk_record(layout, shot)["wav"]] if talks else []
    return {"prompt": prompt, "seconds": shot_seconds(shot, index, plan, layout),
            "aspect_ratio": plan.get("aspect_ratio", "9:16"), "references": references or None,
            "audios": audios or None, "sound": False}


def submit(client, req, sleep=time.sleep, log=print):
    """One generation. PAVO_RATE_LIMITED and PAVO_UNREACHABLE are raised before any job exists, so that call is sent
    again after a wait (TRANSIENT); every other refusal stops the run. An uncertain submission is never resubmitted:
    its job is read with job()."""
    from client import PavoError
    used = {}
    while True:
        try:
            return client.generate_video(**req)
        except PavoError as exc:
            code = str(exc).split()[0]
            waits = TRANSIENT.get(str(exc))
            n = used.get(code, 0)
            if waits is None or n >= len(waits):
                raise ShotFailed(f"PAVO_REFUSED {code}") from None
            used[code] = n + 1
            log(f"{code}: waiting {waits[n]} s")
            sleep(waits[n])


def wait_job(client, cid, sleep=time.sleep, clock=time.monotonic):
    """completed -> the video, failed/incomplete/timeout -> None. Read errors are retried (the job runs on)."""
    from client import PavoError
    deadline, incomplete = clock() + JOB_TIMEOUT_S, 0
    while clock() < deadline:
        try:
            job = client.job(cid)
        except PavoError as exc:
            if str(exc) in ("PAVO_MEDIA_URL_REFUSED", "PAVO_RESULT_SCHEMA_CHANGED", "PAVO_SESSION_EXPIRED",
                            "PAVO_ACCESS_REFUSED", "PAVO_CREDENTIAL_REQUIRED"):
                raise ShotFailed(f"PAVO_JOB {exc} {cid}") from None
            sleep(POLL_S)
            continue
        if job["status"] == "completed":
            return job["videos"][0]
        if job["status"] == "failed":
            return None
        if job["status"] == "incomplete":
            incomplete += 1
            if incomplete >= INCOMPLETE_POLLS:
                return None
        sleep(POLL_S)
    return None


def attempts_for(shot):
    """E98: generations allowed for one shot; every caller of make_shot passes it, so a talking shot gets 6, and so
    does a voice-over Keeper shot (plan B: 1 pass in 6 direct closed-mouth clips before the probes; Pavo is free)."""
    return TALK_ATTEMPTS if plan_check.talking(shot) or plan_check.voiceover(shot) else ATTEMPTS


def make_shot(shot_id, attempt, check, attempts=ATTEMPTS):
    """attempt(n) -> (record, clip path or None); check(path) -> (flags, measures or None). A failed shot gets a NEW
    generation, at most attempts - 1 times; then the run fails naming the shot. Returns (kept path, records)."""
    records = []
    for n in range(1, attempts + 1):
        record, path = attempt(n)
        if path is not None:
            record["flags"], measures = check(path)
            if measures:
                if "faces" in measures:
                    record["faces"] = measures["faces"]
                elif "still_mouth" in measures:
                    record["still_mouth"] = measures["still_mouth"]
                else:
                    record["lipsync"] = measures
            if not record["flags"]:
                records.append(record)
                return path, records
            # E94: a refused generation is kept beside the shot, so the failure-evidence job can show what failed
            kept = Path(path).with_name(f"{Path(path).stem}-fail{n}{Path(path).suffix}")
            if Path(path).is_file():
                shutil.copyfile(path, kept)
                record["clip"] = kept.name
        else:
            record.setdefault("flags", ["NO_VIDEO"])
        records.append(record)
    failed = ShotFailed(f"SHOT_FAILED {shot_id} after {attempts} generations: "
                        + "; ".join(",".join(r["flags"]) for r in records))
    failed.records = records   # the measures of every attempt reach the report (E94)
    raise failed


def clip_flags(path):
    import clip_check
    return clip_check.check(str(path))["flags"]


def lipsync_flags(lip_python, face_model, clip, wav):
    done = subprocess.run([str(lip_python), "-I", "-B", str(HERE / "lipsync_check.py"), str(clip), str(wav),
                           str(face_model)], capture_output=True, text=True)
    try:
        result = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        # the check itself broke (E89: a missing library): not the clip's fault, so no regeneration is spent on it
        tail = " | ".join(done.stderr.strip().splitlines()[-3:])
        raise SystemExit(f"LIPSYNC_TOOL_BROKEN exit {done.returncode}: {tail[-600:]}")
    return result["flags"], {"audio": result["audio"], "mouth": result["mouth"]}


def face_flags(lip_python, face_model, clip):
    """God's voice-over clip must show no person: the pinned face landmarker on sampled frames (lipsync_check
    --faces). A face found flags GOD_SHOT_FACE (the shot is regenerated); a check that prints no JSON stops the run,
    like LIPSYNC_TOOL_BROKEN (E89), so no regeneration is spent on a broken tool."""
    done = subprocess.run([str(lip_python), "-I", "-B", str(HERE / "lipsync_check.py"), "--faces", str(clip),
                           str(face_model)], capture_output=True, text=True)
    try:
        result = json.loads(done.stdout.strip().splitlines()[-1])
        flags = list(result["flags"])
    except (ValueError, IndexError, KeyError, TypeError):
        tail = " | ".join(done.stderr.strip().splitlines()[-3:])
        raise SystemExit(f"FACE_TOOL_BROKEN exit {done.returncode}: {tail[-600:]}")
    return flags, {"faces": {k: result.get(k) for k in ("frames_sampled", "faces_found")}}


def still_mouth_flags(lip_python, face_model, clip):
    """Plan B: a voice-over Keeper clip shows no talking mouth (lipsync_check --still-mouth: the same landmarker and
    lip opening; MOUTH_TALKING over the calibrated range, FACE_NOT_FOUND under 80 % of frames). A check that prints
    no JSON stops the run (E89): no regeneration is spent on a broken tool."""
    done = subprocess.run([str(lip_python), "-I", "-B", str(HERE / "lipsync_check.py"), "--still-mouth", str(clip),
                           str(face_model)], capture_output=True, text=True)
    try:
        result = json.loads(done.stdout.strip().splitlines()[-1])
        flags = list(result["flags"])
    except (ValueError, IndexError, KeyError, TypeError):
        tail = " | ".join(done.stderr.strip().splitlines()[-3:])
        raise SystemExit(f"STILL_MOUTH_TOOL_BROKEN exit {done.returncode}: {tail[-600:]}")
    return flags, {"still_mouth": {k: result.get(k) for k in ("opening_range", "face_frames", "frames")}}


def risk_order(shots):
    """E99: (plan index, shot) with the shots that can fail first: the talking shots (lipsync_check), then God's
    voice-over shots (no face may appear) and the voice-over Keeper shots (no talking mouth), then the scenes. A
    failure costs minutes, not a whole build."""
    def rank(item):
        shot = item[1]
        return 0 if plan_check.talking(shot) else 1 if plan_check.speaking(shot) or plan_check.voiceover(shot) else 2
    return sorted(enumerate(shots), key=rank)


def in_plan_order(report, plan):
    """The report lists its shots in plan order whatever order they were generated in (risk_order, E99)."""
    shots = report["shots"]
    report["shots"] = {**{s["id"]: shots[s["id"]] for s in plan["shots"] if s["id"] in shots},
                       **{k: v for k, v in shots.items() if k not in {s["id"] for s in plan["shots"]}}}
    return report


def generate_step(plan, work, lip_python, face_model, client=None, download=None, sleep=time.sleep):
    work = Path(work)
    rel(work)
    layout, refs = load(work / "layout.json"), load(work / "refs.json")
    if client is None:
        from video import PavoVideoClient
        client = PavoVideoClient()
    if download is None:
        import pavo_footage
        download = pavo_footage.download
    report_path = work / "report.json"
    report = load(report_path) if report_path.exists() else {}
    report.update(episode=plan["episode"], shots=report.get("shots", {}))
    for index, shot in risk_order(plan["shots"]):
        req = request(shot, index, plan, layout, refs)
        entry = {"kind": shot["kind"], "lines": shot.get("lines"), "request": {k: v for k, v in req.items()}}
        if plan_check.speaking(shot):
            entry.update(speaker=shot["speaker"], line=shot["line"])
        talks = plan_check.talking(shot)
        raw = work / "clips" / f"{shot['id']}-raw.mp4"
        final = work / "clips" / f"{shot['id']}.mp4"
        raw.parent.mkdir(parents=True, exist_ok=True)

        def attempt(n):
            result = submit(client, req, sleep=sleep)
            record = {"generation": n, "conversation_id": result["conversation_id"], "submission": result["status"],
                      "quoted_credits": result.get("quoted_credits")}
            if result["status"] == "rejected":
                return record, None
            video = wait_job(client, result["conversation_id"], sleep=sleep)
            if not video:
                return record, None
            download(video["url"], raw)
            record["source"] = {"width": video.get("width"), "height": video.get("height"),
                                "seconds": video.get("seconds")}
            if not talks:   # Pavo adds an AAC track even with sound false: strip it
                run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", raw, "-an", "-c:v", "copy", final])
            else:           # a talking clip keeps our line as its track for lipsync_check
                shutil.copyfile(raw, final)
            return record, final

        voice_over = plan_check.speaking(shot) and not talks
        still = plan_check.voiceover(shot)

        def check(path):
            flags = clip_flags(path)
            if still:       # plan B: the Keeper on screen, silent; his line plays from the voice track
                more, measures = still_mouth_flags(lip_python, face_model, path)
                return flags + more, measures
            if voice_over:  # God's voice-over shot: no lipsync, but no face may appear in it
                more, measures = face_flags(lip_python, face_model, path)
                return flags + more, measures
            if not talks:   # scenes: no lipsync check
                return flags, None
            more, measures = lipsync_flags(lip_python, face_model, path, REPO / talk_record(layout, shot)["wav"])
            return flags + more, measures

        done = report["shots"].get(shot["id"], {})
        if done.get("attempts") and done.get("request") == entry["request"] and final.exists():
            # E93: a re-run restored from a failed run (episode.yml resume_run) keeps the clips already made, after
            # the same checks again; a changed request (plan, voice, references) is generated anew
            flags, _ = check(final)
            if not flags:
                print(json.dumps({"shot": shot["id"], "resumed": True}))
                continue
        try:
            _, records = make_shot(shot["id"], attempt, check, attempts=attempts_for(shot))
        except (ShotFailed, SystemExit) as exc:
            entry["error"] = str(exc)
            if getattr(exc, "records", None):
                entry["attempts"] = exc.records
            report["shots"][shot["id"]] = entry
            save(report_path, in_plan_order(report, plan))
            raise SystemExit(str(exc))
        entry["attempts"] = records
        report["shots"][shot["id"]] = entry
        save(report_path, in_plan_order(report, plan))
        print(json.dumps({"shot": shot["id"], "generations": len(records)}))
    return report


# ---------- compose ----------

def split_scene(span, members, clip_seconds):
    """Time for each scene shot of one run: establishing shots hold <= 2 s, the rest shares by clip length."""
    est = [m for m in members if m.get("establishing")]
    if len(est) == len(members):
        return [span / len(members)] * len(members)
    hold = min(ESTABLISHING_HOLD, span / len(members))
    rest = span - hold * len(est)
    weight = sum(clip_seconds[m["id"]] for m in members if not m.get("establishing"))
    return [hold if m.get("establishing") else rest * clip_seconds[m["id"]] / weight for m in members]


def cuts(clip, start, end, clip_len):
    """One scene's span cut every <= 4 s. Windows spread over the clip (a jump between them) when it is long enough,
    else contiguous and slowed at most MAX_SLOW."""
    piece = end - start
    n = max(1, math.ceil(piece / CUT_MAX - 1e-9))
    length = piece / n
    out = []
    if n * length <= clip_len:
        step = (clip_len - length) / (n - 1) if n > 1 else 0.0
        for i in range(n):
            out.append({"clip": clip, "start": round(start + i * length, 3), "end": round(start + (i + 1) * length, 3),
                        "src_start": round(min(i * step, clip_len - length), 3), "speed": 1.0})
    else:
        have = clip_len / n
        factor = length / have
        if factor > MAX_SLOW:
            raise SystemExit(f"CLIP_TOO_SHORT {clip} ({clip_len:.2f} s for {piece:.2f} s)")
        for i in range(n):
            out.append({"clip": clip, "start": round(start + i * length, 3), "end": round(start + (i + 1) * length, 3),
                        "src_start": round(i * have, 3), "speed": round(factor, 4)})
    out[-1]["end"] = round(end, 3)
    return out


def compose_shots(plan, layout, clips, clip_seconds):
    """short_engine shots tiling [0, total]. A talking shot (the Keeper, a character speaking) spans exactly its
    line's audio (from its first word to its last), from the start of its clip at normal speed, so the lips meet the
    voice (`talk`: the line's span, checked again by short_engine); it covers the silent gap only when the next shot
    talks too, and the closing one covers the tail; beyond its clip (~0.45 s past the speech, E95) its last frame is
    held (`hold`, <= TALK_HOLD_MAX). Scene runs (God's voice-over shots among them) fill the time between, cut every
    2-4 s."""
    shots, total, lines = plan["shots"], layout["total"], layout["lines"]
    _, carried = plan_check.sequence(plan)
    runs = plan_check.groups(shots, carried)
    out, cursor = [], 0.0
    for r, (a, b, ln) in enumerate(runs):
        last = r == len(runs) - 1
        if plan_check.voiceover(shots[a]):
            # plan B: one unbroken clip of the silent Keeper over his line, from where the shot before ended (his
            # first word, or the gap after a talking shot) to the next line (or the end), from its 0 s; his line is
            # narration in the voice track (captions from the timeline). A clip shorter than that is slowed at most
            # MAX_SLOW, never cut or held
            s = shots[a]
            end = total if last else lines[runs[r + 1][2][0]]["start"]
            span = end - cursor
            factor = max(1.0, span / clip_seconds[s["id"]])
            if factor > MAX_SLOW + 1e-9:
                raise SystemExit(f"KEEPER_CLIP_SHORT {s['id']} ({clip_seconds[s['id']]:.2f} s for {span:.2f} s, slowed "
                                 f"at most {MAX_SLOW})")
            out.append({"clip": clips[s["id"]], "start": round(cursor, 3), "end": round(end, 3), "src_start": 0.0,
                        "speed": round(factor, 4) if factor > 1.0 else 1.0, "shot": s["id"], "kind": "keeper-vo"})
            cursor = end
            continue
        if plan_check.talking(shots[a]):
            s = shots[a]
            kind = "keeper" if s["kind"] == "keeper" else "speaker"
            start, end = lines[ln[0]]["start"], lines[ln[-1]]["end"]
            talk = {"start": round(start, 3), "end": round(end, 3)}
            if abs(start - cursor) > 1e-3:
                raise SystemExit(f"{kind.upper()}_NOT_ON_HIS_LINE {s['id']}")
            if last:
                end = total
            elif plan_check.talking(shots[runs[r + 1][0]]):
                end = lines[runs[r + 1][2][0]]["start"]   # covers the silent gap before the next talking line
            # E95: the clip is only ~0.45 s longer than the speech; the gap or the closing tail beyond it is its last
            # frame held (at most TALK_HOLD_MAX; the closing fade-out covers the tail)
            hold = max(0.0, (end - start) - clip_seconds[s["id"]])
            # the hold is written HOLD_MARGIN longer than the time it covers, and short_engine checks that written
            # value against HOLD_MAX, so it is the one checked here (review of #408: else CLIP_TOO_SHORT later)
            held = round(hold + HOLD_MARGIN, 3) if hold > 1e-3 else 0.0
            if held > plan_check.TALK_HOLD_MAX or clip_seconds[s["id"]] + 1e-3 < talk["end"] - talk["start"]:
                raise SystemExit(f"{kind.upper()}_CLIP_SHORT {s['id']} ({clip_seconds[s['id']]:.2f} s for "
                                 f"{end - start:.2f} s, a hold of at most {plan_check.TALK_HOLD_MAX} s)")
            shot_out = {"clip": clips[s["id"]], "start": round(start, 3), "end": round(end, 3), "src_start": 0.0,
                        "speed": 1.0, "shot": s["id"], "kind": kind, "talk": talk}
            if held:
                shot_out["hold"] = held
            out.append(shot_out)
            cursor = end
            continue
        end = total if last else lines[runs[r + 1][2][0]]["start"]
        members = shots[a:b + 1]
        t = cursor
        for m, share in zip(members, split_scene(end - cursor, members, clip_seconds)):
            for c in cuts(clips[m["id"]], t, t + share, clip_seconds[m["id"]]):
                out.append(dict(c, shot=m["id"], kind="scene"))
            t += share
        out[-1]["end"] = round(end, 3)
        cursor = end
    return out


def measure_lufs(path):
    done = subprocess.run(["ffmpeg", "-nostdin", "-v", "info", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                          capture_output=True, text=True)
    found = re.findall(r"I:\s+(-?[0-9.]+) LUFS", done.stderr)
    return float(found[-1]) if found else None


def compose_step(plan, work, music, out):
    import clip_check
    import short_engine
    work = Path(work)
    layout = load(work / "layout.json")
    clips = {s["id"]: str(work / "clips" / f"{s['id']}.mp4") for s in plan["shots"]}
    seconds = {k: short_engine.duration(v) for k, v in clips.items()}
    shots = compose_shots(plan, layout, clips, seconds)
    compose_plan = {"voice": str(work / "narration.wav"), "timeline": str(work / "compose-timeline.json"),
                    "music": str(music), "music_offset": float(plan.get("music_offset", 600.0)), "tail": TAIL,
                    "shots": shots}
    save(work / "compose-plan.json", compose_plan)
    short_engine.main(str(work / "compose-plan.json"), str(out))
    runs = clip_check.black_runs(str(out))
    length = clip_check.probe(str(out))["seconds"]
    dip = round(layout["total"] - FADE_OUT, 2)
    unexpected = clip_check.unexpected(runs, [dip], length)
    lufs = measure_lufs(out)
    total = layout["total"]
    establishing = sum(c["end"] - c["start"] for c in shots
                       if any(s["id"] == c["shot"] and s.get("establishing") for s in plan["shots"]))
    report_path = work / "report.json"
    report = load(report_path) if report_path.exists() else {"episode": plan["episode"], "shots": {}}
    report["composed"] = {
        "output_sha256": sha256(out), "seconds": round(length, 2), "frame": [short_engine.W, short_engine.H],
        "black_check": {"black_starts": runs, "unexpected": unexpected, "intended_dips": [dip]},
        "lufs": lufs, "keeper_share": layout["keeper_share"], "lesson_share": layout.get("lesson_share"),
        "spoken": {**layout.get("speakers", {}), **layout.get("voice_over", {})},
        "establishing_share": round(establishing / total, 3),
        "cuts": len(shots), "timeline": [{k: c[k] for k in ("shot", "kind", "start", "end", "src_start", "speed")}
                                         for c in shots]}
    save(report_path, report)
    problems = []
    if unexpected:
        problems.append(f"BLACK_FRAMES {unexpected}")
    if lufs is None or not LUFS[0] <= lufs <= LUFS[1]:
        problems.append(f"LOUDNESS {lufs} LUFS (-14 +-1)")
    if report["composed"]["establishing_share"] > plan_check.ESTABLISHING_SHARE_MAX:
        problems.append("ESTABLISHING_SHARE")
    print(json.dumps({k: report["composed"][k] for k in ("output_sha256", "seconds", "lufs", "keeper_share", "cuts")}))
    if problems:
        raise SystemExit("COMPOSE_REFUSED " + "; ".join(problems))
    return report


def sheet_step(video, sheet, frames=20):
    import short_engine
    d = short_engine.duration(video)
    tmp = Path(sheet).parent / "sheet-frames"
    tmp.mkdir(parents=True, exist_ok=True)
    for k in range(frames):
        t = d * (k + 0.5) / frames
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", "-vf",
             f"scale=216:384,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{t:.1f}s':"
             "x=6:y=6:fontsize=16:fontcolor=yellow:box=1:boxcolor=black@0.6", tmp / f"f{k:02d}.jpg"])
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", tmp / "f%02d.jpg", "-vf", "tile=5x4", "-frames:v", "1",
         "-q:v", "3", sheet])
    shutil.rmtree(tmp)


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    cmd = argv[1]
    if cmd == "sheet" and len(argv) == 4:
        return sheet_step(argv[2], argv[3])
    plan = load(argv[2])
    result = plan_check.check(plan)
    if result["problems"] or result["pending"]:
        raise SystemExit("PLAN_REFUSED " + "; ".join(result["problems"] + result["pending"]))
    if cmd == "voice-script" and len(argv) == 4:
        save(Path(argv[3]) / "voice-script.json", voice_script(plan))
    elif cmd == "lines" and len(argv) == 4:
        lines_step(plan, argv[3])
    elif cmd == "refs" and len(argv) == 4:
        refs_step(plan, argv[3])
    elif cmd == "generate" and len(argv) == 6:
        if not os.environ.get("PAVO_TOKEN"):
            raise SystemExit("PAVO_CREDENTIAL_REQUIRED")
        generate_step(plan, argv[3], argv[4], argv[5])
    elif cmd == "compose" and len(argv) == 6:
        compose_step(plan, argv[3], argv[4], argv[5])
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
