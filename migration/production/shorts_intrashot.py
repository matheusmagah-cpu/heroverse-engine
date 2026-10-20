#!/usr/bin/env python3
"""Isolated pilot012 scenic-motion experiment; never an approval or baseline overwrite.

Animate verified lamp/water pixels before captions. Keep the existing camera,
scene clock, film finish and baseline audio. No network or generative API.
usage: shorts_intrashot.py BASELINE SELECTION TIMELINE SCRIPT IMAGES OUT [STRENGTH_0_TO_1]
"""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import shorts_produce as sp
import cinematic

ASSET_HASHES = {
    'bg-lamp-window': 'e751e3c917d9b154aade9ec49f25b1da564626273af0bcb9c6f5be582ca841a8',
    'bg-moonlit-sea': 'a08cf077c6ea6aeef018f5ca066aa75dfd138093aa5804e33691a1b57e5a9eb1',
}
BASELINE_SHA256 = 'c135476a1d5a27da217ad289035cc6fe7d76500837c6ef6fb8a62fa037e9d029'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pcm_sha(path):
    data = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0',
                                    '-f', 's16le', '-acodec', 'pcm_s16le', '-'])
    return hashlib.sha256(data).hexdigest()


def mux_args(video, baseline, output):
    return ['ffmpeg','-v','error','-y','-i',str(video),'-i',str(baseline),
            '-map','0:v:0','-map','1:a:0','-c','copy','-movflags','+faststart',str(output)]


def smooth(x):
    x = np.clip(x, 0, 1)
    return x*x*(3-2*x)


class Intrashot:
    """Scene-local pixel animation; moon/sky excluded from the water transform."""
    def __init__(self, image, kind):
        if kind not in ('lamp', 'water'):
            raise ValueError('UNKNOWN_SCENE')
        self.image = image
        self.kind = kind
        h, w = image.shape[:2]
        self.x, self.y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        self.u, self.v = self.x / w, self.y / h
        if kind == 'lamp':
            # Coordinates refer to the verified full-height portrait crop.
            flame = np.exp(-((self.u-.028)/.047)**2-((self.v-.50)/.085)**2)
            spill = np.exp(-((self.u-.12)/.31)**2-((self.v-.63)/.23)**2)
            self.mask = np.where(spill > .006, spill, 0).astype(np.float32)
            self.flame = np.where(flame > .006, flame, 0).astype(np.float32)
        else:
            # Soft horizon ramp: preserve sky, moon and distant horizon exactly.
            self.mask = smooth((self.v-.425)/.13).astype(np.float32)

    def frame(self, seconds, strength=1.0):
        import cv2
        if not math.isfinite(seconds) or not 0 <= strength <= 1:
            raise ValueError('INVALID_TIME_OR_STRENGTH')
        if strength == 0:
            return self.image.copy()
        if self.kind == 'lamp':
            pulse = .65*np.sin(seconds*2.1)+.35*np.sin(seconds*3.7+.6)
            dy = 3.0*(self.image.shape[0]/1920)*self.flame*np.sin(seconds*2.5)*strength
            warped = cv2.remap(self.image, self.x, (self.y+dy).astype(np.float32), cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT_101)
            # BGR warmth: restrained spill from the existing flame, not a flash.
            gain = self.mask[...,None]*np.array([.018,.045,.065],np.float32)*pulse*strength
            return np.clip(np.rint(warped.astype(np.float32)*(1+gain)),0,255).astype(np.uint8)
        depth = smooth((self.v-.425)/.575)
        amplitude = (1.0+6.0*depth)*(self.image.shape[1]/1080)*self.mask*strength
        phase = self.v*29-self.u*4-seconds*1.15
        dx = amplitude*np.sin(phase)
        dy = .38*amplitude*np.sin(phase*.8+.7)
        warped = cv2.remap(self.image,(self.x+dx).astype(np.float32),(self.y+dy).astype(np.float32),cv2.INTER_CUBIC,borderMode=cv2.BORDER_REFLECT_101)
        shimmer = .022*self.mask*np.sin(self.v*37-self.u*3-seconds*1.6)*strength
        return np.clip(np.rint(warped.astype(np.float32)*(1+shimmer[...,None])),0,255).astype(np.uint8)


def camera(frame, index, count):
    import cv2
    h,w=frame.shape[:2]
    zoom=1.0+.06*index/max(count-1,1)
    matrix=np.array([[zoom,0,(1-zoom)*(w-1)/2],[0,zoom,(1-zoom)*(h-1)/2]],np.float32)
    return cv2.warpAffine(frame,matrix,(w,h),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REFLECT_101)


