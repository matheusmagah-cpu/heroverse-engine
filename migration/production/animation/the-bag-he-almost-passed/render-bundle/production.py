"""Headless deterministic 24fps native-camera animation. No external assets."""
import argparse, hashlib, json, math, os, sys, time, resource
from pathlib import Path
import bpy
from mathutils import Vector
sys.dont_write_bytecode=True
if not os.environ.get('RENDER_OUT'):raise ValueError('RENDER_OUT_REQUIRED')
cache_root=Path(os.environ['RENDER_OUT']).resolve()/'cache'
os.environ['XDG_CACHE_HOME']=str(cache_root)
os.environ['MESA_SHADER_CACHE_DIR']=str(cache_root/'mesa')
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from scene_base import s, cam, box, uv, M, bread, bag
from characters import Character
from png_manifest import canonical_png
from frame_mapping import short_frames


def smooth(u):
    u=max(0,min(1,u));return u*u*(3-2*u)


def mix(a,b,u):return a+(b-a)*smooth(u)


def load(path):return json.loads(Path(path).read_text())


def validate_timing(timing):
    rows=timing['scenes']
    if timing['fps']!=24 or rows[0]['first_frame']!=0 or rows[-1]['end_frame']!=timing['frames_total']:
        raise ValueError('INVALID_TIMING')
    if any(a['end_frame']!=b['first_frame'] for a,b in zip(rows,rows[1:])) or any(r['end_frame']<=r['first_frame'] for r in rows):raise ValueError('NONCONTIGUOUS_TIMING')
    if [r['id'] for r in rows]!=[f'S{i:02d}' for i in range(1,16)]:raise ValueError('SCENE_IDS')


args=sys.argv[sys.argv.index('--')+1:]
p=argparse.ArgumentParser();p.add_argument('kind',choices=['master','vertical']);p.add_argument('start',type=int);p.add_argument('end',type=int);p.add_argument('--timing',required=True);p.add_argument('--shorts')
a=p.parse_args(args)
if bpy.app.version[:3]!=(4,3,2):raise RuntimeError('BLENDER_4_3_2_REQUIRED')
if not os.environ.get('RENDER_OUT'):raise ValueError('RENDER_OUT_REQUIRED')
out=Path(os.environ['RENDER_OUT']).resolve();out.mkdir(parents=True,exist_ok=True)
os.environ['XDG_CACHE_HOME']=str(out/'cache')
os.environ['MESA_SHADER_CACHE_DIR']=str(out/'cache'/'mesa')
timing=load(a.timing);validate_timing(timing)
s.render.fps=24;s.render.resolution_percentage=100;s.render.image_settings.color_mode='RGB';s.render.image_settings.compression=15
s.render.film_transparent=False;s.render.use_file_extension=True;s.render.use_stamp=False
for prop in s.render.bl_rna.properties:
    if prop.identifier.startswith('use_stamp'):setattr(s.render,prop.identifier,False)
s.render.threads_mode='FIXED';s.render.threads=max(1,bpy.context.scene.render.threads)
# Existing original environment is retained, relocated around the bench origin.
for ob in bpy.data.objects:
    if ob.name.startswith('Bench'):ob.location.x-=2.8
bag.hide_render=True
bagroot=bpy.data.objects.new('Paper bag',None);bpy.context.collection.objects.link(bagroot)
for name,pos,size in [('bottom',(0,0,.02),(.42,.29,.04)),('front',(0,-.145,.22),(.42,.03,.42)),('back',(0,.145,.22),(.42,.03,.42)),('left',(-.21,0,.22),(.03,.29,.42)),('right',(.21,0,.22),(.03,.29,.42))]:
    obj=box('Paper '+name,pos,size,'bag',.01);obj.parent=bagroot
