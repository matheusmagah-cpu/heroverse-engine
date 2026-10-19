"""Original procedural, skinned humanoids; no downloaded meshes or motion."""
import bpy, math
from mathutils import Vector


def tube(vertices, faces, rings, count=16):
    base=len(vertices)
    for x,y,z,rx,ry in rings:
        for i in range(count):
            a=2*math.pi*i/count; vertices.append((x+rx*math.cos(a),y+ry*math.sin(a),z))
    for j in range(len(rings)-1):
        for i in range(count):
            a=base+j*count+i;b=base+j*count+(i+1)%count
            faces.append((a,b,b+count,a+count))
    faces.append(tuple(base+i for i in reversed(range(count))))
    faces.append(tuple(base+(len(rings)-1)*count+i for i in range(count)))


class Character:
    def __init__(self,name,old,materials):
        self.name=name; self.old=old; self.features={}
        mesh=bpy.data.meshes.new(name+' tailored skin');v=[];f=[]
        # Tailored silhouette, not a stack of spheres/cylinders. Overlapping
        # ring surfaces are unified by voxel remesh before skinning.
        tube(v,f,[(0,0,.76,.20,.16),(0,0,.88,.24,.18),(0,0,1.03,.23,.16),(0,0,1.27,.29,.19),(0,0,1.40,.30,.17),(0,0,1.46,.13,.12)])
        for side in [-1,1]:
            tube(v,f,[(side*.13,0,.83,.12,.14),(side*.14,0,.61,.105,.11),(side*.15,-.02,.43,.095,.10),(side*.15,0,.07,.085,.09)])
            tube(v,f,[(side*.27,0,1.38,.12,.12),(side*.37,0,1.20,.10,.10),(side*.43,-.015,1.04,.085,.085),(side*.49,-.03,.84,.065,.07)])
        mesh.from_pydata(v,[],f);mesh.update();body=bpy.data.objects.new(name+' continuous body',mesh);bpy.context.collection.objects.link(body)
        bpy.context.view_layer.objects.active=body;body.select_set(True)
        remesh=body.modifiers.new('Unified tailored topology','REMESH');remesh.mode='VOXEL';remesh.voxel_size=.035
        bpy.ops.object.modifier_apply(modifier=remesh.name)
        smooth=body.modifiers.new('Relax surface','SMOOTH');smooth.factor=.8;smooth.iterations=4;bpy.ops.object.modifier_apply(modifier=smooth.name)
        body.data.materials.append(materials['red' if old else 'teal']);body.data.materials.append(materials['dark'])
        for poly in body.data.polygons:
            poly.use_smooth=True
            if poly.center.z<.84:poly.material_index=1
        arm=bpy.data.armatures.new(name+' skeleton');rig=bpy.data.objects.new(name+' rig',arm);bpy.context.collection.objects.link(rig)
        bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
        definitions={'pelvis':((0,0,.77),(0,0,.95),None),'spine':((0,0,.95),(0,0,1.38),'pelvis'),'head':((0,0,1.38),(0,0,1.85),'spine')}
        for side in [-1,1]:
            suffix=str(side)
            definitions.update({'thigh'+suffix:((side*.13,0,.80),(side*.15,-.02,.43),'pelvis'),'shin'+suffix:((side*.15,-.02,.43),(side*.15,0,.13),'thigh'+suffix),'arm'+suffix:((side*.27,0,1.38),(side*.43,-.015,1.04),'spine'),'forearm'+suffix:((side*.43,-.015,1.04),(side*.49,-.03,.81),'arm'+suffix)})
        for key,(a,b,parent) in definitions.items():
            bone=arm.edit_bones.new(key);bone.head=a;bone.tail=b
            if parent:bone.parent=arm.edit_bones[parent]
        bpy.ops.object.mode_set(mode='OBJECT');self.rig=rig
        groups={key:body.vertex_groups.new(name=key) for key in definitions}
        def clamp(v):return max(0,min(1,v))
        for vertex in body.data.vertices:
            x,y,z=vertex.co;side='1' if x>=0 else '-1'
            weights={}
            if abs(x)>.27 and z>.80:
                upper=clamp((z-.95)/.20);shoulder=clamp((.34-abs(x))/.08)
                weights={'arm'+side:upper*(1-shoulder),'forearm'+side:(1-upper)*(1-shoulder),'spine':shoulder}
            elif z<.90:
                pelvis=clamp((z-.55)/.20);thigh=clamp((z-.34)/.18)
                weights={'pelvis':pelvis,'thigh'+side:thigh*(1-pelvis),'shin'+side:(1-thigh)*(1-pelvis)}
            else:
                spine=clamp((z-.88)/.25);weights={'pelvis':1-spine,'spine':spine}
            for key,weight in weights.items():
                if weight>0:groups[key].add([vertex.index],weight,'REPLACE')
        mod=body.modifiers.new('Weighted humanoid deformation','ARMATURE');mod.object=rig;mod.use_deform_preserve_volume=True
        sub=body.modifiers.new('Smooth final silhouette','SUBSURF');sub.levels=1;sub.render_levels=1
        body.parent=rig
        self.body=body
        self.targets={}
        self.feet={}
        for side in [-1,1]:
            target=bpy.data.objects.new(name+' hand target '+str(side),None);bpy.context.collection.objects.link(target)
            constraint=rig.pose.bones['forearm'+str(side)].constraints.new('IK');constraint.target=target;constraint.chain_count=2;constraint.use_stretch=False;constraint.influence=0
            self.targets[side]=(target,constraint)
            foot=bpy.data.objects.new(name+' foot target '+str(side),None);bpy.context.collection.objects.link(foot)
            pole=bpy.data.objects.new(name+' knee pole '+str(side),None);bpy.context.collection.objects.link(pole)
            ik=rig.pose.bones['shin'+str(side)].constraints.new('IK');ik.target=foot;ik.pole_target=pole;ik.chain_count=2;ik.use_stretch=False;ik.pole_angle=math.pi/2
            self.feet[side]=(foot,pole)
        def attach(ob,key,bone):
            ob.parent=rig
            group=ob.vertex_groups.new(name=bone);group.add(list(range(len(ob.data.vertices))),1,'REPLACE')
            modifier=ob.modifiers.new('Follow skeleton','ARMATURE');modifier.object=rig;self.features[key]=ob
        def ellipsoid(key,center,scale,material,bone='head'):
            verts=[];faces=[]
            rings=[]
            for j in range(13):
                a=math.pi*(.01+.98*j/12);rings.append((center[0],center[1],center[2]+scale[2]*math.cos(a),scale[0]*math.sin(a),scale[1]*math.sin(a)))
            tube(verts,faces,rings,24);m=bpy.data.meshes.new(name+key);m.from_pydata(verts,[],faces);m.update();o=bpy.data.objects.new(name+key,m);bpy.context.collection.objects.link(o);o.data.materials.append(materials[material])
            for face in m.polygons:face.use_smooth=True
            attach(o,key,bone);return o
        skin='oldskin' if old else 'skin'
        ellipsoid('neck',(0,0,1.47),(.085,.085,.15),skin)
        ellipsoid('face',(0,-.01,1.70),(.185,.16,.22),skin)
        ellipsoid('hair',(0,.025,1.85),(.20,.165,.12),'gray' if old else 'hair')
        ellipsoid('nose',(0,-.18,1.69),(.045,.06,.06),skin)
        for side in [-1,1]:
            suffix=str(side)
            ellipsoid('ear'+suffix,(side*.195,0,1.69),(.035,.035,.065),skin)
            ellipsoid('eye'+suffix,(side*.075,-.164,1.74),(.045,.022,.038),'white')
            ellipsoid('pupil'+suffix,(side*.075,-.186,1.74),(.019,.01,.023),'dark')
            ellipsoid('brow'+suffix,(side*.075,-.17,1.80),(.052,.018,.012),'gray' if old else 'hair')
            ellipsoid('hand'+suffix,(side*.49,-.03,.79),(.065,.055,.095),skin,'forearm'+suffix)
            ellipsoid('shoe'+suffix,(side*.15,-.075,.10),(.095,.17,.085),'dark','shin'+suffix)
            shoe=self.features['shoe'+suffix];shoe.parent=None
            for modifier in list(shoe.modifiers):shoe.modifiers.remove(modifier)
            for vertex in shoe.data.vertices:vertex.co-=Vector((side*.15,-.075,.10))
        mouth=ellipsoid('mouth',(0,-.173,1.59),(.065,.012,.012),'dark');mouth.shape_key_add(name='Basis');smile=mouth.shape_key_add(name='Smile')
        for vert in smile.data:vert.co.z+=.025*(abs(vert.co.x)/.065)**2
        if old:
            ellipsoid('cap',(0,.01,1.91),(.225,.19,.085),'wood')
            ellipsoid('cap brim',(0,-.17,1.89),(.22,.13,.015),'wood')
        for key in ['eye-1','eye1','pupil-1','pupil1']:
            ob=self.features[key];ob.shape_key_add(name='Basis');blink=ob.shape_key_add(name='Blink')
            for vertex in blink.data:vertex.co.z=1.74+(vertex.co.z-1.74)*.06
        for key in ['brow-1','brow1']:
            ob=self.features[key];ob.shape_key_add(name='Basis');expression=ob.shape_key_add(name='Expression')
            for vertex in expression.data:vertex.co.z+=.018+(vertex.co.x-(.075 if key=='brow1' else -.075))*.15
        for key in ['pupil-1','pupil1']:
            ob=self.features[key];look=ob.shape_key_add(name='Look')
            for vertex in look.data:vertex.co.x+=.018
    def pose(self,x,y,yaw,t,walk=0,bend=0,gesture=0,smile=0):
        self.rig.location=(x,y,-.43*bend+.018*math.sin(t*2.1)+.015*abs(math.sin(walk)))
        self.rig.rotation_euler.z=yaw
        for bone in self.rig.pose.bones:bone.rotation_mode='XYZ';bone.rotation_euler=(0,0,0)
        for target,constraint in self.targets.values():constraint.influence=0
        p=self.rig.pose.bones;p['pelvis'].rotation_euler.y=.035*math.sin(walk);p['spine'].rotation_euler.x=.5*bend+.018*math.sin(t*2.1)
        p['head'].rotation_euler.x=-.18*bend+.025*math.sin(t*.8);p['head'].rotation_euler.y=.12*math.sin(t*.7)
        for side in [-1,1]:
            suffix=str(side);phase=math.sin(walk)*side if walk else 0
            p['thigh'+suffix].rotation_euler.x=.48*phase-.65*bend
            p['shin'+suffix].rotation_euler.x=max(0,-phase)*.65+1.05*bend
            p['arm'+suffix].rotation_euler.x=-.35*phase-.55*gesture-.45*bend
            p['forearm'+suffix].rotation_euler.x=-.28-.6*gesture-.45*bend
            p['arm'+suffix].rotation_euler.z=side*(.04+.03*math.sin(t))
            foot,pole=self.feet[side]
            stride=.22*phase if walk else 0
            lift=max(0,phase)*.08 if walk else 0
            local=Vector((side*.15,-stride,.13+lift))
            rot=self.rig.rotation_euler.to_matrix();world=Vector((x,y,0))
            foot.location=world+rot@local
            pole.location=world+rot@Vector((side*.15,-1.0,.45))
            shoe=self.features['shoe'+suffix];shoe.location=world+rot@Vector((side*.15,-stride-.075,.085+lift));shoe.rotation_euler=(0,0,yaw)
        phase=(t+(1.1 if self.old else 0))%4.3;blink=max(0,1-abs(phase-.11)/.11)
        for key,ob in self.features.items():
            if ob.data.shape_keys:
                keys=ob.data.shape_keys.key_blocks
                if 'Blink' in keys:keys['Blink'].value=blink
                if 'Look' in keys:keys['Look'].value=.5+.5*math.sin(t*.7)
                if 'Smile' in keys:keys['Smile'].value=smile
                if 'Expression' in keys:keys['Expression'].value=.25+.45*smile+.2*math.sin(t*.8)

    def hand(self,side,position):
        target,constraint=self.targets[side];target.location=position;constraint.influence=1
