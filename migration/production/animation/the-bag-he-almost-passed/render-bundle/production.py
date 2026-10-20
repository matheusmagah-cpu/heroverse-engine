import bpy, math, os, sys, time
from mathutils import Vector, Matrix
BASE=os.path.join(os.path.dirname(__file__),'scene_base.py')
source=open(BASE).read().split('import sys')[0]
source=source.replace('x+side*.15+swing,y','x+side*.15,y+swing')
exec(compile(source,BASE,'exec'))
OUT=os.environ.get('RENDER_OUT',os.path.dirname(os.path.abspath(__file__)));os.makedirs(OUT,exist_ok=True);FPS=10;DURATION=152
s.render.resolution_x=1920;s.render.resolution_y=1080
# Shift the bench beside Eli, with its far end beside Daniel's stopping place.
for ob in bpy.data.objects:
 if ob.name.startswith('Bench'):ob.location.x-=1.4;ob.location.y+=.4
bag.hide_render=True
# A real open-sided bag rather than the sphere used in the first capability test.
bagroot=bpy.data.objects.new('Paper bag root',None);bpy.context.collection.objects.link(bagroot)
for n,p,sz in [('bottom',(0,0,.025),(.46,.32,.05)),('front',(0,-.16,.25),(.46,.035,.46)),('back',(0,.16,.25),(.46,.035,.46)),('left',(-.23,0,.25),(.035,.32,.46)),('right',(.23,0,.25),(.035,.32,.46))]:
 ob=box('Paper bag '+n,p,sz,'bag',.018);ob.parent=bagroot
for y in [-.15,.15]:
 cu=bpy.data.curves.new('Bag handle','CURVE');cu.dimensions='3D';cu.bevel_depth=.018;cu.bevel_resolution=2;sp=cu.splines.new('POLY');sp.points.add(16)
 for i,pt in enumerate(sp.points):
  a=math.pi*i/16;pt.co=(.15*math.cos(a),y,.46+.22*math.sin(a),1)
 ob=bpy.data.objects.new('Bag handle',cu);bpy.context.collection.objects.link(ob);ob.data.materials.append(M['wood']);ob.parent=bagroot
# Two wrapped loaves and one loose loaf have independent, persistent identities.
loose=bread
wrapped=[]
for k in range(2):
 ob=uv('Wrapped loaf '+str(k),(0,0,0),(.23,.12,.105),'white');wrapped.append(ob)
 # A narrow paper band differentiates the wrapped loaves clearly from the loose bread.
 band=box('Wrapper band '+str(k),(0,0,0),(.07,.245,.08),'bag',.015);band.parent=ob;band.location=(0,0,.025);band.scale=(1/.23,1/.12,1/.105)
for person in [young,elder]:
 person.parts['mouth'].hide_render=True
 cu=bpy.data.curves.new(person.n+' expressive mouth','CURVE');cu.dimensions='3D';cu.bevel_depth=.012;cu.bevel_resolution=2;sp=cu.splines.new('POLY');sp.points.add(8)
 ob=bpy.data.objects.new(person.n+' smile',cu);bpy.context.collection.objects.link(ob);ob.data.materials.append(M['dark']);person.parts['mouthcurve']=ob
 for side in [-1,1]:person.parts['brow'+str(side)]=bone(person.n+' brow',(0,0,0),(0,0,.1),.018,'hair' if not person.old else 'gray')

def pose(person,x,y,walk=0,bend=0,yaw=0,hands=None,smile=0,nod=0,t=0):
 for ob in person.parts.values():ob.rotation_euler=(0,0,0)
 root=Vector((x,y,0));rot=Matrix.Rotation(yaw,3,'Z');inv=rot.inverted()
 localhands={k:root+inv@(Vector(v)-root) for k,v in hands.items()} if hands else None
 person.pose(x,y,walk,bend,localhands)
 head=person.parts['head'].location.copy()
 mouth=person.parts['mouthcurve'];mouth.location=head+Vector((0,-.244,-.12))
 for i,p in enumerate(mouth.data.splines[0].points):
  u=(i-4)/4;p.co=(u*.075,0,smile*.035*u*u-smile*.018,1)
 blink=1
 phase=(t+(1.3 if person.old else 0))%4.7
 if phase<.16:blink=.08+abs(phase-.08)/.08*.92
 for side in [-1,1]:
  person.parts['eye'+str(side)].scale.z=.065*blink;person.parts['pupil'+str(side)].scale.z=.032*blink
  a=head+Vector((side*.06,-.216,.15));b=head+Vector((side*.15,-.20,.14+smile*.015));posebone(person.parts['brow'+str(side)],a,b)
 if nod:
  rr=Matrix.Rotation(nod,3,'X')
  for k,ob in person.parts.items():
   if k in ['head','hair','nose','mouth','mouthcurve','beard'] or k.startswith(('eye','pupil','brow')):
    ob.location=head+rr@(ob.location-head);ob.rotation_euler=(rr@ob.rotation_euler.to_matrix()).to_euler()
 for ob in person.parts.values():ob.location=root+rot@(ob.location-root);ob.rotation_euler=(rot@ob.rotation_euler.to_matrix()).to_euler()

