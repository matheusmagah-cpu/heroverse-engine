#!/usr/bin/env python3
"""Assemble native animation frames with timeline-exact audio and captions."""
from pathlib import Path


def timestamp(seconds):
    """SRT uses milliseconds; round once before decomposing the clock."""
    milliseconds = round(seconds * 1000)
    if milliseconds < 0:
        raise ValueError('NEGATIVE_CUE_TIME')
    seconds, ms = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'


def write_srt(path, sentences):
    blocks = []
    for index, sentence in enumerate(sentences, 1):
        if sentence['end'] <= sentence['start']:
            raise ValueError('INVALID_CUE_RANGE')
        blocks.append(f"{index}\n{timestamp(sentence['start'])} --> {timestamp(sentence['end'])}\n{sentence['text']}\n")
    Path(path).write_text('\n'.join(blocks), encoding='utf-8')

import argparse
import hashlib
import json
import math
import re
import subprocess
import tempfile
import struct

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def run(args):
    result = subprocess.run(args, text=True, capture_output=True, timeout=900)
    if result.returncode:
        raise RuntimeError('COMMAND_FAILED '+result.stderr[-3000:])
    return result


def read(path):
    return json.loads(Path(path).read_text())


def short_sentences(timeline, mapping):
    result=[];cursor=0
    for span in mapping['spans']:
        start,end=span['master_start_s'],span['master_end_s']
        selected=[s for s in timeline['sentences'] if s['segment']==span['scene'] and s['start']>=start and s['end']<=end]
        if not selected or selected[0]['start']!=start or selected[-1]['end']!=end:
            raise ValueError('SHORT_SENTENCE_BOUNDARY')
        result.extend(dict(s,start=cursor+s['start']-start,end=cursor+s['end']-start) for s in selected)
        cursor+=end-start
    if abs(cursor-mapping['total_s'])>.001:raise ValueError('SHORT_TOTAL')
    return result


def ass_time(seconds):
    cs=round(seconds*100);minutes,cs=divmod(cs,6000);hours,minutes=divmod(minutes,60);seconds,cs=divmod(cs,100)
    return f'{hours}:{minutes:02}:{seconds:02}.{cs:02}'


def safe_text(text):
    if any(c in text for c in '{}\\\r\n'):raise ValueError('UNSAFE_CAPTION_TEXT')
    return text


