import bpy, math, os, time
from mathutils import Vector

bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='BLENDER_EEVEE_NEXT';s.cycles.samples=12;s.cycles.use_denoising=False;s.cycles.max_bounces=3
s.eevee.taa_render_samples=32
s.render.resolution_x=768;s.render.resolution_y=432;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.world.color=(.32,.32,.32)
s.view_settings.view_transform='AgX'
def mat(n,c):
 m=bpy.data.materials.new(n);m.diffuse_color=(*c,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Roughness'].default_value=.83;return m
M={n:mat(n,c) for n,c in {'sand':(.72,.56,.38),'wall':(.83,.69,.49),'teal':(.035,.28,.28),'red':(.76,.43,.30),'skin':(.55,.29,.15),'oldskin':(.69,.43,.24),'white':(.9,.85,.72),'dark':(.045,.035,.03),'hair':(.16,.075,.035),'gray':(.67,.65,.57),'leaf':(.26,.38,.20),'wood':(.23,.12,.055),'bread':(.72,.39,.11),'bag':(.40,.27,.13),'sky':(.6,.75,.77)}.items()}
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
bread=uv('Bread',(0,-.55,.12),(.27,.12,.105),'bread')
for i in [-.12,0,.12]:
 o=box('Bread scoring',(i,-.55,.215),(.025,.15,.008),'wall',.006);o.parent=bread;o.matrix_parent_inverse=bread.matrix_world.inverted()
bag=uv('Cloth bag',(-.9,0,.22),(.25,.20,.28),'bag')
bpy.ops.object.light_add(type='AREA',location=(-3,-4,7));bpy.context.object.data.energy=1100;bpy.context.object.data.size=5
bpy.ops.object.light_add(type='AREA',location=(4,1,5));bpy.context.object.data.energy=650;bpy.context.object.data.size=4
bpy.ops.object.camera_add(location=(5,-9,5));cam=bpy.context.object;s.camera=cam;cam.data.type='PERSP';cam.data.lens=50