def lerp(a,b,u):return Vector(a).lerp(Vector(b),smooth(u))
def q(a,b,t):return smooth((t-a)/(b-a))
def camshot(loc,target,scale):
 cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale

def loose_path(t):
 if t<84:return lerp((.35,-.55,.12),(.35,-.55,1.10),(t-82)/2)
 return lerp((.35,-.55,1.10),(1.55,1.18,.75),(t-84)/3)
def wrapped_path(t,start,ground):
 if t<start+2:return lerp(ground,(ground[0],ground[1],1.06),(t-start)/2)
 if t<start+3.5:return lerp((ground[0],ground[1],1.06),(.67,-.20,1.06),(t-start-2)/1.5)
 return lerp((.67,-.20,1.06),(.67,-.20,.65),(t-start-3.5)/.5)
def second_path(t):
 if t<99:return lerp((.95,-.58,.12),(.95,-.58,1.06),t-98)
 if t<99.7:return lerp((.95,-.58,1.06),(.67,-.20,1.06),(t-99)/.7)
 return lerp((.67,-.20,1.06),(.67,-.20,.65),(t-99.7)/.3)
def scene(t):
 # Master timeline: street / drop / pass / reach / conscience / verse / return /
 # consent / separate loose bread / pack / carry / company / pace / departure.
 ex,ey=.4,.35;dy=-.10;dx=-3.2;db=0;eb=0;dwalk=0;ewalk=0;dh={};eh={};dyaw=math.pi/2;eyaw=0;dnod=0;enod=0
 if t<10:dx=-3.2+1.7*q(0,10,t);dwalk=t*5.7
 elif t<20:dx=-1.5+.6*q(10,20,t);dwalk=t*4.0
 elif t<30:dx=-.9+3.4*q(20,30,t);dwalk=t*6.2;dyaw=math.pi/2-.6*math.sin(math.pi*q(20,24,t)) if t<24 else math.pi/2
 elif t<40:dx=2.5+.7*q(30,35,t);dwalk=t*4 if t<35 else 0
 elif t<50:dx=3.2;dyaw=math.pi/2-.6*q(43,49,t);dnod=.07*math.sin(t)
 elif t<62:dx=3.2;dyaw=math.pi/2-.6;dnod=.06*math.sin(t*.8)
 elif t<72:dx=3.2-2.05*q(62,72,t);dyaw=(math.pi/2-.6)+(-math.pi+.6)*q(62,64,t);dwalk=t*4.7
 else:dx=1.15;dyaw=0
 if 30<=t<65:eb=.65*q(30,36,t)*(1-q(62,65,t));eh[-1]=(.00,-.52,.25+.65*(1-eb/.65))
 if 72<=t<78:
  dh[-1]=(.76,-.38,1.10+.05*math.sin(t*1.5));enod=.18*math.sin(math.pi*q(76.5,78,t));eh[1]=(.74,-.2,1.10)
 if 78<=t<82:db=q(78,82,t);dh[-1]=(.82-.47*q(79,82,t),-.55,1.05-.86*db)
 if 82<=t<87:db=1-q(82,84,t);dy=-.10+.55*q(84,87,t);dh[-1]=loose_path(t)+Vector((0,0,.07))
 if 87<=t<92:db=q(89,92,t);dy=.45-.55*q(87,90,t);dh[-1]=lerp((1.55,1.18,.82),(.53,-.55,.19),(t-87)/4)
 if 92<=t<96:db=1-q(92,95,t);dh[-1]=wrapped_path(t,92,(.53,-.55,.12))+Vector((0,0,.07));eh[1]=(.68,-.04,1.02)
 if 96<=t<100:
  db=math.sin(math.pi*q(96,100,t));dh[-1]=lerp((.67,-.20,.84),(.95,-.58,.19),(t-96)/2) if t<98 else second_path(t)+Vector((0,0,.07));eh[1]=(.68,-.04,1.02)
 if 100<=t<105:dh[-1]=(.70,-.12,1.02);eh[1]=(.68,-.04,1.02) if t<103 else (.14,-.35,1.25);enod=.13*math.sin(math.pi*q(102,104,t))
 if t>=105:
  shift=(t-105)*.105;dx=1.15-shift;ex=.4-shift;dyaw=-math.pi/2;eyaw=-math.pi/2;dwalk=(t-105)*4.4;ewalk=(t-105)*4.4
  # Carry on Daniel's outer side, leaving both people unobstructed.
  dh[-1]=(dx+.10,-.42,1.02)
  if t<108:eh[1]=(ex-.35,.10,1.25)
 if t<14.5:eh[1]=(.65,-.05,1.05)
 elif t<18.5:eh[1]=lerp((.65,-.05,1.05),(.72,-.15,.63),(t-14.5)/4)
 if 84<=t<87:dx=1.15+.15*q(84,87,t);dy=-.10+.55*q(84,87,t);dyaw=math.pi*q(84,87,t)
 if 87<=t<90:dx=1.30-.15*q(87,90,t);dyaw=math.pi*(1-q(87,90,t))
 pose(young,dx,dy,dwalk,db,dyaw,dh,smile=.8*q(96,112,t),nod=dnod,t=t)
 pose(elder,ex,ey,ewalk,eb,eyaw,eh,smile=.7*q(76,104,t),nod=enod,t=t)
 # Persistent bread states, including the loose piece left aside for the rest of the film.
 loose.location=(.35,-.55,.12);wrapped[0].location=(.53,-.55,.12);wrapped[1].location=(.95,-.58,.12)
 for ob in [loose,*wrapped]:ob.hide_render=False
 if t<19:
  for i,ob in enumerate([wrapped[0],loose,wrapped[1]]):
   u=q(14.8+i*.65,17.5+i*.55,t);dest=ob.location.copy();ob.location=lerp((.65,-.05,.79+i*.025),dest,u);ob.location.z+=.15*math.sin(math.pi*u)
 if 82<=t<87:loose.location=loose_path(t)
 if t>=87:loose.location=(1.55,1.18,.75)
 if 92<=t<96:wrapped[0].location=wrapped_path(t,92,(.53,-.55,.12))
 if t>=96:wrapped[0].hide_render=True
 if 98<=t<100:wrapped[1].location=second_path(t)
 if t>=100:wrapped[1].hide_render=True
 # Restore the wrapper band's visibility to its own loaf on every frame.
 for ob in wrapped:
  for ch in ob.children:ch.hide_render=ob.hide_render
 if t<14.5:bagroot.location=(.65,-.05,.35);bagroot.rotation_euler=(0,0,0)
 elif t<18.5:bagroot.location=lerp((.65,-.05,.35),(.7,-.15,.03),(t-14.5)/4);bagroot.rotation_euler=(0,.65*math.sin(math.pi*q(14.5,18.5,t)),0)
 elif t<92:bagroot.location=(.7,-.15,.03);bagroot.rotation_euler=(0,0,0)
 elif t<94:bagroot.location=lerp((.7,-.15,.03),(.67,-.20,.34),(t-92)/2);bagroot.rotation_euler=(0,0,0)
 elif t<105:bagroot.location=(.67,-.20,.34);bagroot.rotation_euler=(0,0,0)
 else:bagroot.location=(dx+.10,-.27,.34+.02*math.sin(dwalk));bagroot.rotation_euler=(0,.035*math.sin(dwalk),0)
 bagroot.scale.x=.8+.2*q(92,94,t)
 # Independent camera coverage for all 14 shots.
 if t<10:camshot((1.2,-8,4.3),(-.7+.045*t,0,1),7.3)
 elif t<20:camshot((2.8,-5,3.0),(.5,-.1,1.12),4.5)
 elif t<30:camshot((3.5,-7,3.5),(1.0,0,1),6.0)
 elif t<40:camshot((2.5,-5,2.6),(.5,-.1,1.0),4.3)
 elif t<50:camshot((5.5,-5,3.3),(2.5,.2,1.25),4.3)
 elif t<62:camshot((4.7,-4,2.7),(3.05,-.1,1.35),3.0)
 elif t<72:camshot((dx+2.5,-6,3.5),(dx-.3,.1,1.0),5.2)
 elif t<82:camshot((3.0,-6,3.4),(.8,0,.95),4.8)
 elif t<92:camshot((3.0,-5,3.1),(.8,-.05,1.1),4.8)
 elif t<102:camshot((2.5,-5,3.1),(.8,-.1,1.1),4.5)
 elif t<112:camshot((dx+2.8,-6,3.3),(dx-.25,0,1.0),4.7)
 elif t<122:camshot((dx+2.2,-5,3.0),(dx-.35,.05,1.05),4.3)
 elif t<132:camshot((dx-2.8,-5,3.2),(dx-.35,.05,1.05),4.5)
 elif t<146:camshot((dx+2.7,2.5,4.5+q(132,146,t)),(dx-.35,.1,1.0),5.5+q(132,146,t))
 else:camshot((dx+2.5,-6,3.5),(dx-.35,.05,1.0),4.8)

