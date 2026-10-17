#!/usr/bin/env python3
"""Publication package for a QA-passed pilot: title, description with every
Creative Commons attribution, tags and a 1280x720 thumbnail. Writes files only;
no upload. Packaging promise must match the opening (archetype rule)."""
import json
from pathlib import Path
import subprocess
import sys

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def escape(text):
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")


def chapters_from_script(script, timeline):
    """Chapters at every scripture anchor plus the opening, prayer and blessing turns."""
    named = {"hook": "Good morning", "transition": "Let us pray", "declaration": "Declaration for today",
             "payoff": "One thing to do today", "blessing": "Blessing"}
    named.update({s["id"]: s["chapter"] for s in script["segments"] if s.get("chapter")})  # the script's own chapter names win
    refs = {s["id"]: s["reference"].replace(" (KJV)", "") for s in script["segments"] if s.get("reference")}
    rows = []
    for seg in timeline:
        label = named.get(seg["id"]) or refs.get(seg["id"])
        if label:
            start = 0 if seg["id"] == "hook" else int(seg["start"])
            rows.append(f"{start // 60}:{start % 60:02d} {label}")
    return rows


def chapters(timeline):
    names = {"hook": "Good morning", "scripture-1": "He goes before you (Deuteronomy 31:8)",
             "scripture-2": "New mercy every morning (Lamentations 3:22-23)",
             "scripture-3": "Show me the way (Psalm 143:8)", "transition": "Let us pray",
             "scripture-4": "Fear not (Isaiah 41:10)", "declaration": "Declaration for today",
             "payoff": "One thing to do today", "blessing": "Blessing"}
    rows = []
    for seg in timeline:
        if seg["id"] in names:
            start = 0 if seg["id"] == "hook" else int(seg["start"])
            rows.append(f"{start // 60}:{start % 60:02d} {names[seg['id']]}")
    return rows


def main(work, script_path, out_dir):
    work, out = Path(work), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    script = json.loads(Path(script_path).read_text())
    manifest = json.loads((work / "manifest.json").read_text())
    title = script["working_title"]
    v2 = manifest.get("version") == "pilot-manifest-v2"
    credits = "\n".join("• " + c["attribution"] for c in manifest["clips"])
    visuals = ([script.get("visual_credit") or "Illustrations: original HeroVerse images made with open-licence AI image "
                "models (FLUX.1 schnell, Apache-2.0; Stable Diffusion XL, CreativeML Open RAIL++-M)."] if v2 else
               ["Footage credits (Creative Commons Attribution, picture only):", credits])
    description = "\n".join([
        script.get("description_intro") or (
            "Before you walk into today, God has already been there. Pray this morning prayer with us for peace, "
            "courage and a clean start, anchored in Deuteronomy 31:8, Lamentations 3:22-23, Psalm 143:8, "
            "Isaiah 41:10 and Proverbs 3:5-6."),
        "",
        "Chapters",
        *(chapters_from_script(script, manifest["timeline"]) if any(s.get("reference") for s in script["segments"])
          else chapters(manifest["timeline"])),
        "",
        *(["Scripture in this prayer: " + "; ".join(dict.fromkeys(
            s["reference"].replace(" (KJV)", "") for s in script["segments"] if s.get("reference"))), ""]
          if script.get("description_intro") else []),
        "Scripture quotations: King James Version (public domain).",
        "Narration and music: original HeroVerse productions.",
        "",
        *visuals,
        *(["", " ".join(script["hashtags"])] if script.get("hashtags") else []),
    ])
    tags = script.get("tags") or ["morning prayer", "prayer for peace", "prayer for courage", "christian morning prayer",
            "start your day with God", "God goes before you", "Deuteronomy 31:8", "HeroVerse"]
    thumb = out / "thumbnail.jpg"
    if v2:  # figure over its first background, text stacked on the free right side
        source = ["-i", str(work / "frames" / "001.png")]
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
    draw = ",".join(f"drawtext=fontfile={FONT}:text='{escape(t)}':fontsize={size}:fontcolor={colour}:"
                    f"borderw={6 if size >= 100 else 4}:bordercolor=black@0.7:x={x_text}:y={y}"
                    for t, size, colour, y in lines)
    subprocess.run(["ffmpeg", "-v", "error", "-y", *source, "-frames:v", "1", "-vf",
                    "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,eq=brightness=-0.06:saturation=1.1,"
                    + draw, "-q:v", "2", str(thumb)], check=True, capture_output=True)
    package = {"version": "pilot-package-v1", "pilot_id": script["pilot_id"], "title": title,
               "title_length": len(title), "description": description, "tags": tags,
               "category_id": "29", "playlist": script.get("playlist"), "default_language": "en", "made_for_kids": False,
               "privacy_on_upload": "private", "thumbnail": thumb.name,
               "ai_generated_visuals": v2,
               "altered_or_synthetic_disclosure": ("Stylized devotional illustrations, not realistic footage; review YouTube's "
                                                   "altered-content setting at upload") if v2 else None,
               "promise_matches_opening": script.get("promise") or "Title promise 'God has already gone ahead of you' is spoken at 0-8 s.",
               "upload_performed": False, "publication_performed": False}
    (out / "package.json").write_text(json.dumps(package, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"title": title, "chars": len(title), "clips_credited": len(manifest["clips"])}))


if __name__ == "__main__":
    main(*sys.argv[1:4])
