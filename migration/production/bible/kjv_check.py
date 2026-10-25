#!/usr/bin/env python3
"""Every quotation narrated as Scripture must be the KJV word for word (owner, 2026-10-24). Nothing checked it: a
script could misquote a verse and only a listener would notice. The KJV (1769, public domain; Psalm titles left out)
is kept in kjv/kjv.tsv.gz. A segment mixes our own words ("David prayed like this.") with the quotation, so the text
is aligned with the referenced verses. A run of 3+ passage words in order (not only common words such as "and that
is a"), with the runs within 3 words of it, is a quotation, and inside it nothing may be changed, added or dropped
(case, spaces, punctuation and "Selah" ignored). A quotation that starts or stops inside a verse must be set off
from our words by punctuation, and the words beside it must not be a near copy of the verse words it leaves out
("Be quiet, and know" for "Be still, and know"). Every referenced verse must be quoted; "..." or an ellipsis marks
words left out on purpose.

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
ONE_CHAPTER = {"obadiah", "philemon", "2 john", "3 john", "jude"}
GAP = 3          # words a quotation may skip on either side and still be one quotation (then it must be equal)
NEAR_COPY = 0.5  # letter similarity at which the words beside a quotation copy the verse words it leaves out
ELLIPSIS = "_"   # stands for "..." among the words, so no match runs across it
# a quotation starts at a run of 3+ passage words with 2+ words outside this list ("word for all" in our own sentence
# is not Psalm 119), or at a run of 5+
COMMON = set("a all an and are as at be but by for from he her him his i in is it me my no not of on or our shall "
             "so that the thee their them there they this thou thy to unto us was we were what which who will with "
             "ye you your".split())
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
    """The verses of a reference such as "Psalm 23:1-3 (KJV)", "Genesis 2:7-22, 25", "John 3:16-4:2", "Psalm 23",
    "Jude 3" or "Isaiah 53:5; 1 Peter 2:24", as [(book, chapter, verse, text)]."""
    ref = re.sub(r"\s*\(.*?\)\s*$", "", reference).strip().replace("\u2013", "-").replace("\u2014", "-")
    if ";" in ref:
        return [v for part in ref.split(";") for v in passage(part)]
    m = re.match(r"^((?:[1-3] )?[A-Za-z ]+?)\s+(\d+)(?::(.+))?$", ref)
    if not m:
        raise ValueError(f"REFERENCE_UNPARSED {reference}")
    book = ALIASES.get(m.group(1).lower(), m.group(1).lower())
    ch, spec, table = int(m.group(2)), m.group(3), verses()
    if spec is None and book in ONE_CHAPTER:
        ch, spec = 1, m.group(2)
    if spec is None:  # a whole chapter
        out = [(b, c, v, t) for (b, c, v), t in table.items() if b == book and c == ch]
        if not out:
            raise ValueError(f"REFERENCE_NOT_IN_KJV {reference}")
        return out
    out = []
    for part in spec.replace(" ", "").split(","):
        r = re.match(r"^(?:(\d+):)?(\d+)(?:-(?:(\d+):)?(\d+))?$", part)
        if not r:
            raise ValueError(f"REFERENCE_UNPARSED {reference}")
        ch = int(r.group(1) or ch)
        start, end_ch, end = int(r.group(2)), int(r.group(3) or ch), int(r.group(4) or r.group(2))
        c, v = ch, start
        while (c, v) <= (end_ch, end):
            if (book, c, v) in table:
                out.append((book, c, v, table[(book, c, v)]))
                v += 1
            elif (book, c + 1, 1) in table and c < end_ch:
                c, v = c + 1, 1
            else:
                raise ValueError(f"REFERENCE_NOT_IN_KJV {reference}")
        ch = end_ch
    return out


def words(text):
    return [w for w in re.findall(r"[a-z]+", text.lower()) if w != "selah"]  # a musical mark, not narrated


def similar(a, b):
    return difflib.SequenceMatcher(None, "".join(a), "".join(b), autojunk=False).ratio() if a and b else 0.0


def problem(reference, text):
    """None when every quotation in the text is the KJV of its reference; otherwise the reason."""
    try:
        kjv = passage(reference)
    except ValueError as e:
        return str(e)
    p_words, p_verse = [], []
    for i, (*_, t) in enumerate(kjv):
        w = words(t)
        p_words += w
        p_verse += [i] * len(w)
    text = re.sub(r"[\"\u201c\u201d]", "", text).replace("\u2026", "...")
    tokens = [t for t in re.finditer(r"[a-z]+|\.\.\.", text.lower()) if t.group() != "selah"]
    t_words = [ELLIPSIS if t.group() == "..." else t.group() for t in tokens]

    def between(i):  # the text between token i-1 and token i
        return text[tokens[i - 1].end():tokens[i].start()] if 0 < i < len(tokens) else ""

    def boundary(i):
        return ELLIPSIS in t_words[i - 1:i + 1] or bool(re.search(r"[.!?;:,]", between(i)))

    blocks = [b for b in difflib.SequenceMatcher(None, t_words, p_words, autojunk=False).get_matching_blocks() if b.size]
    chains, chain = [], []
    for b in blocks:
        if chain:
            last = chain[-1]
            gap_t, gap_p = b.a - last.a - last.size, b.b - last.b - last.size
            if gap_t <= GAP and gap_p <= GAP and ELLIPSIS not in t_words[last.a + last.size:b.a]:
                chain.append(b)
                continue
            chains.append(chain)
        chain = [b]
    def seed(b):
        run = t_words[b.a:b.a + b.size]
        return b.size >= 5 or (b.size >= 3 and sum(w not in COMMON for w in run) >= 2)

    chains = [c for c in chains + [chain] if c and any(seed(b) for b in c)]
    if not chains:
        return f"KJV_QUOTE_NOT_FOUND {reference}"
    quoted_verses, prev_end = set(), 0
    for c in chains:
        snippet = text[tokens[c[0].a].start():tokens[c[-1].a + c[-1].size - 1].end()][:80]
        mismatch = f"KJV_TEXT_MISMATCH {reference}: {snippet!r}"
        for x, y in zip(c, c[1:]):
            if y.a - x.a - x.size or y.b - x.b - x.size:
                return mismatch  # words changed, added or dropped inside the quotation
        t0, p0 = c[0].a, c[0].b
        t1, p1 = c[-1].a + c[-1].size, c[-1].b + c[-1].size
        left = [j for j in range(max(prev_end, p0 - 8), p0) if p_verse[j] == p_verse[p0]]
        if left and t0 and (not boundary(t0) or similar(t_words[max(0, t0 - len(left)):t0], [p_words[j] for j in left]) >= NEAR_COPY):
            return mismatch  # the start of the verse was changed, not left out
        right = [j for j in range(p1, min(len(p_words), p1 + 8)) if p_verse[j] == p_verse[p1 - 1]]
        if right and t1 < len(t_words) and (not boundary(t1) or similar(t_words[t1:t1 + len(right)], [p_words[j] for j in right]) >= NEAR_COPY):
            return mismatch  # the end of the verse was changed, not left out
        quoted_verses.update(p_verse[p0:p1])
        prev_end = p1
    missing = [f"{c}:{v}" for i, (_, c, v, _) in enumerate(kjv) if i not in quoted_verses]
    whole_chapter = ":" not in re.sub(r"\(.*?\)", "", reference)
    if missing and not whole_chapter and "..." not in text:
        return f"KJV_VERSE_NOT_QUOTED {reference}: {', '.join(missing[:5])}"
    return None


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