import json
from pathlib import Path
from bpy_extras.object_utils import world_to_camera_view
P=Path(OUT)
def vertical(t):
 scene(t);s.render.resolution_x=1080;s.render.resolution_y=1920
 objects=list(young.parts.values())
 if not 50<=t<56:objects+=list(elder.parts.values())
 if 10<=t<103:objects += [loose,*wrapped,*bagroot.children]
 objects=[ob for ob in objects if not ob.hide_render]
 bpy.context.view_layer.update()
 points=[ob.matrix_world@Vector(corner) for ob in objects for corner in ob.bound_box]
 low=Vector(tuple(min(v[k] for v in points) for k in range(3)));high=Vector(tuple(max(v[k] for v in points) for k in range(3)))
 center=(low+high)/2
 camshot(center+Vector((2.2,-6,3.0)),center,3.8)
 for _ in range(3):
  bpy.context.view_layer.update();coords=[world_to_camera_view(s,cam,v) for v in points]
  cx=(min(v.x for v in coords)+max(v.x for v in coords))/2;cy=(min(v.y for v in coords)+max(v.y for v in coords))/2
  width=max(v.x for v in coords)-min(v.x for v in coords);height=max(v.y for v in coords)-min(v.y for v in coords)
  factor=max(1,width/.82,height/.64);cam.data.ortho_scale*=factor
  # Recenter the subject group while preserving the camera angle.
  right=cam.rotation_euler.to_matrix()@Vector((1,0,0));up=cam.rotation_euler.to_matrix()@Vector((0,1,0))
  cam.location+=right*((cx-.5)*cam.data.ortho_scale*9/16)+up*((cy-.5)*cam.data.ortho_scale)

