#!/usr/bin/env python3
"""Offline synthetic AV controls. Python stdlib + local ffmpeg/ffprobe only.
WARNING: this script and operator-only/ contain answers; never send to evaluator.
"""
import argparse, array, hashlib, json, math, platform, subprocess, sys, tempfile, wave
from pathlib import Path
from fractions import Fraction

W, H, FPS, SECONDS, SR = 320, 240, 30, 6, 48000
FLASH_STARTS = [1.0, 3.0, 5.0]
PULSE_SECONDS, RAMP_SECONDS, HZ, AMPLITUDE = .1, .005, 1000, .25
# Intentionally arbitrary IDs, not meaningful names or condition ordering.
CASES = [
    ('c01.mp4', 'audio_late_500ms', True, .5),
    ('c02.mp4', 'constant_image_with_tones', False, 0),
    ('c03.mp4', 'digital_silence', True, None),
    ('c04.mp4', 'audio_aligned', True, 0),
    ('c05.mp4', 'audio_early_500ms', True, -.5),
]

def run(args, **kw):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw).stdout

def digest(data):
    return hashlib.sha256(data).hexdigest()

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def require(ok, message):
    if not ok:
        raise AssertionError(message)

def ffprobe(path, args):
    return json.loads(run(['ffprobe','-v','error',*args,'-of','json',str(path)]))

def frame(flash):
    y = bytearray([32]) * (W*H)
    # Neutral fixed square, central 80x80; no text or answer cue.
    for row in range(80,160):
        y[row*W+120:row*W+200] = bytes([235 if flash else 80])*80
    return bytes(y) + bytes([128])*(W*H//2)

def make_video(path, flashing):
    normal, light = frame(False), frame(True)
    command = ['ffmpeg','-hide_banner','-loglevel','error','-y',
        '-f','rawvideo','-pixel_format','yuv420p','-video_size',f'{W}x{H}',
        '-framerate',str(FPS),'-i','pipe:0','-an','-c:v','libx264',
        '-preset','medium','-crf','18','-threads','1','-bf','0','-g','30',
        '-pix_fmt','yuv420p','-video_track_timescale','15360',
        '-map_metadata','-1','-fflags','+bitexact','-flags:v','+bitexact',
        '-movflags','+faststart',str(path)]
    p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for index in range(FPS*SECONDS):
        on = flashing and any(int(t*FPS) <= index < int(t*FPS)+3 for t in FLASH_STARTS)
        p.stdin.write(light if on else normal)
    p.stdin.close()
    stderr = p.stderr.read()
    p.wait()
    require(p.returncode == 0, stderr.decode())

def make_pcm(path, offset):
    samples = array.array('h', [0])*(SR*SECONDS)
    if offset is not None:
        length, ramp = round(PULSE_SECONDS*SR), round(RAMP_SECONDS*SR)
        for onset in FLASH_STARTS:
            start = round((onset+offset)*SR)
            for i in range(length):
                # Linear 5 ms attack/release; deterministic 1 kHz sine.
                envelope = min(1.0, i/ramp, (length-1-i)/ramp)
                samples[start+i] = round(32767*AMPLITUDE*envelope*math.sin(2*math.pi*HZ*i/SR))
    if sys.byteorder != 'little': samples.byteswap()
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR); f.writeframes(samples.tobytes())
    return {'sha256_pcm_s16le':digest(samples.tobytes()),'sample_count':SR*SECONDS,
            'all_samples_zero':offset is None}

def build(root):
    (root/'stimuli').mkdir(parents=True, exist_ok=True)
    sources = {}
    with tempfile.TemporaryDirectory(prefix='av_control_') as tmp:
        tmp = Path(tmp)
        for flashing in (False, True):
            make_video(tmp/f'v{int(flashing)}.mp4',flashing)
        for name, condition, flashing, offset in CASES:
            sources[name] = make_pcm(tmp/'audio.wav',offset)
            run(['ffmpeg','-hide_banner','-loglevel','error','-y',
                '-i',str(tmp/f'v{int(flashing)}.mp4'),'-i',str(tmp/'audio.wav'),
                '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac',
                '-profile:a','aac_low','-b:a','128k','-ar',str(SR),'-ac','1',
                '-threads','1','-t',str(SECONDS),'-map_metadata','-1',
                '-fflags','+bitexact','-flags:a','+bitexact',
                '-movflags','+faststart',str(root/'stimuli'/name)])
    return sources

