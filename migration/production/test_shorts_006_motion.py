#!/usr/bin/env python3
"""Independent numerical oracles for the closed native v2 treatment."""
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import unittest
import numpy as np
import shorts_006_motion as m


class NativeMotion(unittest.TestCase):
    def test_camera_knots_and_derivatives(self):
        self.assertEqual([m.camera_x(0,t) for t in (0,3,21.2)], [0,40,48])
        eps=1e-5
        self.assertAlmostEqual((m.camera_x(0,eps)-m.camera_x(0,0))/eps,20,places=3)
        self.assertAlmostEqual((m.camera_x(0,3)-m.camera_x(0,3-eps))/eps,.5,places=3)
        self.assertAlmostEqual((m.camera_x(0,3+eps)-m.camera_x(0,3))/eps,.5,places=3)
        self.assertAlmostEqual((m.camera_x(0,21.2)-m.camera_x(0,21.2-eps))/eps,.3,places=3)
        self.assertEqual([m.camera_x(1,t) for t in (0,637/60,637/30)], [448,464,480])

    def test_all_frame_centers_in_bounds_moon_excluded(self):
        for i in range(637):
            x=m.camera_x(0,i/30)
            self.assertGreaterEqual(x,0);self.assertLessEqual(x+1080,1128)
            if i: self.assertGreater(x,previous)
            previous=x
        for i in range(638):
            x=m.camera_x(1,i/30)
            self.assertGreaterEqual(x,448);self.assertLessEqual(x+1152,1632)

    def test_exact_inward_segment_distance(self):
        square=((0,0),(100,0),(100,100),(0,100))
        np.testing.assert_allclose(m.polygon_mask([-1,0,3,6,12,50,100],[50]*7,square),[0,0,.25,.5,1,1,0])
        # Slanted edge distance, not an axis distance or raster approximation.
        triangle=((0,0),(100,100),(100,0))
        self.assertAlmostEqual(float(m.polygon_mask(50,44,triangle)),6/math.sqrt(2)/12,places=6)
        self.assertEqual(float(m.polygon_mask(50,50,triangle)),0)

    def test_mask_support_and_exclusions(self):
        u,v=np.meshgrid(np.arange(2048),np.arange(1984))
        a,b=[m.polygon_mask(u,v,p) for p in m.POLYGONS]
        self.assertFalse(np.any((a>0)&(b>0)))
        for x,y in [(650,1450),(380,1060),(300,500)]:
            self.assertEqual(a[y,x]+b[y,x],0)
        self.assertEqual(a[1580,850],1);self.assertEqual(b[1340,930],1)
        for polygon in m.POLYGONS:
            for start,end in zip(polygon,polygon[1:]+polygon[:1]):
                for fraction in (0,.1,.5,.7,1):
                    x=start[0]+fraction*(end[0]-start[0]);y=start[1]+fraction*(end[1]-start[1])
                    self.assertEqual(float(m.polygon_mask(x,y,polygon)),0)


    def test_texture_exact_formula_cap_and_outside_unchanged(self):
        base=np.full((2048,2048,3),[.1,.4,.9],np.float32)
        for t in (0,1,3,21.2):
            output=m.texture_frame(base,t)
            self.assertLessEqual(float(np.max(np.abs(output-base))),.0600001)
            for x,v,phase in [(850,1580,0),(930,1340,math.pi/3)]:
                expected=base[v+64,x]+np.minimum(.06,.16*base[v+64,x])*math.sin(2*math.pi*((v+.15*x)/96-t/4)+phase)
                np.testing.assert_allclose(output[v+64,x],expected,atol=1e-7)
            for x,v in [(650,1450),(380,1060),(300,500)]:
                np.testing.assert_array_equal(output[v+64,x],base[v+64,x])
        np.testing.assert_array_equal(base[0,0],np.array([.1,.4,.9],np.float32))

    def test_bilinear_independent_affine_oracle(self):
        yy,xx=np.mgrid[:8,:9]
        base=np.stack((xx,yy,xx+2*yy),axis=-1).astype(np.float32)
        x=np.array([.01,1.123456,5.81234]);y=np.array([.56,4.123456])
        actual=m.bilinear_sample(base,x,y)
        xx,yy=np.meshgrid(x,y)
        expected=np.stack((xx,yy,xx+2*yy),axis=-1)
        np.testing.assert_allclose(actual,expected,atol=2e-6)

    def test_source_geometry_and_pond_camera_only(self):
        yy,xx=np.mgrid[:2048,:2048]
        base=np.stack((xx/2048,yy/2048,np.full(xx.shape,.2)),axis=-1).astype(np.float32)
        for scene,frame,count in [(0,0,637),(0,90,637),(1,0,638),(1,637,638)]:
            actual=m.source_frame(base,scene,frame,count)
            self.assertEqual(actual.shape,(1920,1080,3))
            width,height,y=(1080,1920,64) if scene==0 else (1152,2048,0)
            # Row zero is outside all water masks: exact affine camera oracle.
            expected_x=(m.camera_x(scene,frame/30)+(np.arange(1080)+.5)*width/1080-.5)/2048
            np.testing.assert_allclose(actual[0,:,0],expected_x,atol=1e-7)
            np.testing.assert_allclose(actual[0,:,1],(y+.5*height/1920-.5)/2048,atol=1e-7)
            if scene==1: np.testing.assert_allclose(actual[:,:,2],.2,atol=1e-7)

    def test_fail_closed_clocks_and_geometry(self):
        for args in [(0,0,638),(1,638,638),(False,0,637),(0,-1,637),(2,0,637)]:
            with self.assertRaises(ValueError):m.source_frame(None,*args)
        for t in [float('nan'),-1,22,True]:
            with self.assertRaises(ValueError):m.camera_x(0,t)
        with self.assertRaises(ValueError):m.source_frame(np.zeros((1920,1080,3)),0,0,637)

if __name__=='__main__':unittest.main()
