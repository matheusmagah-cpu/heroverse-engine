"""Build pilot-015's segments: our narration + KJV verses pulled from kjv.tsv.gz (word for word)."""
import gzip, json, re, sys
from pathlib import Path
ROOT = Path('/home/user/heroverse-engine/migration/production')
V = {}
for line in gzip.open(ROOT/'bible/kjv/kjv.tsv.gz','rt',encoding='utf-8'):
    if line.startswith('#'): continue
    b,c,v,t = line.rstrip('\n').split('\t'); V[(b,int(c),int(v))]=t
def kjv(c, a, b=None):
    return " ".join(V[('Genesis',c,v)] for v in range(a,(b or a)+1))
def ref(c,a,b=None): return f"Genesis {c}:{a}" + (f"-{b}" if b and b!=a else "") + " (KJV)"
S = []
def seg(id, text, pause=0.7, reference=None, stills=None, chapter=None):
    x = {"id": id, "text": text, "pause_after": pause}
    if reference: x["reference"] = reference
    if stills: x["stills"] = stills
    if chapter: x["chapter"] = chapter
    S.append(x)
def q(id, lead, c, a, b=None, **kw):
    seg(id, (lead + " " if lead else "") + kjv(c,a,b), reference=ref(c,a,b), **kw)

seg("hook", "Before you hear how it ended, see how it began. One garden, one tree, one choice that reaches you.", 0.6, chapter="The gate at the east of Eden")
q("peak", "It ends at a gate.", 3, 24, stills=["st-gate-sword"])
seg("roadmap", "Today you will hear the whole story from the first words of the Bible: how God made the world, how he formed the first man and woman, the question that broke their trust, and why that gate was closed.", 0.8)
# chapter 1
seg("rehook-1", "It starts in total darkness, with no light, no land and no life. Then God speaks.", 0.6)
seg("chapter-1", "Here is how the Bible opens, in the words of the King James Version.", 0.6, chapter="Before there was light, God spoke")
q("c1-light", "", 1, 1, 3, stills=None)
q("c1-day", "Light is the first thing God makes, and he names it.", 1, 4, 5)
seg("c1-note", "Notice the rhythm. God speaks, it happens, and he calls it good. Every day of creation follows that pattern, and it tells you something about him: nothing he makes is an accident.", 0.7)
q("c1-land", "On the third day the waters pull back and the dry land appears.", 1, 9, 10)
q("c1-lights", "On the fourth day God hangs the lights in the sky, to rule the day and the night and to mark the seasons.", 1, 16, 18)
seg("rehook-1b", "Now comes the moment the whole chapter has been building toward. For the first time, God says \"us\".", 0.6)
q("c1-image", "", 1, 26, 27, stills=["st-man-dawn"])
q("c1-blessing", "And the first words God speaks to people are a blessing.", 1, 28)
q("c1-verygood", "When he looks at everything together, the verdict changes.", 1, 31)
q("c1-rest", "And then God rests.", 2, 1, 3)
seg("c1-close", "Seven days, and a world that is very good. But the Bible is about to slow down and zoom in, to one man, one garden and one command.", 0.8)
# chapter 2
seg("rehook-2", "The second chapter tells the making of man up close. It is gentler than you might expect.", 0.6)
seg("chapter-2", "God does not build the first man from a distance. He kneels in the dust.", 0.6, chapter="God breathed into the dust", stills=["st-dust-hand"])
q("c2-breath", "", 2, 7)
q("c2-garden", "Then God plants a garden for him, in a place called Eden.", 2, 8, 9, stills=["st-tree-of-life"])
q("c2-river", "Out of Eden a river flows, and it parts into four.", 2, 10, stills=["st-four-rivers"])
q("c2-work", "Before any rule, there is work and there is care.", 2, 15)
q("c2-command", "And then there is one command, only one.", 2, 16, 17, stills=["st-tree-knowledge"])
seg("c2-note", "Everything is a yes, except one tree. The command is not a trap. It is a single place where trust in God can be chosen, freely, every day.", 0.7)
seg("rehook-2b", "But something in the garden is still missing, and God is the one who says it.", 0.6)
q("c2-alone", "", 2, 18, 19, stills=["st-animals-named"])
q("c2-woman", "So God does something no animal could do.", 2, 21, 22, stills=["st-two-hands"])
q("c2-poem", "And the first words a man ever speaks in the Bible are a poem.", 2, 23)
q("c2-unashamed", "The chapter ends in peace.", 2, 25)
seg("c2-close", "No fear, no shame, nothing hidden. Hold on to that picture, because in the very next verse, a voice enters the garden.", 0.8)
# chapter 3
seg("rehook-3", "One question. That was all it took to begin the unravelling of everything you just heard.", 0.6)
seg("chapter-3", "The serpent does not start with a lie. He starts with a question.", 0.6, chapter="Did God really say that?", stills=["st-serpent"])
q("c3-question", "", 3, 1)
q("c3-answer", "The woman answers him, and she adds a little to the command.", 3, 2, 3)
q("c3-lie", "Now the serpent says the opposite of what God said.", 3, 4, 5)
seg("c3-note", "Look at the order. First God's word is questioned, then it is contradicted, and then his heart is questioned too: maybe he is keeping something good from you. That is still how temptation sounds.", 0.7)
q("c3-take", "", 3, 6, stills=["st-one-fruit", "st-hand-reach"])
q("c3-eyes", "Their eyes are opened, but not to what they hoped.", 3, 7)
seg("c3-close", "They wanted to be like God. Instead, the first thing they do is hide.", 0.8)
# chapter 4
seg("rehook-4", "They hid from God. And he came looking for them anyway.", 0.6)
seg("chapter-4", "Listen for the first question God asks in the whole Bible.", 0.6, chapter="Where art thou?")
q("c4-walk", "", 3, 8, 9)
seg("c4-note", "God knows where they are. The question is an invitation to come out and tell the truth.", 0.6)
q("c4-afraid", "", 3, 10, 13)
seg("c4-blame", "The man blames the woman, and even God for giving her. The woman blames the serpent. Nobody says sorry.", 0.6)
q("c4-promise", "Then God speaks to the serpent, and inside the curse there is a promise.", 3, 14, 15)
seg("rehook-4b", "Keep that promise in mind: one day a descendant of the woman will crush the serpent's head. The whole Bible is the story of that promise.", 0.6)
q("c4-cost", "The man and the woman now hear what their choice will cost.", 3, 17, 19)
q("c4-coats", "And yet the next thing God does is an act of kindness.", 3, 21, stills=["st-leaving"])
q("c4-out", "", 3, 22, 23)
seg("c4-close", "And that is where we began: the gate, the cherubims, and the flaming sword that turns every way to keep the way of the tree of life.", 0.8)
# close
seg("reflection", "Here is what this story leaves you with. Sin did not begin with a monster, but with a doubt about whether God is good. And God's first answer to sin was not to walk away, but to come looking, to ask where you are, to cover, and to promise a rescuer. If you have been hiding from him, his question is still an invitation. Thank him tonight that he came looking first.", 0.8)
seg("prayer-close", "Pray with me. Father, thank you for making a world that was very good, and for making us in your image. Forgive us for the times we doubted your goodness and hid from you. Thank you that you came looking for us, and that you kept your promise. Help us to trust your word today. In Jesus' name, amen.", 0.9)
seg("cta", "The next story is Cain and Abel: two brothers, two offerings, and the first time anger wins. Subscribe so you don't miss it, and type amen if you prayed with me.", 0.8)

json.dump(S, open(sys.argv[1],'w'), indent=1, ensure_ascii=False)
print(len(S), sum(len(re.findall(r"[a-z']+", x['text'].lower())) for x in S))
