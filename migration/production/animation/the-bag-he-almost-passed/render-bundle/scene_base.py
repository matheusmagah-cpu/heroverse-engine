import bpy, math, os, time
from mathutils import Vector
OUT='/workspace/scratch/ad2bbae16958/christian-pilot'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='BLENDER_EEVEE_NEXT';s.cycles.samples=12;s.cycles.use_denoising=False;s.cycles.max_bounces=3
s.eevee.taa_render_samples=16
s.render.resolution_x=768;s.render.resolution_y=432;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.world.color=(.32,.32,.32)
s.view_settings.view_transform='AgX'
def mat(n,c):
 m=bpy.data.materials.new(n);m.diffuse_color=(*c,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Roughness'].default_value=.83;return m
M={n:mat(n,c) for n,c in {'sand':(.72,.56,.38),'wall':(.83,.69,.49),'teal':(.035,.28,.28),'red':(.64,.18,.10),'skin':(.55,.29,.15),'oldskin':(.69,.43,.24),'white':(.9,.85,.72),'dark':(.045,.035,.03),'hair':(.16,.075,.035),'gray':(.67,.65,.57),'leaf':(.26,.38,.20),'wood':(.23,.12,.055),'bread':(.72,.39,.11),'bag':(.40,.27,.13),'sky':(.6,.75,.77)}.items()}
def uv(n,loc,scale,m):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,location=loc);o=bpy.context.object;o.name=n;o.scale=scale;o.data.materials.append(M[m]);bpy.ops.object.shade_smooth();return o
def box(n,loc,scale,m,bevel=.08):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=n;o.scale=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(M[m]);mod=o.modifiers.new('Soft edges','BEVEL');mod.width=bevel;mod.segments=3;o.modifiers.new('Normals','WEIGHTED_NORMAL');return o
def bone(n,a,b,r,m):
 bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=r,depth=1);o=bpy.context.object;o.name=n;o.data.materials.append(M[m]);bpy.ops.object.shade_smooth();posebone(o,a,b);return o
def posebone(o,a,b):
 a=Vector(a);b=Vector(b);o.location=(a+b)/2;o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();o.scale.z=(b-a).length
box('Square',(0,0,-.14),(200,200,.2),'sand')
box('Back wall',(0,4,1.7),(15,.5,3.6),'wall')
for x in [-5,-2.8,0,2.8,5]:
 box('Recess',(x,3.71,1.4),(1.5,.05,2.1),'wood',.35)
 box('Door',(x,3.65,1.35),(1.25,.06,1.9),'teal',.25)
for x in [-4,4]:
 bone('Trunk',(x,1,0),(x,1,2.8),.18,'wood')
 for dx,z in [(-.4,2.6),(.4,2.9),(0,3.3)]:uv('Olive canopy',(x+dx,1,z),(.8,.65,.75),'leaf')
box('Bench',(2.8,1,.55),(1.9,.6,.18),'wood')
for x in [2.1,3.5]:box('Bench leg',(x,1,.25),(.15,.5,.5),'wood')
# Decorative paving makes the world visibly three dimensional.
for y in [-2,-.8,.4,1.6,2.8]:
 for x in [-3,-1.5,0,1.5,3]:box('Paving',(x+(y%1)*.3,y,-.018),(1.37,1.08,.03),'wall',.04)
class Person:
 def __init__(self,n,old=False):
  self.n=n;self.old=old;self.parts={};self.skin='oldskin' if old else 'skin';self.cloth='red' if old else 'teal'
  for k,scale,ma in [('body',(.31,.22,.48),self.cloth),('head',(.26,.24,.30),self.skin),('hair',(.275,.24,.17),'gray' if old else 'hair'),('nose',(.065,.10,.07),self.skin),('mouth',(.07,.025,.014),'dark')]:self.parts[k]=uv(n+k,(0,0,0),scale,ma)
  for side in [-1,1]:
   for k,scale,ma in [('eye',(.055,.028,.065),'white'),('pupil',(.025,.025,.032),'dark'),('hand',(.095,.09,.12),self.skin),('shoe',(.12,.22,.09),'dark')]:self.parts[k+str(side)]=uv(n+k,(0,0,0),scale,ma)
   for k,r,ma in [('upperarm',.085,self.cloth),('forearm',.07,self.skin),('thigh',.095,self.cloth),('shin',.075,self.cloth)]:self.parts[k+str(side)]=bone(n+k,(0,0,0),(0,0,1),r,ma)
  if old:self.parts['beard']=uv(n+'beard',(0,0,0),(.21,.12,.18),'gray')
 def pose(self,x,y,walk=0,bend=0,hands=None,joy=0):
  bob=abs(math.sin(walk))*0.035 if walk else 0
  hip=Vector((x,y,.78+bob-bend*.32));chest=hip+Vector((0,-bend*.42,.43-bend*.28));head=chest+Vector((0,-bend*.20,.48))
  self.parts['body'].location=chest-Vector((0,0,.05));self.parts['body'].rotation_euler.x=-bend*.65
  for k,off in [('head',(0,0,0)),('hair',(0,.025,.19)),('nose',(0,-.255,-.02)),('mouth',(0,-.233,-.13))]:self.parts[k].location=head+Vector(off)
  for side in [-1,1]:
   self.parts['eye'+str(side)].location=head+Vector((side*.10,-.22,.055));self.parts['pupil'+str(side)].location=head+Vector((side*.10,-.246,.055))
   shoulder=chest+Vector((side*.27,0,.17));swing=math.sin(walk)*side*.27
   hand=Vector(hands[side]) if hands and side in hands else shoulder+Vector((side*.08,-swing,-.57))
   elbow=(shoulder+hand)/2+Vector((side*.08,-.08,0))
   posebone(self.parts['upperarm'+str(side)],shoulder,elbow);posebone(self.parts['forearm'+str(side)],elbow,hand);self.parts['hand'+str(side)].location=hand
   foot=Vector((x+side*.15+swing,y,.10+max(0,math.cos(walk)*side)*.08 if walk else .10));knee=(hip+foot)/2+Vector((side*.08,-.06-bend*.24,0))
   posebone(self.parts['thigh'+str(side)],hip+Vector((side*.13,0,0)),knee);posebone(self.parts['shin'+str(side)],knee,foot);self.parts['shoe'+str(side)].location=foot+Vector((0,-.08,-.02))
  if self.old:self.parts['beard'].location=head+Vector((0,-.16,-.20))
