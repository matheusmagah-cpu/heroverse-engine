import json,re,random,ast,datetime as dt
from collections import defaultdict
rows={r['id']:r for r in json.load(open('rows.json'))}
meta=json.load(open('meta.json'))
data=[]
for m in meta:
    r=rows.get(m['id'])
    if not r: continue
    d=m.get('description') or ''
    try: tags=ast.literal_eval(m['tags']) if isinstance(m.get('tags'),str) else (m.get('tags') or [])
    except Exception: tags=[]
    topics=str(m.get('topicCategories'))
    pub=dt.datetime.fromisoformat(r['pub'].replace('Z','+00:00'))
    data.append({**r,'desc':d,'tags':tags,'topics':topics,'hour':pub.hour,'wd':pub.weekday()})
F={
 'desc_len>1000': lambda x: len(x['desc'])>1000,
 'desc_len<300': lambda x: len(x['desc'])<300,
 'chapters (0:00 timestamps)': lambda x: bool(re.search(r'(^|\n)\s*\(?0?0:00',x['desc'])),
 'hashtags>=3 in desc': lambda x: len(re.findall(r'#\w+',x['desc']))>=3,
 'external link in desc': lambda x: 'http' in x['desc'],
 'scripture refs in desc': lambda x: bool(re.search(r'\b(psalm|john|isaiah|matthew|romans|philippians|proverbs)\s*\d',x['desc'],re.I)),
 'prayer request ask in desc': lambda x: bool(re.search(r'prayer request',x['desc'],re.I)),
 'subscribe ask in desc': lambda x: 'subscribe' in x['desc'].lower(),
 'AI/synthetic disclosure in desc': lambda x: bool(re.search(r'\bAI\b|artificial|synthetic|voice generated',x['desc'])),
 'tags>=15': lambda x: len(x['tags'])>=15,
 'no tags': lambda x: len(x['tags'])==0,
 'topic=Christian_music': lambda x: 'Christian_music' in x['topics'],
 'upload 00-06 UTC': lambda x: 0<=x['hour']<6,
 'upload 06-12 UTC': lambda x: 6<=x['hour']<12,
 'upload 12-18 UTC': lambda x: 12<=x['hour']<18,
 'upload 18-24 UTC': lambda x: 18<=x['hour']<24,
 'weekend upload': lambda x: x['wd']>=5,
}
hit=lambda r: r['ratio']>=3
strata=defaultdict(list)
for r in data: strata[(r['ch'],r['pub'][:7])].append(r)
strata={k:v for k,v in strata.items() if len(v)>=2}
def mh(flags):
    num=den=0
    for k,rs in strata.items():
        fl=flags[k]
        a=sum(1 for r,f in zip(rs,fl) if f and hit(r)); b=sum(1 for r,f in zip(rs,fl) if f and not hit(r))
        c=sum(1 for r,f in zip(rs,fl) if not f and hit(r)); d=sum(1 for r,f in zip(rs,fl) if not f and not hit(r))
        n=a+b+c+d; num+=a*d/n; den+=b*c/n
    return num/den if den else float('inf')
random.seed(3); N=2000
print("videos",len(data),"strata",len(strata),"hits",sum(map(hit,data)),"dead",sum(r['ratio']<=0.5 for r in data))
print(f"{'feature':34}{'n':>5}{'%hits_with':>11}{'%dead_with':>11}{'OR_hit':>8}{'p':>7}")
for name,f in F.items():
    flags={k:[bool(f(r)) for r in rs] for k,rs in strata.items()}
    obs=mh(flags); ge=0
    for _ in range(N):
        sh={k:random.sample(v,len(v)) for k,v in flags.items()}
        o=mh(sh)
        if (obs>=1 and o>=obs) or (obs<1 and o<=obs): ge+=1
    n=sum(f(r) for r in data); ph=sum(f(r) for r in data if hit(r))/max(1,sum(map(hit,data))); pdd=sum(f(r) for r in data if r['ratio']<=0.5)/max(1,sum(r['ratio']<=0.5 for r in data))
    print(f"{name:34}{n:5}{ph:11.2f}{pdd:11.2f}{obs:8.2f}{(ge+1)/(N+1):7.3f}")
# engagement
import statistics as st
for lab,g in (('hits',[r for r in data if hit(r)]),('dead',[r for r in data if r['ratio']<=0.5])):
    lk=[ (int(m.get('likeCount') or 0)) for m in meta if m['id'] in {x['id'] for x in g}]
print("done")