def render(baseline, selection, timeline_path, script_path, images, output, motion_strength=1.0):
    import cv2
    if not math.isfinite(motion_strength) or not 0 <= motion_strength <= 1:
        raise ValueError("INVALID_MOTION_STRENGTH")
    baseline,images,output=Path(baseline),Path(images),Path(output)
    protected=[baseline,Path(selection),Path(timeline_path),Path(script_path)]
    protected.extend(images/(name+'.png') for name in ASSET_HASHES)
    work=output.parent/'intrashot-work'
    if output.resolve() in {p.resolve() for p in protected}:raise ValueError('SOURCE_OVERWRITE_FORBIDDEN')
    if any(p.resolve().is_relative_to(work.resolve()) for p in protected):
        raise ValueError('WORK_DIRECTORY_OVERLAPS_SOURCE')
    if sha(baseline)!=BASELINE_SHA256:raise ValueError('BASELINE_HASH_MISMATCH')
    for name,digest in ASSET_HASHES.items():
        if sha(images/(name+'.png'))!=digest:raise ValueError('ASSET_HASH_MISMATCH')
    sel=json.loads(Path(selection).read_text());timeline=json.loads(Path(timeline_path).read_text());script=json.loads(Path(script_path).read_text())
    moment,reason=sp.snap(sel['chosen'][0],timeline['sentences'])
    if reason:raise ValueError(reason)
    duration=moment['end']-moment['start']+sp.TAIL_S
    if sp.scene_plan(duration)[0]!=2:raise ValueError('TWO_SCENE_EXPERIMENT_ONLY')
    count=round(duration*30);output.parent.mkdir(parents=True,exist_ok=True)
    work.mkdir(exist_ok=True)
    scenes=[]
    for name,kind in [('bg-lamp-window','lamp'),('bg-moonlit-sea','water')]:
        p=work/(name+'.png');sp.vertical_still(images/(name+'.png'),p);cinematic.grade(p)
        scenes.append(Intrashot(cv2.imread(str(p)),kind))
    refs={s['id']:s.get('reference') for s in script['segments']}
    captions=work/'captions.ass';captions.write_text(sp.ass(moment,sp.nonredundant_hook(moment,moment.get('hook')),refs,duration,timeline['sentences']))
    if any(c in str(captions) for c in "':,[];"):raise ValueError('UNSAFE_PATH')
    look=cinematic.look(1080,1920)+f',ass={captions},fade=t=out:st={duration-sp.TAIL_S:.3f}:d={sp.TAIL_S:.3f},format=yuv420p'
    video_only=work/'video-only.mp4'
    cmd=['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s','1080x1920','-r','30','-i','-',
         '-filter_complex','[0:v]'+look+'[v]', '-map','[v]','-an',
         '-c:v','libx264','-preset','medium','-crf','19','-threads','2','-frames:v',str(count),
         '-movflags','+faststart',str(video_only)]
    process=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    blend_start=duration/2-sp.FADE_S/2
    try:
        for i in range(count):
            t=i/30
            alpha=float(np.clip((t-blend_start)/sp.FADE_S,0,1))
            # A stronger, still restrained opening; water settles towards closure.
            lamp_strength=.55+.45*float(1-smooth((t-3)/3))
            water_strength=1-.30*float(smooth((t-(duration-6))/5.5))
            if alpha==0:frame=scenes[0].frame(t,lamp_strength*motion_strength)
            elif alpha==1:frame=scenes[1].frame(t,water_strength*motion_strength)
            else:frame=cv2.addWeighted(scenes[0].frame(t,lamp_strength*motion_strength),1-alpha,scenes[1].frame(t,water_strength*motion_strength),alpha,0)
            process.stdin.write(camera(frame,i,count).tobytes())
    except BaseException:
        process.terminate()
        try:
            process.stdin.close()
        except BrokenPipeError:
            pass
        process.wait()
        raise
    else:
        process.stdin.close()
    if process.wait():raise RuntimeError('RENDER_FAILED')
    # Mux separately: -frames:v on a combined encode truncates the last AAC packet.
    subprocess.run(mux_args(video_only,baseline,output),check=True)
    before,after=pcm_sha(baseline),pcm_sha(output)
    if before!=after:raise RuntimeError('AUDIO_CHANGED')
    measurements={'baseline_sha256':sha(baseline),'candidate_sha256':sha(output),'frames':count,'seconds':duration,
                  'audio_decoded_sha256':before,'audio_identical':True,'motion_strength':motion_strength,'asset_sha256':ASSET_HASHES,'publish':False,
                  'motion':'localized flame/light and water' if motion_strength else 'CONTROL_NO_INTRASHOT_MOTION',
                  'camera':'same1.00-1.06 camera','creative_review':'NOT_RUN'}
    output.with_suffix('.json').write_text(json.dumps(measurements,indent=2)+'\n')
    return measurements


if __name__=='__main__':
    print(json.dumps(render(*sys.argv[1:7], motion_strength=float(sys.argv[7]) if len(sys.argv)>7 else 1.0)))
