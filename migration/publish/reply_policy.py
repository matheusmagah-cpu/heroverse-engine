#!/usr/bin/env python3
"""What a reply to a viewer's comment may be, on YouTube and on TikTok (owner, 2026-10-28: "every comment answered,
coherently, automatically"). Claude writes each reply in the series' voice (brand-profile.md "Voice"); this module is
the gate every reply passes before any platform sees it, so a slip in a written reply cannot reach a viewer.

A decision is {"decision": "REPLY", "text": ..., "verse": {"reference", "quote"} (optional)} or
{"decision": "SKIP", "reason": one of SKIP_REASONS}. Spam, hate and provocation are skipped, never argued with.
A reply is short, has no link, mention, hashtag, e-mail or phone number, none of the banned words, and quotes
Scripture only through `verse`: the quote is in the text word for word and is the KJV of its reference
(production/bible/kjv_check.py). A verse reference in the text without a checked `verse` is refused.

usage: reply_policy.py check FILE PLATFORM   FILE = {"replies": {comment_id: decision}}, PLATFORM youtube|tiktok
"""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "migration/production/bible"))
import kjv_check  # noqa: E402

LIMITS = {"youtube": 300, "tiktok": 150}      # "short"; TikTok's own comment limit is 150 characters
SKIP_REASONS = {"spam", "hate", "provocation", "self_promotion", "off_topic", "no_reply_needed", "unclear"}
BANNED = ("shocking", "they don't want you to know", "they dont want you to know", "subscribe", "link in bio",
          "buy ", "donate", "giveaway", "you're wrong", "you are wrong", "stupid", "idiot")
URL = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(?:com|net|org|io|ly|be|me|tv|app)\b", re.I)
MENTION = re.compile(r"(?<![\w.])@\w")
HASHTAG = re.compile(r"(?<![\w&])#\w")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.\w+")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
# "Genesis 2:7", "1 John 4:8", "Psalm 23:1-3": a chapter:verse reference
REFERENCE = re.compile(r"\b(?:[1-3]\s)?[A-Z][a-z]+(?:\sof\s[A-Z][a-z]+)?\s\d{1,3}:\d{1,3}")


def norm(text):
    return re.sub(r"\s+", " ", (text or "").strip())


def problems(decision, platform):
    """[] when the decision may be acted on; otherwise the reasons."""
    if platform not in LIMITS:
        return [f"PLATFORM_UNKNOWN {platform}"]
    if not isinstance(decision, dict):
        return ["DECISION_NOT_AN_OBJECT"]
    kind = decision.get("decision")
    if kind == "SKIP":
        return [] if decision.get("reason") in SKIP_REASONS else [f"SKIP_REASON_INVALID {decision.get('reason')!r}"]
    if kind != "REPLY":
        return [f"DECISION_INVALID {kind!r}"]
    text = norm(decision.get("text"))
    out = []
    if not text:
        return ["REPLY_EMPTY"]
    if len(text) > LIMITS[platform]:
        out.append(f"REPLY_TOO_LONG {len(text)} > {LIMITS[platform]}")
    for name, rx in (("LINK", URL), ("EMAIL", EMAIL), ("MENTION", MENTION), ("HASHTAG", HASHTAG), ("PHONE", PHONE)):
        if rx.search(text):
            out.append(f"REPLY_HAS_{name}")
    low = text.lower()
    out += [f"REPLY_BANNED_WORD {w.strip()!r}" for w in BANNED if w in low]
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 12 and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        out.append("REPLY_SHOUTING")
    verse = decision.get("verse")
    if verse:
        ref, quote = norm(verse.get("reference")), norm(verse.get("quote"))
        if not ref or not quote:
            out.append("VERSE_INCOMPLETE")
        else:
            if quote not in text:
                out.append("VERSE_QUOTE_NOT_IN_REPLY")
            if ref not in text:
                out.append("VERSE_REFERENCE_NOT_IN_REPLY")
            p = kjv_check.problem(ref, quote)
            if p:
                out.append(p)
        refs = [m.group() for m in REFERENCE.finditer(text) if m.group() not in ref]
        out += [f"VERSE_UNCHECKED {r}" for r in refs]
    else:
        out += [f"VERSE_UNCHECKED {m.group()}" for m in REFERENCE.finditer(text)]
    return out


def file_problems(replies, platform):
    """Every decision of a replies file, and no reply text used twice (a copied answer reads as a bot)."""
    out, seen = [], {}
    for cid, d in sorted((replies or {}).items()):
        out += [f"{cid}: {p}" for p in problems(d, platform)]
        if isinstance(d, dict) and d.get("decision") == "REPLY":
            t = norm(d.get("text")).lower()
            if t in seen:
                out.append(f"{cid}: REPLY_DUPLICATE_OF {seen[t]}")
            seen.setdefault(t, cid)
    return out


def main(argv):
    if len(argv) != 4 or argv[1] != "check":
        print(__doc__)
        return 2
    bad = file_problems(json.loads(Path(argv[2]).read_text()).get("replies", {}), argv[3])
    print("\n".join(bad) or "PASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