loaves=[bread,uv('Wrapped loaf A',(0,0,0),(.24,.11,.10),'white'),uv('Wrapped loaf B',(0,0,0),(.24,.11,.10),'white')]
young=Character('Daniel',False,M);elder=Character('Eli',True,M)
# Exact story endpoints: bench at x=0, distance specified in metres.
DX=[-9,-6,-3,1,4,5,5,1,.7,.7,.7,.7,-.7,-2.1,-4,-4.7]
EY=.35


def set_camera(index,u,dx,ex,vertical):
    # Perspective lenses and independent portrait composition.
    target=Vector(((dx+ex)/2,0,1.05));lens=50;location=target+Vector((2,-6,2))
    if index==0: lens=28;target=Vector(((dx+ex)/2,0,1));location=target+Vector((0,-12,2.3))
    elif index in [1,3,7,8,9]:target=Vector((.35,0,.9));location=target+Vector((1.7,-5,1.4))
    elif index==2:target=Vector(((dx+ex)/2,0,1.1));location=target+Vector((2.2,-6.5+u*.15,1.0));lens=45
    elif index in [4,5]:target=Vector((dx,0,1.55));location=target+Vector((.8,-3, .4));lens=65
    elif index==6:target=Vector((dx,0,1.1));location=target+Vector((0,-6,1.2))
    elif index in [10,11]:location=target+Vector((0,-5.5,1.0))
    elif index==12:location=target+Vector((-2,-5,1.0))
    elif index>=13:lens=24;location=target+Vector((4,4,3+u+(1 if index==14 else 0)));target.z=.8
    cam.data.type='PERSP';cam.data.lens=lens
    if vertical:
        # Own camera, fitted to both models and action, never a master crop.
        target=Vector(((dx+ex)/2,0,1.0))
        if index in [4,5,6]:target=Vector((dx,0,1.35))
        if index in [1,3]:target=Vector((ex,0,1.0))
        extent=abs(dx-ex) if index not in [1,3,4,5,6] else .6
        distance=max(6,extent*2.2+3)
        location=target+Vector((.5,-distance,1.2));cam.data.lens=45
    cam.location=location;cam.rotation_euler=(target-location).to_track_quat('-Z','Y').to_euler()