young=Person('Traveller');elder=Person('Neighbour',True)
bread=uv('Bread',(0,-.55,.12),(.27,.12,.105),'bread')
for i in [-.12,0,.12]:
 o=box('Bread scoring',(i,-.55,.215),(.025,.15,.008),'wall',.006);o.parent=bread;o.matrix_parent_inverse=bread.matrix_world.inverted()
bag=uv('Cloth bag',(-.9,0,.22),(.25,.20,.28),'bag')
bpy.ops.object.light_add(type='AREA',location=(-3,-4,7));bpy.context.object.data.energy=1100;bpy.context.object.data.size=5
bpy.ops.object.light_add(type='AREA',location=(4,1,5));bpy.context.object.data.energy=650;bpy.context.object.data.size=4
bpy.ops.object.camera_add(location=(5,-9,5));cam=bpy.context.object;s.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=6.2

def smooth(a):return max(0,min(1,a))**2*(3-2*max(0,min(1,a)))
def animate(t):
 # Pause, pass, notice, return, crouch, lift, share, sit together.
 ex=-.8;ey=.35
 if t<5:
  p=smooth(t/5);x=-2.7+p*3.7;walk=t*7;bend=0;hands=None
 elif t<8:x=1.;walk=0;bend=0;hands=None
 elif t<11:
  p=smooth((t-8)/3);x=1.-p*.95;walk=t*7;bend=0;hands=None
 elif t<14:
  x=.05;walk=0;bend=smooth((t-11)/2.4);hands={-1:(-.12,-.55,.22+.70*(1-bend))}
 elif t<17:
  p=smooth((t-14)/3);x=.05;walk=0;bend=1-p;hands={-1:(-.12,-.55,.22+p*.85)};bread.location=(-.12,-.55,.22+p*.85)
 elif t<21:
  p=smooth((t-17)/3);x=.05;walk=0;bend=0;hands={-1:(-.12-p*.36,-.35,1.07)};bread.location=(-.12-p*.36,-.35,1.07)
 else:
  x=.05;walk=0;bend=0;hands={-1:(-.48,-.35,1.07)};bread.location=(-.48,-.35,1.07)
 if t<14:bread.location=(-.12,-.55,.12)
 young.pose(x,-.05,walk,bend,hands)
 eh={1:(-.50,-.34,1.02)} if t>18 else None
 elder.pose(ex,ey,0,.12 if t<17 else 0,eh)
 # Slow motivated change in shot size, never a substitute for character animation.
 target=Vector((-.3,0,1.05));cam.location=(3.8,-8,4.2);cam.data.ortho_scale=6.2
 if 5<=t<11:cam.location=(2.5,-7,3.6);cam.data.ortho_scale=4.8
 if 11<=t<18:cam.location=(2,-6,3.3);cam.data.ortho_scale=4.8;target=Vector((-.3,-.1,1.05))
 if t>=18:cam.location=(2,-7,3.4);cam.data.ortho_scale=4.5
 cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
import sys
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
if args and args[0]=='test':
 animate(19);s.render.filepath=OUT+'/preview.png';st=time.monotonic();bpy.ops.render.render(write_still=True);print('TEST_SECONDS',time.monotonic()-st)
else:
 for f in [130,160,200]+list(range(240)):
  dest=OUT+'/frames/%04d.png'%f
  if os.path.exists(dest):continue
  animate(f/10);s.render.filepath=dest;bpy.ops.render.render(write_still=True)
 bpy.ops.wm.save_as_mainfile(filepath=OUT+'/scene.blend')
