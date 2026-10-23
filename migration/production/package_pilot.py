#!/usr/bin/env python3
"""Publication package for a QA-passed pilot: title, description with every
Creative Commons attribution, tags and a 1280x720 thumbnail. Writes files only;
no upload. Packaging promise must match the opening (archetype rule)."""
import json
import re
from pathlib import Path
import subprocess
import sys
import unicodedata

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def escape(text):
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")


FIRST_COMMENT_MAX = 300  # owner rule for the channel's first comment (stage 5)
# content rules (stage 3): no fear-bait, no health or wealth promise; a conservative phrase list, not a critique
FIRST_COMMENT_BANNED = ("before it's too late", "don't scroll", "do not scroll", "don't ignore", "do not ignore",
                        "or else", "curse", "bad luck", "warning", "guarantee", "will be healed", "healing is yours",
                        "money", "wealth", "riches", "breakthrough is coming", "you will receive")


def check_first_comment(text):
    """One plain comment: non-empty, at most 300 characters, no emoji or pictographs."""
    text = (text or "").strip()
    if not text or len(text) > FIRST_COMMENT_MAX:
        raise SystemExit(f"FIRST_COMMENT_INVALID length {len(text)} (1-{FIRST_COMMENT_MAX})")
    bad = [c for c in text if unicodedata.category(c) == "So" or 0x1F000 <= ord(c) <= 0x1FAFF or c in "\ufe0f\u200d"]
    if bad:
        raise SystemExit("FIRST_COMMENT_INVALID emoji or symbol " + repr("".join(bad)))
    hit = [w for w in FIRST_COMMENT_BANNED if w in text.lower().replace("\u2019", "'")]
    if hit:
        raise SystemExit("FIRST_COMMENT_INVALID fear or promise wording " + ", ".join(hit))
    return text


def default_first_comment(title):
    """From the title's promise (the part after "|", else the whole title): one sentence inviting "Amen" and one
    mercy from today. No emoji, no fear, no promise beyond the title's own words."""
    promise = (title.split("|", 1)[1] if "|" in title else title).strip().rstrip(".!?,;: ")
    generic = 'If this prayer spoke to you, write "Amen" below and share one mercy God showed you today.'
    if promise:
        try:  # a title phrase that breaks a comment rule falls back to the plain invitation
            return check_first_comment(f'If "{promise}" spoke to you, write "Amen" below and share one mercy God showed you today.')
        except SystemExit:
            pass
    return check_first_comment(generic)


def first_comment_for(script):
    """The script's own first_comment wins; otherwise the default built from the title's promise."""
    if script.get("first_comment"):
        return check_first_comment(script["first_comment"])
    return default_first_comment(script["working_title"])


def opening_chapter(script):
    """Use the spoken greeting, never guess a daypart from publication time."""
    hook = next((s for s in script.get("segments", []) if s.get("id") == "hook"), {})
    if hook.get("chapter"):
        return hook["chapter"]
    text = hook.get("text", "").strip()
    for greeting in ("Good morning", "Good evening"):
        if re.match(re.escape(greeting) + r"(?:\b|$)", text, re.IGNORECASE):
            return greeting
    return "Opening prayer"


def chapters_from_script(script, timeline):
    """Chapters at the opening, prayer and blessing turns and at every segment the script names. R15 (algorithm study
    2026-10-23: Bible references in the description lowered the odds of a hit to x0.33, p=0.007): a chapter is never
    a bare reference, and a reference in parentheses is dropped from its name."""
    named = {"hook": opening_chapter(script), "transition": "Let us pray", "declaration": "Declaration for today",
             "payoff": "One thing to do today", "blessing": "Blessing"}
    named.update({s["id"]: s["chapter"] for s in script["segments"] if s.get("chapter")})  # the script's own chapter names win
    rows = []
    for seg in timeline:
        label = SCRIPTURE_REF_IN_LABEL.sub("", named.get(seg["id"]) or "").strip()  # R15: no Bible references
        if label:
            start = 0 if seg["id"] == "hook" else int(seg["start"])
            rows.append(f"{start // 60}:{start % 60:02d} {label}")
    return rows


