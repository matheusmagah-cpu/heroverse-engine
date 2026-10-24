#!/usr/bin/env python3
"""Every quotation narrated as Scripture must be the KJV word for word (owner, 2026-10-24). Nothing checked it: a
script could misquote a verse and only a listener would notice. The KJV (1769, public domain) is kept in
kjv/kjv.tsv.gz. A segment mixes our own lead-in ("David prayed like this.") with the quotation, so each sentence
is compared with the referenced verses: a sentence with at least half of its words in the passage is a quotation,
and from its first quoted word to its end it must be the KJV letter for letter (case, spaces and punctuation
ignored; a part of a verse is allowed; a lead-in such as "Jesus said," ends on a comma or colon). A sentence of
passage words in another order counts as a quotation. A referenced segment with no quoted sentence fails too.

usage: kjv_check.py SCRIPT.json      every segment with a "reference" (pilot scripts) or every item of
                                     "scripture" [{reference, text}] (Bible episodes); exit 1 on any mismatch
       kjv_check.py "REFERENCE" "TEXT"
"""
import difflib
import gzip
import json
from pathlib import Path
import re
import sys

KJV = Path(__file__).resolve().parent / "kjv" / "kjv.tsv.gz"
ALIASES = {"psalm": "psalms", "song of songs": "song of solomon", "revelations": "revelation",
           "revelation of john": "revelation"}
_VERSES = {}


def verses():
    if not _VERSES:
        with gzip.open(KJV, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.startswith("#"):
                    book, ch, v, text = line.rstrip("\n").split("\t")
                    _VERSES[(book.lower(), int(ch), int(v))] = text
    return _VERSES


def letters(text):
    return re.sub(r"[^a-z]", "", text.lower())


def passage(reference):
    """The KJV text of a reference such as "Psalm 23:1-3 (KJV)", "Genesis 2:7-22, 25" or "John 3:16-4:2"."""
    ref = re.sub(r"\s*\(.*?\)\s*$", "", reference).strip()
    m = re.match(r"^((?:[1-3] )?[A-Za-z ]+?)\s+(\d+)(?::(.+))?$", ref)
    if not m:
        raise ValueError(f"REFERENCE_UNPARSED {reference}")
    book = ALIASES.get(m.group(1).lower(), m.group(1).lower())
    ch, out, table = int(m.group(2)), [], verses()
    if m.group(3) is None:  # a whole chapter
        out = [t for (b, c, _), t in table.items() if b == book and c == ch]
        if not out:
            raise ValueError(f"REFERENCE_NOT_IN_KJV {reference}")
        return " ".join(out)
    for part in m.group(3).replace(" ", "").split(","):
        r = re.match(r"^(\d+)(?:-(?:(\d+):)?(\d+))?$", part)
        if not r:
            raise ValueError(f"REFERENCE_UNPARSED {reference}")
        start, end_ch, end = int(r.group(1)), int(r.group(2) or ch), int(r.group(3) or r.group(1))
        c, v = ch, start
        while (c, v) <= (end_ch, end):
            if (book, c, v) in table:
                out.append(table[(book, c, v)])
                v += 1
            elif (book, c + 1, 1) in table and c < end_ch:
                c, v = c + 1, 1
            else:
                raise ValueError(f"REFERENCE_NOT_IN_KJV {reference}")
        ch = end_ch
    return " ".join(out)


def words(text):
    return re.findall(r"[a-z]+", text.lower())


def problem(reference, text):
    """None when every quoted sentence of the text is the KJV of its reference; otherwise the reason."""
    try:
        kjv = passage(reference)
    except ValueError as e:
        return str(e)
    kjv_words, kjv_letters, quoted = words(kjv), letters(kjv), 0
    vocabulary = set(kjv_words)
    for sentence in re.split(r"(?<=[.!?;])\s+|\.\.\.|…", text):
        tokens = list(re.finditer(r"[a-z]+", sentence.lower()))
        w = [t.group() for t in tokens]
        blocks = [b for b in difflib.SequenceMatcher(None, w, kjv_words, autojunk=False).get_matching_blocks()
                  if b.size >= 3 or (b.size and b.size == len(w))]
        reordered = len(w) >= 6 and sum(x in vocabulary for x in w) >= 0.9 * len(w)
        if not w or (sum(b.size for b in blocks) * 2 < len(w) and not reordered):
            continue  # our own words
        quoted += 1
        # a lead-in ("Jesus said,") ends on a comma or colon; anything after the first quoted word is the quotation
        start = blocks[0].a if blocks else 0
        if start and not re.match(r"\s*[,:]", sentence.lower()[tokens[start - 1].end():]):
            start = 0
        if "".join(w[start:]) not in kjv_letters:
            return f"KJV_TEXT_MISMATCH {reference}: {sentence.strip()[:80]!r}"
    return None if quoted else f"KJV_QUOTE_NOT_FOUND {reference}"


def script_problems(script):
    items = [(x.get("id"), x["reference"], x.get("text", "")) for x in script.get("segments", []) if x.get("reference")]
    items += [(f"scripture-{i}", x["reference"], x.get("text", "")) for i, x in enumerate(script.get("scripture", []))]
    return [f"{p} ({sid})" for sid, ref, text in items if (p := problem(ref, text))]


def main(argv):
    if len(argv) == 3:
        p = problem(argv[1], argv[2])
        print(p or "PASS")
        return 1 if p else 0
    if len(argv) != 2:
        print(__doc__)
        return 2
    problems = script_problems(json.loads(Path(argv[1]).read_text()))
    print("\n".join(problems) if problems else "PASS")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
