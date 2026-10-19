"""Blender-only evaluated pose tests; not a substitute for watched visual QA.
Run: blender -b --python test_rig.py (writes only to a temporary RENDER_OUT).
"""
import json, os, sys, tempfile, unittest
from pathlib import Path
try:
    import bpy
except ImportError:
    bpy=None

@unittest.skipIf(bpy is None,'requires pinned Blender 4.3.2')
class RigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();os.environ['RENDER_OUT']=cls.temp.name
        root=Path(__file__).resolve().parent;story=json.loads((root/'story.json').read_text());cursor=0;rows=[]
        for row in story['scenes']:
            end=cursor+round(row['target_seconds']*24);rows.append({'id':row['id'],'first_frame':cursor,'end_frame':end});cursor=end
        timing=Path(cls.temp.name)/'timing.json';timing.write_text(json.dumps({'fps':24,'frames_total':cursor,'scenes':rows}))
        sys.argv=['production.py','--','master','0','1','--timing',str(timing)]
        path=root/'production.py';cls.g={'__file__':str(path)}
        # Build the same production scene without invoking the render loop.
        exec(compile(path.read_text().split('\njobs=[]')[0],str(path),'exec'),cls.g)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_evaluated_wrist_reach(self):
        for frame in [600,1848,1919,1967,2088,2328,2568,3048]:
            self.g['scene'](frame,False)
            for who in ['young','elder']:
                c=self.g[who]
                for side,(target,constraint) in c.targets.items():
                    if constraint.influence:
                        wrist=c.rig.matrix_world@c.rig.pose.bones['forearm'+str(side)].tail
                        self.assertLess((wrist-target.location).length,.03,(frame,who,side))
    def test_kneeling_clearance_and_tailoring(self):
        self.g['scene'](1967,False)
        for who in ['young','elder']:
            c=self.g[who]
            self.assertIn('tailored_height',c.body.data.attributes)
            for side in [-1,1]:
                knee=c.rig.matrix_world@c.rig.pose.bones['shin'+str(side)].head
                self.assertGreater(knee.z,.10)
                self.assertIn('Grip',c.features['finger'+str(side)+'0'].data.shape_keys.key_blocks)
        self.assertEqual(self.g['s'].eevee.taa_render_samples,64)

if __name__=='__main__':unittest.main(argv=[sys.argv[0]])