def chapters(timeline):
    names = {"hook": "Opening prayer", "scripture-1": "He goes before you (Deuteronomy 31:8)",
             "scripture-2": "New mercy every morning (Lamentations 3:22-23)",
             "scripture-3": "Show me the way (Psalm 143:8)", "transition": "Let us pray",
             "scripture-4": "Fear not (Isaiah 41:10)", "declaration": "Declaration for today",
             "payoff": "One thing to do today", "blessing": "Blessing"}
    rows = []
    for seg in timeline:
        if seg["id"] in names:
            start = 0 if seg["id"] == "hook" else int(seg["start"])
            rows.append(f"{start // 60}:{start % 60:02d} {SCRIPTURE_REF_IN_LABEL.sub('', names[seg['id']])}")
    return rows


# R15: "Psalm 23:1", "1 John 4:18", "Isaiah 40:31", "Psalm 23" in the description lowered the odds of a hit
SCRIPTURE_REF = re.compile(r"\b(?:[1-3] )?[A-Z][a-z]+ \d+:\d+|\b(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|Samuel|Kings|Chronicles|Ezra|Nehemiah|Esther|Job|Psalms?|Proverbs|Ecclesiastes|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|Romans|Corinthians|Galatians|Ephesians|Philippians|Colossians|Thessalonians|Timothy|Titus|Philemon|Hebrews|James|Peter|Jude|Revelation) \d+", re.UNICODE)
SCRIPTURE_REF_IN_LABEL = re.compile(r"\s*\((?:[1-3] )?[A-Z][a-z]+ \d+(?::\d+(?:-\d+)?)?(?: \(KJV\))?\)")
SUBSCRIBE_LINE = "Subscribe and pray with us every morning and every night."  # R15: hit odds x3.27 (p=0.014)
# R16 (thumbnail study 2026-10-23, 806 thumbnails in 89 channel-month strata, algorithm_study/thumbs): saturated
# thumbnails were dead x0.29 as often (p = 0.003) and blue-dominant ones broke out x0.26 as often (p = 0.008). The
# breakouts' contact sheet shows one style: warm golden light and huge bold text across the whole frame, the search
# phrase on top ("NIGHT PRAYER", "Morning prayer"), the hook below; the dead sheet shows dark, cool, desaturated frames
# with thin small text.
THUMB_GRADE = ("scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
               "colorbalance=rs=0.12:gs=0.03:bs=-0.12:rm=0.08:gm=0.02:bm=-0.08:rh=0.05:bh=-0.05,"
               "eq=brightness=0.03:contrast=1.08:saturation=1.6")
THUMB_WIDTH = 1200        # text spans the frame (1280 px) with a 40 px margin
THUMB_CHAR_EM = 0.78      # DejaVu Sans Bold upper-case advance plus the border, in em (0.66 overflowed "YOUR CARES")


