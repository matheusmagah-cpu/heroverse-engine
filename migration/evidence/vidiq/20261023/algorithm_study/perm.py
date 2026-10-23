import json,random,re
from collections import defaultdict
exec(open('analyze.py').read().split("def mh(")[0].split("rows=[]")[0])  # imports + dur
rows=json.load(open('rows.json'))
src=open('analyze.py').read()
FEAT=eval(src[src.index('FEAT={')+5:src.index('\ndef mh(')])
T=lambda r:r['t'].lower()
hit=lambda r: r['ratio']>=3; dead=lambda r: r['ratio']<=0.5
strata=defaultdict(list)
for r in rows: strata[(r['ch'],r['pub'][:7])].append(r)
strata={k:v for k,v in strata.items() if len(v)>=2}
def mh_from(flags_by_stratum,outcome):
    num=den=0
    for k,rs in strata.items():
        fl=flags_by_stratum[k]
        a=sum(1 for r,f in zip(rs,fl) if f and outcome(r)); b=sum(1 for r,f in zip(rs,fl) if f and not outcome(r))
        c=sum(1 for r,f in zip(rs,fl) if not f and outcome(r)); d=sum(1 for r,f in zip(rs,fl) if not f and not outcome(r))
        n=a+b+c+d; num+=a*d/n; den+=b*c/n
    return (num/den) if den else float('inf'), num, den
random.seed(7)
N=2000
print(f"strata (channel x month) with >=2 videos: {len(strata)}; videos: {sum(len(v) for v in strata.values())}")
print(f"{'feature':38} {'n_f':>4} {'OR_hit':>7} {'p_hit':>6} {'OR_dead':>8} {'p_dead':>7}")
out=[]
for name,f in FEAT.items():
    flags={k:[bool(f(r)) for r in rs] for k,rs in strata.items()}
    nf=sum(sum(v) for v in flags.values())
    res=[]
    for outc in (hit,dead):
        obs,_,_=mh_from(flags,outc)
        ge=0
        for _ in range(N):
            sh={k:random.sample(v,len(v)) for k,v in flags.items()}
            o,_,_=mh_from(sh,outc)
            if (obs>=1 and o>=obs) or (obs<1 and o<=obs): ge+=1
        res+= [obs,(ge+1)/(N+1)]
    out.append((name,nf,*res))
for name,nf,oh,ph,od,pd in sorted(out,key=lambda x:x[3]):
    fmt=lambda x: f"{x:7.2f}" if x!=float('inf') else "    inf"
    print(f"{name:38} {nf:4} {fmt(oh)} {ph:6.3f} {fmt(od)} {pd:7.3f}")
json.dump(out,open('perm_results.json','w'))
