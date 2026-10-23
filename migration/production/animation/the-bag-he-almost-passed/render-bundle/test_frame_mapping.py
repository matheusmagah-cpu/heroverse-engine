#!/usr/bin/env python3
import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('frame_mapping',Path(__file__).with_name('frame_mapping.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class FrameMapTests(unittest.TestCase):
    def test_no_cumulative_rounding_drift(self):
        spans=[{'master_start_s':i*2+.001,'master_end_s':i*2+.111} for i in range(5)]
        frames=m.short_frames({'spans':spans,'total_s':.55});self.assertEqual(len(frames),round(.55*24));self.assertAlmostEqual(frames[0],.024)
    def test_speed_one_and_cut(self):
        frames=m.short_frames({'spans':[{'master_start_s':10,'master_end_s':11},{'master_start_s':20,'master_end_s':21}],'total_s':2})
        self.assertEqual(len(frames),48)
        for actual,expected in zip(frames,list(range(240,264))+list(range(480,504))):self.assertAlmostEqual(actual,expected)
    def test_fractional_end_does_not_duplicate(self):
        frames=m.short_frames({'spans':[{'master_start_s':110.038,'master_end_s':152.019}],'total_s':41.981})
        self.assertEqual(len(frames),round(41.981*24));self.assertLess(frames[-1],round(152.019*24))
        for a,b in zip(frames,frames[1:]):self.assertAlmostEqual(b-a,1)
    def test_invalid_total(self):
        with self.assertRaises(ValueError):m.short_frames({'spans':[{'master_start_s':1,'master_end_s':2}],'total_s':3})


if __name__=='__main__':unittest.main(verbosity=2)