def thumbnail_lines(th):
    """Search phrase on top in gold, then the hook lines in white, each sized to the full width (capped)."""
    rows = [(th["sub"].upper(), "0xFFD23F", 100)] + [(t.upper(), "white", 175) for t in th["lines"]]
    sized = [(t, c, min(cap, int(THUMB_WIDTH / (THUMB_CHAR_EM * max(len(t), 1))))) for t, c, cap in rows]
    total = sum(int(sz * 1.05) for _, _, sz in sized)
    y, out = max(20, (720 - total) // 2), []
    for t, c, sz in sized:
        out.append((t, sz, c, y))
        y += int(sz * 1.05)
    return out


def warmth(path):
    """Chroma means from ffmpeg: Cr above Cb is warm (amber, gold), Cb above Cr is blue; plus mean saturation."""
    out = subprocess.run(["ffprobe", "-v", "error", "-f", "lavfi", "-i", f"movie={path},scale=320:180,signalstats",
                          "-show_entries", "frame_tags=lavfi.signalstats.UAVG,lavfi.signalstats.VAVG,lavfi.signalstats.SATAVG",
                          "-of", "json"], check=True, capture_output=True, text=True).stdout
    t = json.loads(out)["frames"][0]["tags"]
    return float(t["lavfi.signalstats.VAVG"]) - float(t["lavfi.signalstats.UAVG"]) + 0.5 * float(t["lavfi.signalstats.SATAVG"])


def warmest(stills):
    """R16: blue-dominant thumbnails broke out x0.26 as often; no grade turns a blue night frame warm, so pick the frame."""
    return max(stills, key=warmth)


def thumbnail_filter(th):
    draw = ",".join(f"drawtext=fontfile={FONT}:text='{escape(t)}':fontsize={sz}:fontcolor={c}:"
                    f"borderw={max(6, sz // 14)}:bordercolor=black:shadowx=4:shadowy=4:shadowcolor=black@0.6:"
                    f"x=(w-text_w)/2:y={y}" for t, sz, c, y in thumbnail_lines(th))
    return THUMB_GRADE + "," + draw


DESCRIPTION_MAX = 4900  # YouTube's limit is 5,000 characters
SOURCE_NAMES = {"pixabay": "Pixabay", "pexels": "Pexels", "commons": "Wikimedia Commons"}


def footage_credits(clips, with_authors=True):
    """E52: 85 one-line credits made a 7,577-character description. CC BY clips keep their own attribution line
    (the licence requires it); clips whose licence needs no attribution (Pixabay, Pexels, CC0, public domain) are
    credited once per source, with their authors when there is room."""
    lines = ["Footage credits:"]
    lines += ["• " + c["credit"] for c in clips if (c.get("licence") or "").startswith("CC BY")]
    groups = {}
    for c in clips:
        if not (c.get("licence") or "").startswith("CC BY"):
            groups.setdefault((SOURCE_NAMES.get(c.get("source"), c.get("source") or "licensed source"), c["licence"]),
                              []).append(c.get("author") or "")
    for (source, licence), authors in sorted(groups.items()):
        names = ", ".join(sorted({a for a in authors if a}))
        lines.append(f"• {len(authors)} clips via {source} ({licence})" + (f": {names}" if with_authors and names else ""))
    return lines


def main(work, script_path, out_dir):
    work, out = Path(work), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    script = json.loads(Path(script_path).read_text())
    manifest = json.loads((work / "manifest.json").read_text())
    title = script["working_title"]
    v2 = manifest.get("version") == "pilot-manifest-v2"
    credits = "\n".join("• " + c["attribution"] for c in manifest["clips"] if c.get("attribution"))
    visuals = ([script.get("visual_credit") or "Illustrations: original HeroVerse images made with open-licence AI image "
                "models (FLUX.1 schnell, Apache-2.0; Stable Diffusion XL, CreativeML Open RAIL++-M)."] if v2 else
               ["Footage credits (Creative Commons Attribution, picture only):", credits])
    if v2 and manifest["clips"]:  # v4: licensed real footage, every clip credited (required for CC BY)
        visuals += footage_credits(manifest["clips"])
    description = "\n".join([
        script.get("description_intro") or (
            "Before you walk into today, God has already been there. Pray this morning prayer with us for peace, "
            "courage and a clean start, anchored in KJV Scripture."),
        "",
        SUBSCRIBE_LINE,
        "",
        "Chapters",
        *(chapters_from_script(script, manifest["timeline"]) if any(s.get("reference") for s in script["segments"])
          else chapters(manifest["timeline"])),
        "",
        "Scripture quotations: King James Version (public domain).",
        "Narration and music: original HeroVerse productions.",
        "",
        *visuals,
        *(["", " ".join(script["hashtags"])] if script.get("hashtags") else []),
    ])
    if len(description) > DESCRIPTION_MAX and v2 and manifest["clips"]:
        # YouTube allows 5,000 characters: drop the optional author names; required attributions stay
        description = description.replace("\n".join(footage_credits(manifest["clips"])),
                                          "\n".join(footage_credits(manifest["clips"], with_authors=False)))
    refs = SCRIPTURE_REF.findall(description.split("Footage credits")[0])
    if refs:
        raise SystemExit(f"DESCRIPTION_SCRIPTURE_REF {refs[:3]} (STANDARD R15)")
    if len(description) > DESCRIPTION_MAX:
        raise SystemExit(f"DESCRIPTION_TOO_LONG {len(description)} > {DESCRIPTION_MAX}")
    tags = script.get("tags") or ["morning prayer", "prayer for peace", "prayer for courage", "christian morning prayer",
            "start your day with God", "God goes before you", "Deuteronomy 31:8", "HeroVerse"]
    thumb = out / "thumbnail.jpg"
    if v2 and manifest["clips"]:  # v4 footage: R16 breakout style over the warmest, most saturated still
        stills = sorted(f for f in (work / "frames").glob("[0-9][0-9][0-9].png") if f.stem != "000")
        source = ["-i", str(warmest(stills) if stills else work / "frames" / "001.png")]
        vf = thumbnail_filter(script.get("thumbnail") or {"lines": ["GOD WENT", "FIRST"], "sub": "Morning Prayer"})
    elif v2:  # figure over its first background, text stacked on the free right side
        # first scene's still; in v4 the first scenes may be footage, which has no still frame
        stills = sorted(f for f in (work / "frames").glob("[0-9][0-9][0-9].png") if f.stem != "000")
        source = ["-i", str(stills[0] if stills else work / "frames" / "001.png")]
        th = script.get("thumbnail") or {"lines": ["GOD WENT", "FIRST"], "sub": "Morning Prayer"}
        fit = lambda t, top: min(top, int(560 / (0.72 * max(len(t), 1))))  # keep every line inside the 620 px text column
        lines = [(t, fit(t, 100), "white", f"h*0.22+{115 * i}") for i, t in enumerate(th["lines"])]
        lines.append((th["sub"], fit(th["sub"], 58), "0xFFE7A3", f"h*0.22+{115 * len(th['lines']) + 15}"))
        x_text = "640+(620-text_w)/2"
    else:
        first_shot = manifest["shots"][0]
        source = ["-ss", str(first_shot["source_start"] + 0.5), "-i", first_shot["file"]]
        lines = [("GOD WENT FIRST", 118, "white", "h*0.30"), ("Morning Prayer", 64, "0xFFE7A3", "h*0.30+150")]
        x_text = "(w-text_w)/2"
    if not (v2 and manifest["clips"]):
        draw = ",".join(f"drawtext=fontfile={FONT}:text='{escape(t)}':fontsize={size}:fontcolor={colour}:"
                        f"borderw={6 if size >= 100 else 4}:bordercolor=black@0.7:x={x_text}:y={y}"
                        for t, size, colour, y in lines)
        vf = "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,eq=brightness=-0.06:saturation=1.1," + draw
    subprocess.run(["ffmpeg", "-v", "error", "-y", *source, "-frames:v", "1", "-vf", vf, "-q:v", "2", str(thumb)],
                   check=True, capture_output=True)
    package = {"version": "pilot-package-v1", "pilot_id": script["pilot_id"], "title": title,
               "title_length": len(title), "description": description, "tags": tags,
               "category_id": "29", "playlist": script.get("playlist"), "default_language": "en", "made_for_kids": False,
               "privacy_on_upload": "private", "thumbnail": thumb.name,
               "ai_generated_visuals": v2,
               "altered_or_synthetic_disclosure": ("Stylized devotional illustrations, not realistic footage; review YouTube's "
                                                   "altered-content setting at upload") if v2 and not manifest["clips"] else
                                                  ("Licensed real nature footage plus AI-generated stylized stills; no realistic "
                                                   "people or events are depicted") if v2 else None,
               "first_comment": first_comment_for(script),
               "promise_matches_opening": script.get("promise") or "Title promise 'God has already gone ahead of you' is spoken at 0-8 s.",
               "upload_performed": False, "publication_performed": False}
    (out / "package.json").write_text(json.dumps(package, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"title": title, "chars": len(title), "clips_credited": len(manifest["clips"])}))


if __name__ == "__main__":
    main(*sys.argv[1:4])