def contiguous_ranges(indices):
    groups=[]
    for value in indices:
        if not groups or value != groups[-1][-1]+1: groups.append([])
        groups[-1].append(value)
    return groups

def analyze(root, source_pcm):
    records=[]
    frames_out, pts_out, probes_out = {}, {}, {}
    flash_hashes=[]
    for name, condition, flashing, offset in CASES:
        path=root/'stimuli'/name
        probe=ffprobe(path,['-show_format','-show_streams'])
        probes_out[name]=probe
        video=[s for s in probe['streams'] if s['codec_type']=='video'][0]
        audio=[s for s in probe['streams'] if s['codec_type']=='audio'][0]
        require(video['codec_name']=='h264' and audio['codec_name']=='aac',f'{name}: codecs')
        require(video['width']==W and video['height']==H and video['pix_fmt']=='yuv420p',f'{name}: pixels')
        require(Fraction(video['avg_frame_rate'])==FPS,f'{name}: FPS')
        require(int(audio['sample_rate'])==SR and audio['channels']==1,f'{name}: audio specs')
        for obj in (video,audio,probe['format']):
            require(abs(float(obj['duration'])-SECONDS)<1e-6,f'{name}: duration')
            require(abs(float(obj['start_time']))<1e-6,f'{name}: start time')
        raw=run(['ffmpeg','-v','error','-i',str(path),'-map','0:v:0','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','yuv420p','pipe:1'])
        size=W*H*3//2
        require(len(raw)==size*FPS*SECONDS,f'{name}: frame count')
        means=[]
        for idx in range(FPS*SECONDS):
            # Inner 40x40 avoids block boundary artifacts.
            means.append(sum(raw[idx*size+r*W+c] for r in range(100,140) for c in range(140,180))/1600)
        unique_frame_hashes={digest(raw[i*size:(i+1)*size]) for i in range(FPS*SECONDS)}
        if not flashing: require(len(unique_frame_hashes)==1,f'{name}: supposedly constant image changed')
        flashframes=[i for i,value in enumerate(means) if value>200]
        expected=[round(t*FPS)+j for t in FLASH_STARTS for j in range(3)] if flashing else []
        require(flashframes==expected,f'{name}: unexpected flash frames {flashframes}')
        frames_out[name]={'center_luma_by_frame':means,'flash_frames':flashframes}
        if flashing: flash_hashes.append(digest(raw))
        vframes=ffprobe(path,['-select_streams','v:0','-show_frames'])['frames']
        vp=[float(f['best_effort_timestamp_time']) for f in vframes]
        require(len(vp)==FPS*SECONDS and all(abs(t-i/FPS)<1e-6 for i,t in enumerate(vp)),f'{name}: video PTS')
        aframes=ffprobe(path,['-select_streams','a:0','-show_frames'])['frames']
        ap=[float(f['best_effort_timestamp_time']) for f in aframes]
        require(ap[0]==0 and all(ap[i]<ap[i+1] for i in range(len(ap)-1)),f'{name}: audio frame PTS')
        # AAC decoder frame sizes are 1024 samples. Track time is exact; last decoded frame may pad.
        require(all(abs(ap[i+1]-ap[i]-aframes[i]['nb_samples']/SR)<2e-6 for i in range(len(ap)-1)),f'{name}: audio PTS continuity')
        packets=ffprobe(path,['-select_streams','a:0','-show_packets'])['packets']
        pkt_pts=[float(p['pts_time']) for p in packets]
        require(all(pkt_pts[i]<pkt_pts[i+1] for i in range(len(pkt_pts)-1)),f'{name}: packet PTS monotonic')
        require(abs(float(packets[-1]['pts_time'])+float(packets[-1]['duration_time'])-SECONDS)<2e-6,f'{name}: packet end')
        pts_out[name]={
            'video_frame_pts_seconds':vp,'audio_decoded_frame_pts_seconds':ap,
            'audio_decoded_frame_nb_samples':[f['nb_samples'] for f in aframes],
            'audio_packets':[{'pts_time':p.get('pts_time'),'dts_time':p.get('dts_time'),
                              'duration_time':p.get('duration_time'),'side_data_list':p.get('side_data_list',[])} for p in packets]}
        pcm=run(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-c:a','pcm_f32le','-f','f32le','pipe:1'])
        samples=array.array('f');samples.frombytes(pcm)
        if sys.byteorder!='little':samples.byteswap()
        require(all(math.isfinite(s) for s in samples),f'{name}: nonfinite PCM')
        require(len(samples)>=SR*SECONDS,f'{name}: missing decoded samples')
        nonzero=sum(s!=0 for s in samples)
        blocks=[math.sqrt(sum(float(s)**2 for s in samples[i:i+48])/len(samples[i:i+48])) for i in range(0,len(samples),48)]
        active=contiguous_ranges([i for i,rms in enumerate(blocks) if rms>=.02])
        observed=[{'start_seconds':g[0]/1000,'end_seconds_exclusive':(g[-1]+1)/1000} for g in active]
        expected_tones=[] if offset is None else [t+offset for t in FLASH_STARTS]
        require(len(active)==len(expected_tones),f'{name}: pulse count {observed}')
        frequencies=[]
        for group,expected_start in zip(active,expected_tones):
            require(abs(group[0]/1000-expected_start)<.015,f'{name}: onset')
            require(abs((group[-1]+1)/1000-(expected_start+PULSE_SECONDS))<.015,f'{name}: offset')
            segment=samples[round((expected_start+.025)*SR):round((expected_start+.075)*SR)]
            crossings=sum(segment[i]<=0<segment[i+1] for i in range(len(segment)-1))
            frequency=crossings/(len(segment)/SR)
            require(abs(frequency-HZ)<=25,f'{name}: frequency {frequency}')
            frequencies.append(frequency)
        if offset is None: require(nonzero==0,f'{name}: decoded silence is not exactly zero')
        tail=samples[SR*SECONDS:]
        require(all(s==0 for s in tail),f'{name}: nonzero AAC tail padding')
        timing=[round(o['start_seconds']-f,6) for o,f in zip(observed,FLASH_STARTS)] if flashing and offset is not None else []
        record={
            'filename':name,'condition':condition,'size_bytes':path.stat().st_size,'sha256':digest(path.read_bytes()),
            'video':{'codec':video['codec_name'],'profile':video.get('profile'),'width':W,'height':H,'pix_fmt':video['pix_fmt'],'fps':FPS,
                     'frames':len(vp),'unique_decoded_frames':len(unique_frame_hashes),'duration_seconds':float(video['duration']),'time_base':video['time_base'],
                     'first_pts_seconds':vp[0],'last_pts_seconds':vp[-1],'decoded_yuv420p_sha256':digest(raw),
                     'flash_start_seconds':[vp[g[0]] for g in contiguous_ranges(flashframes)],'flash_frame_indices':flashframes},
            'audio':{'codec':audio['codec_name'],'profile':audio.get('profile'),'sample_rate':SR,'channels':audio['channels'],
                     'duration_seconds':float(audio['duration']),'time_base':audio['time_base'],
                     'source_pcm':source_pcm.get(name),'decoded_f32le_sha256':digest(pcm),'decoded_sample_count':len(samples),
                     'decoded_nonzero_samples':nonzero,'decoded_all_samples_exactly_zero':nonzero==0,
                     'decoded_peak_absolute':max(abs(s) for s in samples),'decoded_tail_samples_outside_track':len(tail),
                     'tail_outside_track_exactly_zero':all(s==0 for s in tail),
                     'expected_tone_start_seconds':expected_tones,'observed_tone_intervals_seconds':observed,
                     'observed_frequency_zero_crossing_hz':frequencies,'tone_onset_minus_flash_seconds':timing,
                     'first_packet_pts_seconds':pkt_pts[0],'first_packet_skip_samples':packets[0].get('side_data_list',[]),
                     'decoded_first_frame_pts_seconds':ap[0],'decoded_last_frame_pts_seconds':ap[-1],
                     'nominal_audio_shift_seconds':offset},'verification':'PASS'}
        records.append(record)
    require(len(set(flash_hashes))==1,'Four flashing cases must have identical decoded video')
    private=root/'operator-only';private.mkdir(exist_ok=True)
    dump(private/'frame-measurements.json',frames_out)
    dump(private/'pts-evidence.json',pts_out)
    dump(private/'probe-evidence.json',probes_out)
    manifest={
        'schema_version':1,'purpose':'Channel access and coarse audiovisual offset triage only; not model approval or fine synchrony accuracy.',
        'do_not_give_to_evaluator':True,'contains_user_data':False,
        'tools':{'ffmpeg':run(['ffmpeg','-version']).decode().splitlines()[0],
                 'ffprobe':run(['ffprobe','-version']).decode().splitlines()[0],'python':platform.python_version()},
        'recipe':{'duration_seconds':SECONDS,'fps':FPS,'resolution':[W,H],'flash_duration_frames':3,
                  'tone_hz':HZ,'tone_duration_seconds':PULSE_SECONDS,'linear_ramp_seconds':RAMP_SECONDS,
                  'peak_source_amplitude_full_scale':AMPLITUDE,'source_audio':'PCM signed 16-bit mono 48000 Hz'},
        'measurement_method':{'flash':'Decoded Y plane center 40x40 average > 200; source levels 80/235.',
                              'tone':'Decoded PCM float32; RMS of nonoverlapping 48-sample (1 ms) windows >= 0.02 full scale. Report first and end-exclusive active window.',
                              'onset_tolerance_seconds':.015,'frequency':'Positive zero crossings on central 50 ms plateau; 20 Hz bin resolution.',
                              'silence':'Every decoded float sample must equal zero, including AAC padding.',
                              'timing_sign':'Positive audio onset minus flash means sound lags; negative means sound leads.',
                              'limitations':'AAC preecho, ramps and RMS threshold make these operational onsets, not perceptual or sample-accurate onset estimates.'},
        'files':records,'cross_file_checks':{'identical_decoded_video_for_four_flashing_cases':True},
        'all_checks_passed':True}
    dump(private/'manifest.json',manifest)
    (private/'SHA256SUMS.stimuli').write_text(''.join(f"{r['sha256']}  stimuli/{r['filename']}\n" for r in records))
    return manifest

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--verify-only',action='store_true');p.add_argument('--check-reproducibility',action='store_true');args=p.parse_args()
    root=args.output.resolve()
    source={}
    if args.verify_only:
        previous=root/'operator-only'/'manifest.json'
        if previous.exists(): source={r['filename']:r['audio']['source_pcm'] for r in json.loads(previous.read_text())['files']}
    else: source=build(root)
    manifest=analyze(root,source)
    if args.check_reproducibility:
        with tempfile.TemporaryDirectory(prefix='av_rebuild_') as tmp:
            other=Path(tmp);build(other)
            hashes={name:digest((other/'stimuli'/name).read_bytes()) for name,*_ in CASES}
            for record in manifest['files']:
                require(hashes[record['filename']]==record['sha256'],f"Nonreproducible: {record['filename']}")
        dump(root/'operator-only'/'reproducibility.json',{'same_toolchain_second_build_byte_identical':True,'sha256':hashes,
              'scope':'Two independent builds with this installed toolchain. Cross-version byte identity is not promised.'})
    print(json.dumps({'all_checks_passed':manifest['all_checks_passed'],'files':[
        {'file':r['filename'],'bytes':r['size_bytes'],'sha256':r['sha256'],'condition':r['condition'],
         'observed_tones':r['audio']['observed_tone_intervals_seconds'],'delta_seconds':r['audio']['tone_onset_minus_flash_seconds'],
         'zero_samples':r['audio']['decoded_all_samples_exactly_zero']} for r in manifest['files']]},indent=2))

if __name__=='__main__': main()
