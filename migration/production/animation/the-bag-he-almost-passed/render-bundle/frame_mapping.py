"""Map output frame times through sentence-aligned source spans at speed one."""
import math


def short_frames(mapping,fps=24):
    spans=mapping['spans'];total=sum(s['master_end_s']-s['master_start_s'] for s in spans)
    if not spans or not math.isfinite(total) or abs(total-mapping['total_s'])>1e-6:raise ValueError('SHORT_TOTAL')
    if any(s['master_start_s']<0 or s['master_end_s']<=s['master_start_s'] for s in spans):raise ValueError('SHORT_SPAN')
    result=[];cursor=0;index=0
    for output in range(round(total*fps)):
        t=output/fps
        while index<len(spans)-1 and t>=cursor+spans[index]['master_end_s']-spans[index]['master_start_s']:
            cursor+=spans[index]['master_end_s']-spans[index]['master_start_s'];index+=1
        source=spans[index]['master_start_s']+t-cursor
        result.append(source*fps)
    return result
