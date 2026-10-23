#!/usr/bin/env python3
"""Fail-closed animation measurements against the byte-pinned criteria.

Usage: qa_animation.py OUT_DIR CRITERIA
Reads master.mp4, short1.mp4, short2.mp4 and their SRTs; timeline.json,
scenes.json, timing.json, shorts-map.json and frames.json when available.
Missing provenance, perceptual review, ASR, stem or visual-card evidence remains
UNKNOWN, never converted from a self-reported boolean into PASS. No approvals.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

FROZEN_SHA256 = '2c97ebfd04951f9016096c1c392c33370cea41a4faf2d72cfe801c18cf202b71'


def run(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=180)


def load(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    try:
        return json.loads(Path(path).read_text(), object_pairs_hook=unique_pairs)
    except (OSError, ValueError):
        return None


def finite(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def probe(path):
    if not path.is_file():
        return None
    try:
        p = run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)])
        if p.returncode: return None
        return json.loads(p.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def loudness(path):
    try:
        p=run(['ffmpeg','-nostdin','-v','info','-i',str(path),'-vn','-af','ebur128=peak=true','-f','null','-'])
        if p.returncode: return None
        summary=p.stderr.rsplit('Summary:',1)[-1]
        integrated=re.search(r'I:\s*([-+\d.]+) LUFS',summary)
        peak=re.search(r'Peak:\s*([-+\d.]+) dBFS',summary)
        return {'integrated_lufs':finite(integrated.group(1)) if integrated else None,
                'true_peak_dbtp':finite(peak.group(1)) if peak else None}
    except (OSError, subprocess.TimeoutExpired):
        return None


def decode(path):
    try:
        p=run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(path),'-f','null','-'])
        return p.returncode == 0 and not p.stderr.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None


def parse_srt(path):
    text=path.read_text(encoding='utf-8-sig').strip()
    cues=[]
    def stamp(v):
        h,m,s,ms=map(int,re.split('[:,]',v)); return h*3600+m*60+s+ms/1000
    for block in re.split(r'\n\s*\n',text):
        lines=block.splitlines()
        if len(lines)<3 or not lines[0].isdigit(): raise ValueError('INVALID_SRT')
        match=re.fullmatch(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})',lines[1])
        if not match: raise ValueError('INVALID_SRT')
        start,end=map(stamp,match.groups())
        if end<=start or (cues and start<cues[-1]['start']): raise ValueError('INVALID_SRT_TIMING')
        cues.append({'start':start,'end':end,'text':' '.join(lines[2:])})
    return cues


def subtitle_metrics(cues, sentences):
    if len(cues)!=len(sentences): return {'text':False,'start':None,'end':None}
    return {'text':all(c['text']==s['text'] for c,s in zip(cues,sentences)),
            'start':max((abs(c['start']-s['start']) for c,s in zip(cues,sentences)),default=0),
            'end':max((abs(c['end']-s['end']) for c,s in zip(cues,sentences)),default=0)}


def frame_metrics(frames, fps, expected, holds=()):
    """Hashes are the required render manifest, not decoded lossy-video hashes."""
    if not isinstance(frames,dict): raise ValueError('INVALID_FRAMES')
    keys=[]
    for key,value in frames.items():
        if not re.fullmatch(r'0|[1-9]\d*',str(key)) or not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):
            raise ValueError('INVALID_FRAME_ENTRY')
        keys.append(int(key))
    if sorted(keys)!=list(range(expected)): return {'contiguous':False,'ratio':None,'unique_fps':None}
    excluded=set()
    for first,last in holds:
        if not 0<=first<=last<=expected: raise ValueError('INVALID_HOLD')
        excluded.update(range(first,last))
    indexes=[i for i in range(expected) if i not in excluded]
    if not indexes: raise ValueError('NO_MEASURED_FRAMES')
    distinct=sum(i==0 or i-1 in excluded or frames[str(i)]!=frames[str(i-1)] for i in indexes)
    return {'contiguous':True,'ratio':distinct/len(indexes),'unique_fps':distinct*fps/len(indexes)}


def expected_short(timeline, short):
    result=[]; cursor=0
    for span in short['spans']:
        start,end=span['master_start_s'],span['master_end_s']
        selected=[s for s in timeline['sentences'] if s['segment']==span['scene'] and s['start']>=start and s['end']<=end]
        if not selected or selected[0]['start']!=start or selected[-1]['end']!=end:
            raise ValueError('SHORT_NOT_SENTENCE_ALIGNED')
        result.extend({'text':s['text'],'start':cursor+s['start']-start,'end':cursor+s['end']-start} for s in selected)
        cursor+=end-start
    if abs(cursor-short['total_s'])>1e-6: raise ValueError('SHORT_TOTAL_MISMATCH')
    return result


def evaluate(out, criteria):
    rows={}
    def add(key,value,limit,ok=None):
        rows[key]={'id':key,'value':value,'limit':limit,'status': 'UNKNOWN' if ok is None else ('PASS' if ok else 'FAIL')}
    def equal(key,value,limit): add(key,value,limit,None if value is None else value==limit)
    def between(key,value,limit): add(key,value,limit,None if value is None else limit[0]<=value<=limit[1])
    def maximum(key,value,limit): add(key,value,limit,None if value is None else value<=limit)
    def minimum(key,value,limit): add(key,value,limit,None if value is None else value>=limit)
    # Enumerate every operational leaf, including unmeasurable requirements.
    def seed(obj,prefix=''):
        for key,value in obj.items():
            name=f'{prefix}.{key}' if prefix else key
            if isinstance(value,dict): seed(value,name)
            else: add(name,None,value)
    for group in ('master','shorts','fluidity','continuity','audio','subtitles','scripture','cta','render_identity','rights'):
        seed(criteria[group],group)
    add('perceptual_review_required_before_approval',None,criteria['perceptual_review_required_before_approval'])
    timeline=load(out/'timeline.json'); scenes=load(out/'scenes.json'); timing=load(out/'timing.json'); shorts=load(out/'shorts-map.json')
    media={}; audio={}; cues={}; expected={}
    if timeline:
        expected['master']=timeline.get('sentences',[])
        for name in criteria['shorts']['duration_seconds']:
            try: expected[name]=expected_short(timeline,shorts[name])
            except (ValueError,KeyError,TypeError): pass
    names=['master',*criteria['shorts']['duration_seconds']]
    measured={}
    for name in names:
        cfg=criteria['master'] if name=='master' else criteria['shorts']
        prefix=name if name=='master' else 'shorts.'+name
        file=out/(name+'.mp4'); p=probe(file); media[name]=p
        if p:
            videos=[s for s in p['streams'] if s['codec_type']=='video']; audios=[s for s in p['streams'] if s['codec_type']=='audio']
            if len(videos)!=1:
                add(prefix+'.video_stream_count',len(videos),1,False); continue
            v=videos[0]
            for key in ('width','height','codec','pix_fmt'):
                equal(prefix+'.'+key,v.get('codec_name' if key=='codec' else key),cfg[key])
            rate=v.get('avg_frame_rate','0/0').split('/')
            fps=float(rate[0])/float(rate[1]) if len(rate)==2 and float(rate[1]) else None
            equal(prefix+'.fps',fps,cfg['fps'])
            duration=finite(v.get('duration',p.get('format',{}).get('duration')))
            limits=cfg['duration_seconds'] if name=='master' else cfg['duration_seconds'][name]
            between(prefix+'.duration_seconds',duration,limits)
            valid_audio=(len(audios)==1 and audios[0].get('codec_name')=='aac' and audios[0].get('sample_rate')=='48000' and audios[0].get('channels')==2)
            add(prefix+'.audio',{'count':len(audios),'streams':[{k:s.get(k) for k in ('codec_name','sample_rate','channels')} for s in audios]},criteria['master']['audio'],valid_audio)
            ad=finite(audios[0].get('duration')) if len(audios)==1 else None
            maximum(prefix+'.av_duration_delta_seconds_max',abs(duration-ad) if duration is not None and ad is not None else None,criteria['master']['av_duration_delta_seconds_max'])
            equal(prefix+'.full_decode_without_errors',decode(file),True)
            levels=loudness(file); audio[name]=levels
            between(prefix+'.integrated_lufs',levels.get('integrated_lufs') if levels else None,criteria['audio']['integrated_lufs'])
            maximum(prefix+'.true_peak_dbtp_max',levels.get('true_peak_dbtp') if levels else None,criteria['audio']['true_peak_dbtp_max'])
            measured[name]={'fps':fps,'duration':duration}
        try:
            cues[name]=parse_srt(out/(name+'.srt'))
        except (OSError,ValueError): pass
        if name in cues and name in expected and expected[name]:
            sub=subtitle_metrics(cues[name],expected[name])
            equal(prefix+'.srt_text_equals_narration',sub['text'],True)
            maximum(prefix+'.cue_start_offset_seconds_max',sub['start'],criteria['subtitles']['cue_start_offset_seconds_max'])
            maximum(prefix+'.cue_end_offset_seconds_max',sub['end'],criteria['subtitles']['cue_end_offset_seconds_max'])
            # This checks timeline text, not independent recognition of audio.
            add(prefix+'.timeline_cta_last',expected[name][-1]['text'],criteria['cta']['text'],expected[name][-1]['text']==criteria['cta']['text'])
    def aggregate(key,keys):
        found=[rows.get(k) for k in keys]
        states=[r['status'] if r else 'UNKNOWN' for r in found]
        rows[key]['value']={k:r['value'] if r else None for k,r in zip(keys,found)}
        rows[key]['status']='FAIL' if 'FAIL' in states else ('PASS' if states and all(s=='PASS' for s in states) else 'UNKNOWN')
    short_names=list(criteria['shorts']['duration_seconds'])
    equal('shorts.count',len(list(out.glob('short[0-9]*.mp4'))),criteria['shorts']['count'])
    for key in ('width','height','codec','pix_fmt','fps'):
        aggregate('shorts.'+key,['shorts.'+name+'.'+key for name in short_names])
    for name in short_names:
        src='shorts.'+name+'.duration_seconds'; target='shorts.duration_seconds.'+name
        if src in rows: rows[target].update(value=rows[src]['value'],status=rows[src]['status'])
    aggregate('audio.integrated_lufs',[('master' if n=='master' else 'shorts.'+n)+'.integrated_lufs' for n in names])
    aggregate('audio.true_peak_dbtp_max',[('master' if n=='master' else 'shorts.'+n)+'.true_peak_dbtp_max' for n in names])
    equal('subtitles.srt_present_for_master_and_each_short',len(cues)==len(names),True)
    for key,suffix in [('text_equals_narration_exactly','srt_text_equals_narration'),('cue_start_offset_seconds_max','cue_start_offset_seconds_max'),('cue_end_offset_seconds_max','cue_end_offset_seconds_max')]:
        aggregate('subtitles.'+key,[('master' if n=='master' else 'shorts.'+n)+'.'+suffix for n in names])
    if shorts and timeline:
        aligned=all(n in expected for n in short_names)
        equal('shorts.source_spans_recorded',all(n in shorts and bool(shorts[n].get('spans')) for n in short_names),True)
        equal('shorts.starts_on_sentence_start',aligned,True)
        equal('shorts.ends_on_sentence_end_or_cta',aligned,True)
        # Source speed is measured from mapped source duration / actual output duration.
        speeds=[]
        for n in short_names:
            duration=measured.get(n,{}).get('duration')
            if duration and n in shorts: speeds.append(shorts[n]['total_s']/duration)
        add('shorts.source_speed',speeds or None,criteria['shorts']['source_speed'],all(criteria['shorts']['source_speed'][0]<=v<=criteria['shorts']['source_speed'][1] for v in speeds) if len(speeds)==len(short_names) else None)
    if scenes:
        ss=scenes.get('scenes',[])
        continuity=bool(ss) and all(a['end_state']==b['start_state'] or bool(b.get('cut_reason')) for a,b in zip(ss,ss[1:]))
        equal('continuity.scene_end_state_equals_next_start_state',continuity,True)
        holds=[s['hold']['seconds'] for s in ss if s.get('hold')]
        maximum('fluidity.hold_seconds_max',max(holds,default=0),criteria['fluidity']['hold_seconds_max'])
        if timing:
            expected_ids=[s['id'] for s in ss]; timed_ids=[s['id'] for s in timing.get('scenes',[])]
            equal('continuity.every_scene_in_scenes_json_rendered',None,True) # timing alone does not prove rendering
            add('timing.scene_ids',timed_ids,expected_ids,timed_ids==expected_ids)
    frames=load(out/'frames.json')
    if frames is None and (out/'frames.json').exists():
        add('continuity.frame_set_contiguous_no_missing_no_duplicate_index','INVALID_FRAME_JSON',True,False)
    if frames is not None and timing and scenes:
        try:
            hold_ranges=[]
            ranges=timing['scenes']
            if (not ranges or ranges[0]['first_frame'] != 0
                    or ranges[-1]['end_frame'] != timing['frames_total']
                    or len({s['id'] for s in ranges}) != len(ranges)
                    or any(s['end_frame'] <= s['first_frame'] for s in ranges)
                    or any(a['end_frame'] != b['first_frame'] for a,b in zip(ranges,ranges[1:]))
                    or timing['fps'] != criteria['master']['fps']):
                raise ValueError('INVALID_TIMING_RANGES')
            tm={s['id']:s for s in ranges}
            for s in scenes['scenes']:
                if s.get('hold'):
                    last=tm[s['id']]['end_frame']; first=last-round(s['hold']['seconds']*timing['fps']); hold_ranges.append((first,last))
            f=frame_metrics(frames,timing['fps'],timing['frames_total'],hold_ranges)
            equal('continuity.frame_set_contiguous_no_missing_no_duplicate_index',f['contiguous'],True)
            minimum('fluidity.unique_frame_ratio_min',f['ratio'],criteria['fluidity']['unique_frame_ratio_min'])
            minimum('fluidity.unique_render_fps_min',f['unique_fps'],criteria['fluidity']['unique_render_fps_min'])
            if f['contiguous'] and [s['id'] for s in timing['scenes']]==[s['id'] for s in scenes['scenes']]:
                equal('continuity.every_scene_in_scenes_json_rendered',True,True)
        except (ValueError,KeyError,TypeError):
            add('continuity.frame_set_contiguous_no_missing_no_duplicate_index','INVALID_FRAMES_OR_TIMING',True,False)
    # No schema exists yet for trusted ASR, voice/music provenance, card-pixel
    # verification, native-render/chunk-rerender evidence or watched review.
    # These rows intentionally stay UNKNOWN rather than trusting arbitrary JSON.
    ordered=list(rows.values())
    status='FAIL' if any(r['status']=='FAIL' for r in ordered) else ('PASS' if all(r['status']=='PASS' for r in ordered) else 'UNKNOWN')
    return {'criteria_sha256':FROZEN_SHA256,'render_id':None,'rows':ordered,'status':status}


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if len(argv)!=2:
        print('usage: qa_animation.py OUT_DIR CRITERIA',file=sys.stderr); return 2
    out=Path(argv[0]); path=Path(argv[1])
    try: raw=path.read_bytes()
    except OSError:
        print('CRITERIA_SHA_MISMATCH',file=sys.stderr); return 2
    if hashlib.sha256(raw).hexdigest()!=FROZEN_SHA256:
        print('CRITERIA_SHA_MISMATCH',file=sys.stderr); return 2
    try:
        report=evaluate(out,json.loads(raw)); out.mkdir(parents=True,exist_ok=True)
        (out/'qa.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        print(report['status']); return 0 if report['status']=='PASS' else 1
    except (OSError,ValueError,KeyError,TypeError) as error:
        print('QA_ERROR '+str(error),file=sys.stderr); return 2

if __name__=='__main__': sys.exit(main())
