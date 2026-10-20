import sys, unittest, tempfile
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import shorts_intrashot as motion


class IntrashotTests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(7)
        self.image=rng.integers(20,220,(384,216,3),dtype=np.uint8)
    def test_deterministic_native_shape_and_input_unchanged(self):
        before=self.image.copy()
        for kind in ('lamp','water'):
            scene=motion.Intrashot(self.image,kind)
            a,b=scene.frame(2.5),scene.frame(2.5)
            self.assertTrue(np.array_equal(a,b));self.assertEqual(a.shape,self.image.shape)
            self.assertEqual(a.dtype,np.uint8)
        self.assertTrue(np.array_equal(before,self.image))
    def test_zero_strength_is_exact_control(self):
        for kind in ('lamp','water'):
            self.assertTrue(np.array_equal(motion.Intrashot(self.image,kind).frame(3,0),self.image))
    def test_water_moves_without_camera_and_preserves_sky(self):
        scene=motion.Intrashot(self.image,'water');a,b=scene.frame(0),scene.frame(2)
        self.assertTrue(np.array_equal(a[:150],b[:150]))
        self.assertGreater(np.abs(a[220:].astype(float)-b[220:].astype(float)).mean(),1)
    def test_lamp_changes_without_camera_and_preserves_distant_sky(self):
        scene=motion.Intrashot(self.image,'lamp');a,b=scene.frame(0),scene.frame(1)
        self.assertTrue(np.array_equal(a[:40],b[:40]))
        self.assertGreater(np.abs(a[160:250,:60].astype(float)-b[160:250,:60].astype(float)).mean(),.1)
    def test_mux_copies_complete_audio_without_time_or_frame_limit(self):
        args=motion.mux_args('video.mp4','baseline.mp4','out.mp4')
        self.assertIn('1:a:0',args)
        self.assertEqual(args[args.index('-c')+1],'copy')
        for option in ('-t','-shortest','-frames:v','-frames:a'):
            self.assertNotIn(option,args)

    def test_bad_inputs_fail(self):
        with self.assertRaises(ValueError):motion.Intrashot(self.image,'unknown')
        with self.assertRaises(ValueError):motion.Intrashot(self.image,'lamp').frame(float('nan'))
        with self.assertRaises(ValueError):motion.Intrashot(self.image,'lamp').frame(1,2)
    def test_renderer_rejects_source_overwrite_before_reading(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            args=[root/'baseline.mp4',root/'selection.json',root/'timeline.json',root/'script.json',root/'images']
            for output in args[:4]+[args[4]/'bg-lamp-window.png']:
                with self.assertRaisesRegex(ValueError,'SOURCE_OVERWRITE_FORBIDDEN'):
                    motion.render(*args,output)

    def test_renderer_rejects_work_directory_input_collision(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with self.assertRaisesRegex(ValueError,'WORK_DIRECTORY_OVERLAPS_SOURCE'):
                motion.render(root/'baseline.mp4',root/'selection.json',root/'timeline.json',root/'script.json',root/'intrashot-work',root/'out.mp4')

    def test_camera_starts_identity_and_ends_exact_six_percent(self):
        import cv2
        self.assertTrue(np.array_equal(motion.camera(self.image,0,31),self.image))
        h,w=self.image.shape[:2];z=1.06
        expected=cv2.warpAffine(self.image,np.array([[z,0,(1-z)*(w-1)/2],[0,z,(1-z)*(h-1)/2]],np.float32),(w,h),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REFLECT_101)
        self.assertTrue(np.array_equal(motion.camera(self.image,30,31),expected))


if __name__=='__main__':unittest.main()