def write_ass(path,sentences,scenes,vertical):
    width,height=(1080,1920) if vertical else (1920,1080)
    header=f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,48,&H00FFFFFF,&H00FFFFFF,&H00151515,&H80151515,0,0,0,0,100,100,0,0,1,3,1,2,50,50,100,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events=[]
    def event(start,end,text,x,y,size=48):
        events.append(f'Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{{\\an5\\pos({x},{y})\\fs{size}}}{text}')
    byid={s['id']:s for s in scenes['scenes']}
    for sentence in sentences:
        start,end=sentence['start'],sentence['end'];text=safe_text(sentence['text'])
        if vertical:
            # Parallel phrase lines share actual sentence boundaries. No
            # fabricated word alignment or proportional speech timestamps.
            words=text.split();phrases=[' '.join(words[i:i+5]) for i in range(0,len(words),5)]
            for n,phrase in enumerate(phrases):event(start,end,phrase,width//2,height-220-(len(phrases)-1-n)*62)
        overlay=byid.get(sentence['segment'],{}).get('overlay',{})
        if overlay.get('verse_card') and overlay['verse_card'] in text:
            quote=safe_text(overlay['verse_card']);ref=safe_text(overlay['reference'])
            # Quote display is bounded by its actual spoken sentence.
            lines=[quote,ref] if not vertical else ['Thou shalt love thy','neighbour as thyself.',ref]
            for n,line in enumerate(lines):event(start,end,line,width//2,180+n*60,44 if vertical else 48)
        if overlay.get('cta_card'):
            if text!=overlay['cta_card']:raise ValueError('CTA_TEXT_MISMATCH')
            # Explicit line breaks affect layout only, not text content.
            words=text.split();groups=[' '.join(words[i:i+(5 if vertical else 10)]) for i in range(0,len(words),5 if vertical else 10)]
            for n,line in enumerate(groups):event(start,end,line,width//2,240+n*60)
    Path(path).write_text(header+'\n'.join(events)+'\n')


def mean_volume(path):
    log=run(['ffmpeg','-nostdin','-v','info','-i',str(path),'-af','volumedetect','-f','null','-']).stderr
    match=re.search(r'mean_volume:\s*([-\d.]+) dB',log)
    if not match:raise ValueError('UNMEASURABLE_AUDIO')
    return float(match.group(1))


def normalize(source,dest):
    options='I=-15:TP=-1.5:LRA=11'
    log=run(['ffmpeg','-nostdin','-v','info','-i',str(source),'-af','loudnorm='+options+':print_format=json','-f','null','-']).stderr
    data=json.loads(log[log.rfind('{'):log.rfind('}')+1])
    fields={'measured_I':'input_i','measured_TP':'input_tp','measured_LRA':'input_lra','measured_thresh':'input_thresh','offset':'target_offset'}
    if not all(math.isfinite(float(data[k])) for k in fields.values()):raise ValueError('INVALID_LOUDNESS')
    filter_='loudnorm='+options+':'+':'.join(k+'='+data[v] for k,v in fields.items())+':linear=true'
    run(['ffmpeg','-y','-nostdin','-v','error','-i',str(source),'-af',filter_,'-ar','48000','-ac','2',str(dest)])


def assemble(work,scenes_path,timing_path,map_path,music,out):
    work=Path(work);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    scenes=read(scenes_path);timing=read(timing_path);maps=read(map_path);timeline=read(work/'timeline.json')
    if timing['fps']!=24:raise ValueError('FPS_24_REQUIRED')
    if not Path(FONT).is_file():raise ValueError('DEJAVU_REQUIRED')
    if abs(timing['frames_total']/24-timeline['voice_seconds'])>1/24:raise ValueError('VOICE_TIMING_MISMATCH')
    source=work/'voice.wav';voice_level=mean_volume(source);music_level=mean_volume(music)
    gain=voice_level-music_level-16 # headroom beyond the required 12dB integrated separation
    evidence={'voice_mean_db':voice_level,'music_mean_db_before_gain':music_level,'music_gain_db':gain,'mean_separation_db':16,'phrase_timing':'parallel lines, each 1-5 words, all using source sentence timestamps','outputs':{}}
    with tempfile.TemporaryDirectory(prefix='assembly-',dir=out) as temp:
        temp=Path(temp)
        mixed=temp/'mixed.wav'
        run(['ffmpeg','-y','-nostdin','-v','error','-i',str(source),'-stream_loop','-1','-i',str(music),'-filter_complex',f'[1:a]volume={gain}dB[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]','-map','[a]','-ar','48000','-ac','2',str(mixed)])
        for name in ['master','short1','short2']:
            vertical=name!='master';sentences=short_sentences(timeline,maps[name]) if vertical else timeline['sentences']
            if vertical and sentences[-1]['text']!=next(s['overlay']['cta_card'] for s in scenes['scenes'] if s.get('overlay',{}).get('cta_card')):raise ValueError('SHORT_CTA_REQUIRED')
            duration=maps[name]['total_s'] if vertical else timeline['voice_seconds']
            count=sum(round(s['master_end_s']*24)-round(s['master_start_s']*24) for s in maps[name]['spans']) if vertical else timing['frames_total']
            folder=work/('vertical-frames' if vertical else 'hd-frames');pattern=(name+'-%05d.png') if vertical else '%05d.png'
            for index in range(count):
                frame=folder/(pattern%index)
                if not frame.is_file():raise ValueError('MISSING_FRAME '+str(index))
                with frame.open('rb') as stream:header=stream.read(24)
                expected=(1080,1920) if vertical else (1920,1080)
                if header[:8]!=b'\x89PNG\r\n\x1a\n' or len(header)<24 or struct.unpack('>II',header[16:24])!=expected:raise ValueError('NATIVE_FRAME_DIMENSIONS')
            audio=temp/(name+'-cut.wav')
            if vertical:
                parts=[];labels=[]
                for i,span in enumerate(maps[name]['spans']):
                    parts.append(f"[0:a]atrim=start={span['master_start_s']}:end={span['master_end_s']},asetpts=PTS-STARTPTS[a{i}]");labels.append(f'[a{i}]')
                parts.append(''.join(labels)+f'concat=n={len(labels)}:v=0:a=1[a]')
                run(['ffmpeg','-y','-nostdin','-v','error','-i',str(mixed),'-filter_complex',';'.join(parts),'-map','[a]',str(audio)])
            else:audio=mixed
            normalized=temp/(name+'-normalized.wav');normalize(audio,normalized)
            write_srt(out/(name+'.srt'),sentences);ass=temp/(name+'.ass');write_ass(ass,sentences,scenes,vertical)
            # Paths generated under a controlled temporary directory; reject
            # filter metacharacters rather than interpolating unsafe paths.
            if any(c in str(ass) for c in "':,[];"):raise ValueError('UNSAFE_OUTPUT_PATH')
            filters=f"subtitles=filename='{ass}':fontsdir=/usr/share/fonts/truetype/dejavu"
            if not vertical:filters+=f',fade=t=out:st={max(0,duration-.5)}:d=0.5'
            dest=out/(name+'.mp4')
            run(['ffmpeg','-y','-nostdin','-v','error','-framerate','24','-i',str(folder/pattern),'-i',str(normalized),'-vf',filters,'-frames:v',str(count),'-t',str(duration),'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-r','24','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-movflags','+faststart',str(dest)])
            evidence['outputs'][name]={'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'frames':count,'seconds':duration}
    (out/'assembly-measurements.json').write_text(json.dumps(evidence,indent=2)+'\n')
    return evidence


def main():
    p=argparse.ArgumentParser()
    for name in ['work','scenes','timing','shorts_map','music','out']:p.add_argument(name)
    args=p.parse_args();assemble(args.work,args.scenes,args.timing,args.shorts_map,args.music,args.out)


if __name__=='__main__':main()