def scene(frame,vertical):
    row=next(r for r in timing['scenes'] if r['first_frame']<=frame<r['end_frame'])
    index=int(row['id'][1:])-1;start=row['first_frame'];end=row['end_frame'];local=(frame-start)/24;duration=(end-start)/24
    # S14 alone freezes its declared final two seconds.
    if index==13:local=min(local,max(0,duration-2))
    u=local/max(1/24,duration-(2 if index==13 else 0));t=(start/24)+local-(2 if index==14 else 0)
    dx=mix(DX[index],DX[index+1],u);ex=0 if index<11 else dx-.75
    walk=(t*6 if index<3 else t*4) if index in [0,1,2,3,6,10,11,12,13,14] else 0
    db=(smooth(u) if index==7 else 1 if index==8 else 1-smooth(u) if index==9 else 0)
    eb=smooth(u) if index==3 else 1 if 4<=index<=7 else 1-smooth(u) if index==8 else 0
    yaw=math.pi/2 if index<4 else mix(math.pi/2,0,u) if index==4 else 0 if index==5 else -math.pi/2 if index==6 else 0 if index<11 else -math.pi/2
    young.pose(dx,-.15,yaw,t,walk,db,1 if 7<=index<=10 else 0,smooth(u) if index==12 else .5 if index>9 else 0)
    elder.pose(ex,EY,-math.pi/2 if index>=11 else 0,t,t*4 if index>=11 else 0,eb,.5 if index in [0,1,8,9,10] else 0,.6 if index>=8 else 0)
    ground=[(-.35,-.55,.11),(.05,-.50,.11),(.42,-.65,.11)]
    bagroot.location=(ex+.22,0,.67);bagroot.rotation_euler=(0,0,0)
    if index==1:bagroot.rotation_euler.y=mix(0,.7,u)
    if 2<=index<=7:bagroot.rotation_euler.y=.7
    if index>=10:bagroot.location=(dx+.10,-.58,.70)
    for k,obj in enumerate(loaves):
        obj.hide_render=False
        if k>0:obj.scale.x=.17 if index>=9 else .24;obj.scale.y=.09 if index>=9 else .11
        if index==0:obj.location=(.22,0,.90+k*.035)
        elif index==1:
            v=smooth((u-.15-k*.12)/.55);obj.location=Vector((.22,0,.90)).lerp(Vector(ground[k]),v)
        elif index<=6:obj.location=ground[k]
        elif index==7:obj.location=Vector(ground[k]).lerp(Vector((.4+k*.16,-.55,.12)),smooth(u))
        elif index==8:
            target=(.55,1,.75) if k==0 else (.65+(k-1)*.15,-.45,.90)
            obj.location=Vector((.4+k*.16,-.55,.12)).lerp(Vector(target),smooth(u))
        elif index==9:
            obj.location=(.55,1,.75) if k==0 else Vector((.65+(k-1)*.15,-.45,.90)).lerp(Vector((.22,0,.90)),smooth(u))
        else:
            obj.location=(.55,1,.75) if k==0 else bagroot.location+Vector((0,0,.23+(k-1)*.04))
    # Constrain wrists to actual carried props rather than detached gestures.
    if index in [0,1,2,3,4,5,6,7,8,9]:
        elder.hand(1,bagroot.location+Vector((.16,-.14,.36)))
    if index>=10:
        young.hand(1,bagroot.location+Vector((.12,-.14,.34)))
    if index==7:
        young.hand(-1,loaves[1].location+Vector((0,0,.06)))
        young.hand(1,loaves[2].location+Vector((0,0,.06)))
    if index==8:
        young.hand(-1,loaves[1].location+Vector((0,0,.04)))
        young.hand(1,loaves[2].location+Vector((0,0,.04)))
    if index==9:
        young.hand(-1,loaves[1].location+Vector((0,0,.04)))
    set_camera(index,u,dx,ex,vertical)
    # Scene15 fade is composited by assembly; body and camera keep moving.
    s.frame_set(math.floor(frame)+1,subframe=frame-math.floor(frame));bpy.context.view_layer.update()


jobs=[]
if a.kind=='master':
    jobs=[(i,'hd-frames/'+f'{i:05d}.png',i) for i in range(timing['frames_total'])]
else:
    if not a.shorts:raise ValueError('SHORTS_REQUIRED')
    maps=load(a.shorts)
    for name in ['short1','short2']:
        for local,frame in enumerate(short_frames(maps[name])):
            jobs.append((len(jobs),f'vertical-frames/{name}-{local:05d}.png',frame))
if not 0<=a.start<a.end<=len(jobs):raise ValueError('CHUNK_RANGE')
s.render.resolution_x,s.render.resolution_y=(1920,1080) if a.kind=='master' else (1080,1920)
hashes={};elapsed=[]
for index,relative,frame in jobs[a.start:a.end]:
    dest=out/relative;dest.parent.mkdir(parents=True,exist_ok=True)
    scene(frame,a.kind=='vertical');s.render.filepath=str(dest)
    started=time.monotonic();bpy.ops.render.render(write_still=True);elapsed.append(time.monotonic()-started)
    dest.write_bytes(canonical_png(dest.read_bytes()))
    hashes[str(index)]=hashlib.sha256(dest.read_bytes()).hexdigest()
    print('FRAME',index,relative,elapsed[-1],hashes[str(index)],flush=True)
(out/f'frames-{a.kind}-{a.start}-{a.end}.json').write_text(json.dumps(hashes,sort_keys=True,indent=2)+'\n')
print('MEASURED',json.dumps({'frames':len(elapsed),'seconds_per_frame':sum(elapsed)/len(elapsed),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'blender':bpy.app.version_string,'engine':s.render.engine}),flush=True)