def key(t):return f'{round(t*1000):06d}'
def segment(start,duration,source_span=None):
 return [round(start+i/10*(source_span/duration if source_span else 1),3) for i in range(round(duration*10))]
shared={'drop':segment(10,10),'pass':segment(20,6),'return':segment(62,3,10),'help':segment(72,10),'bag':segment(92,3,10),'walk':segment(105,4,7),'cta':segment(146,6),'verse':segment(50,5)}
short1=shared['drop']+shared['pass']+shared['return']+shared['help']+shared['bag']+shared['walk']+shared['cta']
short2=shared['verse']+segment(10,9)+segment(24,1,2)+shared['return']+shared['help']+shared['bag']+shared['walk']+shared['cta']
(P/'short-frame-maps.json').write_text(json.dumps({'short1':short1,'short2':short2,'unique_times':sorted(set(short1+short2))},indent=2))
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
mode=args[0] if args else 'all'
if mode=='vertical_preview':
 for t in map(float,args[1:]):
  vertical(t);s.render.filepath=f'{OUT}/vertical1080-{t:05.1f}.png';st=time.monotonic();bpy.ops.render.render(write_still=True);print('VERTICAL_SECONDS',t,time.monotonic()-st,flush=True)
else:
 if mode in ['all','master']:
  (P/'hd-frames').mkdir(exist_ok=True);s.render.resolution_x=1920;s.render.resolution_y=1080
  begin=int(args[1]) if len(args)>1 else 0;end=int(args[2]) if len(args)>2 else FPS*DURATION
  for f in range(begin,end):
   path=P/'hd-frames'/f'{f:05d}.png'
   if path.exists():continue
   scene(f/FPS);s.render.filepath=str(path);bpy.ops.render.render(write_still=True)
   if f%100==0:print('MASTER_MILESTONE',f/FPS,flush=True)
  (P/f'master-chunk-{begin}-{end}.done').write_text('Complete')
  if len(list((P/'hd-frames').glob('*.png')))==FPS*DURATION:
   bpy.ops.wm.save_as_mainfile(filepath=str(P/'master-final-scene.blend'));(P/'master.done').write_text('152 seconds, 1920x1080 native, 10 unique fps')
 if mode in ['all','vertical']:
  (P/'vertical-frames').mkdir(exist_ok=True)
  times=sorted(set(short1+short2));begin=int(args[1]) if len(args)>1 else 0;end=int(args[2]) if len(args)>2 else len(times)
  for index in range(begin,end):
   t=times[index]
   path=P/'vertical-frames'/(key(t)+'.png')
   if path.exists():continue
   vertical(t);s.render.filepath=str(path);bpy.ops.render.render(write_still=True)
   if index%50==0:print('VERTICAL_MILESTONE',index,flush=True)
  (P/f'vertical-chunk-{begin}-{end}.done').write_text('Complete')
  if len(list((P/'vertical-frames').glob('*.png')))==len(times):(P/'vertical.done').write_text('Native 1080x1920, 42-second and 41-second short frame sequences')
