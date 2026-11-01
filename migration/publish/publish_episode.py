#!/usr/bin/env python3
"""Publish one Bible-series episode (owner, 2026-10-24: Bible stories from Genesis, one at a time; Shorts first).

The episode record (migration/production/bible/episodes/<id>.json) holds the metadata and the hash of the exact file.
Idempotent like publish_video: the ledger maps "bible:<id>:<sha256>" -> video_id, an existing key is never uploaded
again and a re-run only finishes missing steps. Public at once, or private with publishAt. AI scenes and voice are
declared (containsSyntheticMedia). From part 9 the thumbnail is the one approved in bible/thumbs/<id>.json (owner, 27/10:
the story character, reviewed before publish): any other is THUMB_NOT_APPROVED here and in check-record, never a
rework after the upload.
usage: publish_episode.py EPISODE_JSON VIDEO LEDGER RECEIPT [PUBLISH_AT_ISO]
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_video as pv  # noqa: E402

TITLE_MAX = 100
DESCRIPTION_MAX = 4900   # YouTube allows 5,000


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


SHORT_RULES_FROM_PART = 6      # owner, 2026-10-25: from Genesis 6 on (what is published stays as it is)
SHORT_LENGTH_FROM_PART = 7     # owner, 2026-10-26 (structure bible-story-short: 5/6 winners ran 170-179 s, 0/3 weak)
SHORT_MIN_S, SHORT_MAX_S = 170.0, 179.0   # measured with the tail; YouTube Shorts end at 180 s
SHORTS_LIMIT_S = 180.0
SHORT_PART6_S = (62.0, 90.0)   # part 6 as published (TikTok Creator Rewards counts 1 min or more; 2 s of margin)
ORIGINAL_MIN = 0.40            # share of narration words that are ours (not the KJV quotation)
INSIGHT_MIN_WORDS = 20
CTA_TO_LONG = re.compile(r"(?i)\b(full|whole|complete) (story|video)\b|\blong video\b")


def short_length(part):
    """(min, max) seconds of a Short of this part: 170-179 s from part 7, 62-90 s for part 6 (kept as published)."""
    return (SHORT_MIN_S, SHORT_MAX_S) if part >= SHORT_LENGTH_FROM_PART else SHORT_PART6_S


# E259 (owner, 2026-11-01, DECISIONS.md "Long-first, Shorts cut from the long"): a record with "track": "buzzy-cut"
# is a 9:16 Short cut from a long-first long (short_cuts.py): a coherent unit of the long's own sentences, 20-179 s,
# never starting or ending inside speech (checked by short_cuts.py on the long's timeline), linking its parent long
# (`parent`). Its words keep the Short's originality share; the 170-179 s band, the 20-word insight and the spoken CTA
# belong to a whole Short episode, so a cut points to the full story in its description instead. Its review is the
# buzzy defect gate on the cut's own master, with the Buzzy shot and the revocations of its parent long.
CUT_TRACK = "buzzy-cut"
CUT_SECONDS = (20.0, 179.0)


def cut_problems(episode):
    out = []
    parent = episode.get("parent")
    if not (isinstance(parent, dict) and isinstance(parent.get("long"), str) and parent["long"]
            and isinstance(parent.get("pilot"), str) and re.fullmatch(r"pilot-\d{3}", parent["pilot"])
            and isinstance(parent.get("clean_master_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", parent["clean_master_sha256"])):
        out.append("CUT_PARENT_MISSING (parent: long, pilot, clean_master_sha256)")
    elif parent["long"] == episode.get("id"):
        out.append("CUT_PARENT_IS_ITSELF")
    if episode.get("format") != "short":
        out.append("CUT_NOT_A_SHORT")
    seconds = episode.get("seconds")
    if type(seconds) not in (int, float) or not CUT_SECONDS[0] <= seconds <= CUT_SECONDS[1]:
        out.append(f"CUT_LENGTH {seconds} s (need {CUT_SECONDS[0]:.0f}-{CUT_SECONDS[1]:.0f})")
    lines = episode.get("narration") or []
    if not lines:
        return out + ["NARRATION_MISSING (the cut's lines, kind scripture/story/insight/cta)"]
    words = {k: sum(len(x.get("text", "").split()) for x in lines if x.get("kind") == k)
             for k in ("scripture", "story", "insight", "cta")}
    total = sum(words.values())
    if total and (total - words["scripture"]) / total < ORIGINAL_MIN:
        out.append(f"ORIGINAL_SHARE {(total - words['scripture']) / total:.2f} < {ORIGINAL_MIN}")
    if not CTA_TO_LONG.search(episode.get("description", "")):
        out.append("CUT_DESCRIPTION_NOT_TO_THE_LONG (the description sends the viewer to the full story)")
    return out


def short_problems(episode):
    """Owner, 2026-10-25: Shorts of 1 minute or more with a strong layer of originality, authenticity, critique and a
    clear direction to the long video, so neither TikTok nor YouTube can read them as reused or unoriginal content.
    The narration is recorded line by line: kind scripture (KJV, checked by kjv_check), story (our retelling),
    insight (our own observation or critique of the passage), cta (where to go next)."""
    if episode.get("track") == CUT_TRACK:   # E259: a cut of a long-first long has its own rules (cut_problems)
        return cut_problems(episode)
    if episode.get("format") != "short" or episode.get("part", 0) < SHORT_RULES_FROM_PART:
        return []
    out = []
    low, high = short_length(episode.get("part", 0))
    if not low <= episode.get("seconds", 0) <= high:
        out.append(f"SHORT_LENGTH {episode.get('seconds')} s (need {low:.0f}-{high:.0f})")
    lines = episode.get("narration") or []
    if not lines:
        return out + ["NARRATION_MISSING (kind scripture/story/insight/cta, line by line)"]
    words = {k: sum(len(x.get("text", "").split()) for x in lines if x.get("kind") == k)
             for k in ("scripture", "story", "insight", "cta")}
    total = sum(words.values())
    if total and (total - words["scripture"]) / total < ORIGINAL_MIN:
        out.append(f"ORIGINAL_SHARE {(total - words['scripture']) / total:.2f} < {ORIGINAL_MIN}")
    if not any(x.get("kind") == "insight" and len(x.get("text", "").split()) >= INSIGHT_MIN_WORDS for x in lines):
        out.append(f"INSIGHT_MISSING (one line of our own observation or critique, >= {INSIGHT_MIN_WORDS} words)")
    cta = " ".join(x.get("text", "") for x in lines if x.get("kind") == "cta")
    if not CTA_TO_LONG.search(cta):
        out.append("CTA_NOT_TO_THE_LONG (the close sends the viewer to the full story)")
    return out


def description_problems(description):
    """The rules every episode description keeps, at upload and after any later edit (arc_links.py)."""
    out = []
    if len(description) > DESCRIPTION_MAX:
        out.append("DESCRIPTION_LENGTH")
    if "(public domain)" not in description or "AI" not in description:
        out.append("DISCLOSURE_MISSING")   # KJV source and AI disclosure are always stated
    return out


THUMB_FROM_PART = 9   # owner, 2026-10-27: the approved character thumbnail (what is published stays as it is)
THUMBS_CODE = Path(__file__).resolve().parents[1] / "production" / "bible"


def thumbs():
    """bible/thumbs.py, imported when first needed (plan_check imports this module)."""
    if str(THUMBS_CODE) not in sys.path:
        sys.path.insert(0, str(THUMBS_CODE))
    import thumbs as t
    return t


def thumb_required(episode):
    return episode.get("part", 0) >= THUMB_FROM_PART


def thumb_problems(episode):
    """From part 9: the approved thumbnail of this episode, its spec unchanged and its image the approved one; every
    reason is THUMB_NOT_APPROVED (or the spec's own code), named in check-record before publish-episode.yml runs."""
    if not thumb_required(episode):
        return []
    return thumbs().publish_problems(episode["id"], episode.get("format", "short"))


# E235: the Short publish route never read the review. A record now carries the review of THIS master by a
# designated Short reviewer at the owner floor, or it is refused (fail-closed; the score is never produced here).
SHORT_REVIEWERS = ("claude-session-reviewer", "gemini-3.8-flash")
SHORT_FLOOR = 9.5
# E242 (owner, 2026-10-31, PR #599): a record with "track": "buzzy" (Short made with Buzzy clips) is reviewed at
# overall 8.0 with every rubric item >= 7 (review.scores); the default track keeps 9.5. Reviewer, sha binding, issues,
# hard refusals and frozen QA are the same on both tracks.
# E250 (owner, 2026-11-01, DECISIONS.md): the buzzy track is gated on defects, not scores. The native review is a defect
# finder; the record carries review.publish_decision {"decision": "publish", "by": "claude-session-reviewer", "note"}
# and review.defects [{"issue": index, "category": "a".."f"|"info", "resolved": bool}]. Categories a (speech cut off),
# b (scene does not fit its line / story order) and e (policy) refuse while unresolved. Every other track keeps 9.5.
BUZZY_TRACKS = ("buzzy",)
BUZZY_BLOCKING = ("a", "b", "e")
BUZZY_CATEGORIES = ("a", "b", "c", "d", "e", "f", "info")
BUZZY_DECIDER = "claude-session-reviewer"
RUBRIC = ("opening_and_promise", "picture_quality", "figure_and_background_integrity", "captions_readable_and_synced",
          "audio_clarity_and_mix", "pacing_and_visual_variety", "scripture_on_screen", "policy_safe")


BUZZY_LEDGER = Path(__file__).resolve().parents[1] / "evidence" / "buzzy" / "ledger.json"


def buzzy_shot_problems(episode, shots_dir=None, ledger=None):
    """E242: track buzzy lowers the floor only for an episode that really contains Buzzy video: an approved shot of
    bible/shots/<id>.json with source "buzzy" whose task_id is a call recorded in evidence/buzzy/ledger.json."""
    path = Path(shots_dir or THUMBS_CODE / "shots") / f"{episode.get('id')}.json"
    try:
        shots = (json.loads(path.read_text()).get("shots") or {}) if path.is_file() else {}
        calls = json.loads(Path(ledger or BUZZY_LEDGER).read_text()).get("calls") or []
    except (OSError, ValueError, AttributeError):
        return ["TRACK_BUZZY_WITHOUT_BUZZY_SHOT"]
    known = {c.get("task_id") for c in calls if isinstance(c, dict) and c.get("task_id")}
    if any(isinstance(a, dict) and a.get("source") == "buzzy" and a.get("task_id") in known for a in shots.values()):
        return []
    return ["TRACK_BUZZY_WITHOUT_BUZZY_SHOT"]


def buzzy_decision_problems(review):
    """E250: the buzzy gate. A designated reviewer's publish decision with a note, and no unresolved cut-off speech (a),
    scene/story-order mismatch (b) or policy problem (e). Scores are information and gate nothing."""
    out = []
    decision = review.get("publish_decision")
    if not (isinstance(decision, dict) and decision.get("decision") == "publish"
            and decision.get("by") == BUZZY_DECIDER
            and isinstance(decision.get("note"), str) and decision["note"].strip()):
        out.append("REVIEW_DECISION_MISSING")
    issues = review.get("issues") if isinstance(review.get("issues"), list) else []
    defects = review.get("defects")
    if not isinstance(defects, list) or not all(
            isinstance(d, dict) and d.get("category") in BUZZY_CATEGORIES and type(d.get("resolved")) is bool
            and type(d.get("issue")) is int and 0 <= d["issue"] < len(issues) for d in defects):
        return out + ["REVIEW_DEFECTS_INVALID"]
    if any(d["category"] in BUZZY_BLOCKING and not d["resolved"] for d in defects):
        out.append("REVIEW_DEFECT_UNRESOLVED")
    classified = {d["issue"] for d in defects}
    if len(classified) != len(defects) or classified != set(range(len(issues))):
        out.append("REVIEW_DEFECTS_INVALID")   # every listed issue is classified exactly once
    return out


def review_problems(episode, shots_dir=None, ledger=None):
    review = episode.get("review")
    if not isinstance(review, dict):
        return ["REVIEW_MISSING"]
    out = []
    track = episode.get("track")
    if track is not None and track not in BUZZY_TRACKS + (CUT_TRACK,):
        out.append("TRACK_UNKNOWN")
    if track in BUZZY_TRACKS:
        out += buzzy_shot_problems(episode, shots_dir, ledger) + buzzy_decision_problems(review)
    elif track == CUT_TRACK:   # E259: the defect gate on the cut's own master; the Buzzy shot is its parent long's
        out += buzzy_shot_problems({"id": parent_of(episode)}, shots_dir, ledger) + buzzy_decision_problems(review)
    else:
        overall = review.get("overall")
        if isinstance(overall, bool) or not isinstance(overall, (int, float)) or not SHORT_FLOOR <= overall <= 10:
            out.append("REVIEW_BELOW_FLOOR")
    if review.get("reviewer") not in SHORT_REVIEWERS:
        out.append("REVIEW_REVIEWER_NOT_DESIGNATED")
    if review.get("output_sha256") != episode.get("output_sha256"):
        out.append("REVIEW_NOT_FOR_THIS_FILE")
    if not isinstance(review.get("issues"), list):
        out.append("REVIEW_ISSUES_MISSING")
    return out


def problems(episode, video=None):
    """Everything EPISODE_REFUSED names. video None: the record alone (episode_build.py check-record runs this before
    publish-episode.yml is dispatched, E106); the upload always passes the file, so its sha256 is checked there."""
    out = short_problems(episode) + thumb_problems(episode)
    if not episode.get("video_id"):   # a record already published resumes its own upload; it is never re-reviewed
        out += review_problems(episode)
    if episode.get("id"):
        # E189: re-read explicit retractions at upload, not only when the master was built.
        if str(THUMBS_CODE) not in sys.path:
            sys.path.insert(0, str(THUMBS_CODE))
        import episode_build
        out += episode_build.revocation_problems(episode["id"])
        out += attribution_problems(episode)
        if episode.get("track") == CUT_TRACK and parent_of(episode):   # E259: the cut shows its parent long's shots
            out += episode_build.revocation_problems(parent_of(episode))
            out += attribution_problems(dict(episode, id=parent_of(episode)))
    if video is not None and sha256_file(video) != episode["output_sha256"]:
        out.append("OUTPUT_SHA256_MISMATCH")
    if not 0 < len(episode["title"]) <= TITLE_MAX:
        out.append("TITLE_LENGTH")
    return out + description_problems(episode["description"])


def parent_of(episode):
    parent = episode.get("parent")
    return parent.get("long") if isinstance(parent, dict) and isinstance(parent.get("long"), str) else None


def attribution_problems(episode, shots_dir=None):
    """E237: a CC-BY / CC-BY-SA public still approved for a shot of this episode (bible/shots/<id>.json, its
    `attribution`) is credited word for word in the description, or the record is refused (ATTRIBUTION_MISSING)."""
    path = Path(shots_dir or THUMBS_CODE / "shots") / f"{episode['id']}.json"
    shots = (json.loads(path.read_text()).get("shots") or {}) if path.is_file() else {}
    return [f"ATTRIBUTION_MISSING {sid} ({a['attribution']!r} is not in the description)"
            for sid, a in sorted(shots.items()) if isinstance(a, dict) and a.get("attribution")
            and str(a["attribution"]) not in episode.get("description", "")]


def record_video_id(episode_path, episode, vid):
    """E140: the episode record carries the id of the video published from it (live_intel and the daily pass read it
    there); publish-episode.yml commits the record with the ledger. A record naming another video is refused."""
    if episode.get("video_id") == vid:
        return
    if episode.get("video_id"):
        raise SystemExit(f"EPISODE_VIDEO_ID_MISMATCH record {episode['video_id']}, ledger {vid}")
    episode["video_id"] = vid
    Path(episode_path).write_text(json.dumps(episode, indent=1, ensure_ascii=False) + "\n")


def main(episode_path, video, ledger_path, receipt_path, publish_at=None):
    episode = json.loads(Path(episode_path).read_text())
    bad = problems(episode, video)
    if bad:
        raise SystemExit("EPISODE_REFUSED " + " ".join(bad))
    ledger_path = Path(ledger_path)
    ledger = json.loads(ledger_path.read_text())
    key = f"bible:{episode['id']}:{episode['output_sha256']}"
    entry = ledger["entries"].get(key, {"steps": {}})
    s = pv.session()
    if [c["id"] for c in pv.check(s.get(pv.API + "channels", params={"part": "id", "mine": "true"}), "CHANNEL")["items"]] != [pv.CHANNEL]:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")

    def save():
        ledger["entries"][key] = entry
        ledger_path.write_text(json.dumps(ledger, indent=1) + "\n")
    if "video_id" not in entry:
        status = {"privacyStatus": "private" if publish_at else "public", "selfDeclaredMadeForKids": False,
                  "embeddable": True, "license": "youtube", "publicStatsViewable": True, "containsSyntheticMedia": True}
        if publish_at:
            status["publishAt"] = publish_at
        body = {"snippet": {"title": episode["title"], "description": episode["description"], "tags": episode["tags"],
                            "categoryId": episode.get("category_id", "29"), "defaultLanguage": "en",
                            "defaultAudioLanguage": "en"}, "status": status}
        entry.update({"video_id": pv.upload(s, video, body)["id"], "uploaded_at": datetime.now(timezone.utc).isoformat()})
        save()   # durable before any further step
    vid = entry["video_id"]
    record_video_id(episode_path, episode, vid)
    if thumb_required(episode) and not entry["steps"].get("thumbnail"):
        image = thumbs().approved_image(episode["id"])
        bad = thumbs().publish_problems(episode["id"], episode.get("format", "short"), image)
        if bad:   # checked again on the exact bytes uploaded
            raise SystemExit("THUMB_NOT_APPROVED " + "; ".join(bad))
        pv.check(s.post(pv.UPLOAD + "thumbnails/set", params={"videoId": vid}, data=image.read_bytes(),
                        headers={"Content-Type": "image/jpeg"}), "THUMBNAIL")
        entry["steps"]["thumbnail"] = True
        save()
    if episode.get("first_comment") and not pv.comment_done(entry["steps"].get("first_comment")):
        entry["steps"]["first_comment"] = pv.first_comment(s, vid, episode["first_comment"])
        save()
    final = pv.check(s.get(pv.API + "videos", params={"part": "status,snippet", "id": vid}), "VERIFY")["items"][0]
    receipt = {"version": "publish-receipt-v1", "key": key, "video_id": vid, "url": f"https://youtube.com/shorts/{vid}",
               "channel_id": final["snippet"]["channelId"], "title": final["snippet"]["title"],
               "privacy": final["status"]["privacyStatus"], "publish_at": final["status"].get("publishAt"),
               "upload_status": final["status"].get("uploadStatus"), "steps": entry["steps"],
               "verified_at": datetime.now(timezone.utc).isoformat()}
    Path(receipt_path).write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main(*sys.argv[1:6])
