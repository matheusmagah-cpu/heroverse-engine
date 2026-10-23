import json,re,math,statistics as st,datetime as dt
from collections import defaultdict
import os; os.chdir(os.path.dirname(os.path.abspath(__file__))); chans=json.load(open('channel_videos.json'))
NOW=dt.datetime(2026,10,23,tzinfo=dt.timezone.utc)
def dur(s):
    m=re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?',s or '');h,mi,se=(int(x or 0) for x in m.groups());return h*60+mi+se/60
rows=[]
for cid,c in chans.items():
    vs=[]
    for v in c['videos']:
        age=(NOW-dt.datetime.fromisoformat(v['publishedAt'].replace('Z','+00:00'))).days
        if age<10 or not v.get('viewCount') is not None: continue
        vs.append(dict(ch=c['channelTitle'],id=v['videoId'],t=v['title'],min=dur(v['duration']),views=v['viewCount'],
                       com=v.get('commentCount') or 0,age=age,pub=v['publishedAt']))
    if len(vs)<5: continue
    med=st.median(x['views'] for x in vs)
    for x in vs: x['med']=med; x['ratio']=x['views']/max(med,1)
    rows+=vs
T=lambda r:r['t'].lower()
FEAT={
 'date_or_weekday_in_title': lambda r: bool(re.search(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d|\b20\d\d\b',T(r))),
 'month_name_in_title': lambda r: bool(re.search(r'\b(january|february|march|april|june|july|august|september|october|november|december)\b',T(r))),
 'gratitude (thank)': lambda r: bool(re.search(r'\bthank|gratitude|grateful',T(r))),
 'search_phrase_start_day_with_god': lambda r: 'start your day' in T(r),
 'night_before_sleep/bed phrase': lambda r: bool(re.search(r'before (you )?(sleep|bed|going to bed)|bedtime prayer|night prayer',T(r))),
 'time_anchor_before_you': lambda r: bool(re.search(r'^\W*(before you|tonight|this morning|today)',T(r))),
 'psalm_number': lambda r: bool(re.search(r'psalms? ?\d',T(r))),
 'powerful': lambda r: 'powerful' in T(r),
 'protection': lambda r: 'protect' in T(r),
 'anxiety/worry/stress': lambda r: bool(re.search(r'anxi|worr|stress|overthink|can.?t sleep',T(r))),
 'money/financial/breakthrough': lambda r: bool(re.search(r'financ|money|wealth|breakthrough|miracle',T(r))),
 'warfare/evil/enemy': lambda r: bool(re.search(r'warfare|evil|enemy|enemies|demonic|attack',T(r))),
 'emoji': lambda r: bool(re.search(r'[\U0001F300-\U0001FAFF☀-➿]',r['t'])),
 'all_caps_opening': lambda r: bool(re.match(r'^\W*[A-Z]{3,}( [A-Z]{2,}){2,}',r['t'])),
 'pipe_separator': lambda r: '|' in r['t'],
 'second_person_you': lambda r: bool(re.search(r'\byou(r)?\b',T(r))),
 'first_person_prayer (Lord, I/me/my)': lambda r: bool(re.search(r'\b(i|me|my)\b',T(r))),
 'numeric_minutes_in_title': lambda r: bool(re.search(r'\d+[- ]minut',T(r))),
 'title_len>80': lambda r: len(r['t'])>80,
 'dur<10': lambda r: r['min']<10,
 'dur10-20': lambda r: 10<=r['min']<20,
 'dur20-40': lambda r: 20<=r['min']<40,
 'dur40-90': lambda r: 40<=r['min']<90,
 'dur>=90': lambda r: r['min']>=90,
}
def mh(feature,outcome):
    # Mantel-Haenszel odds ratio stratified by channel
    num=den=0; a_tot=b_tot=c_tot=d_tot=0
    by=defaultdict(list)
    for r in rows: by[r['ch']].append(r)
    for ch,rs in by.items():
        a=sum(1 for r in rs if feature(r) and outcome(r)); b=sum(1 for r in rs if feature(r) and not outcome(r))
        c=sum(1 for r in rs if not feature(r) and outcome(r)); d=sum(1 for r in rs if not feature(r) and not outcome(r))
        n=a+b+c+d
        if n==0: continue
        num+=a*d/n; den+=b*c/n; a_tot+=a;b_tot+=b;c_tot+=c;d_tot+=d
    orr=num/den if den else float('inf')
    return orr,a_tot,b_tot,c_tot,d_tot
hit=lambda r: r['ratio']>=3
dead=lambda r: r['ratio']<=0.5
print(f"videos analysed: {len(rows)} in {len(set(r['ch'] for r in rows))} channels; hits(ratio>=3): {sum(map(hit,rows))}; dead(<=0.5x median): {sum(map(dead,rows))}")
res=[]
for k,f in FEAT.items():
    o,a,b,c,d=mh(f,hit); o2,*_=mh(f,dead)
    n_f=a+b
    res.append((k,n_f,a,(a/n_f if n_f else 0),(c/(c+d) if c+d else 0),o,o2))
print(f"{'feature':38} {'n':>4} {'hits':>4} {'P(hit|f)':>8} {'P(hit|~f)':>9} {'MH-OR hit':>9} {'MH-OR dead':>10}")
for k,n,a,p1,p0,o,o2 in sorted(res,key=lambda x:-x[5] if x[5]!=float('inf') else -99):
    print(f"{k:38} {n:4} {a:4} {p1:8.2f} {p0:9.2f} {o:9.2f} {o2:10.2f}")
json.dump(rows,open('rows.json','w'))
