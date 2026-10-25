#!/usr/bin/env python3
"""Offline: the Agnes test clip waits out a full free queue, follows the task to its MP4 and never sends the key
anywhere but the Authorization header."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agnes_clip as ac  # noqa: E402


class Agnes(unittest.TestCase):
    def test_a_full_queue_is_retried_then_the_task_is_followed_to_its_mp4(self):
        calls, slept = [], []
        replies = iter([{"_http": 503, "error": {"code": "video_queue_full"}},
                        {"_http": 200, "data": {"video_id": "v1"}},
                        {"_http": 200, "data": {"status": "processing"}},
                        {"_http": 200, "data": {"status": "completed", "video_url": "https://cdn.example/v1.mp4"}}])

        def call(method, url, key, body=None):
            calls.append((method, url, key, body))
            return next(replies)
        vid = ac.create("light over the deep", "sk-test", call=call, sleep=slept.append)
        url, _ = ac.wait(vid, "sk-test", call=call, sleep=slept.append)
        self.assertEqual((vid, url), ("v1", "https://cdn.example/v1.mp4"))
        body = calls[1][3]
        self.assertEqual((body["model"], body["size"], body["aspect_ratio"]), (ac.MODEL, "720P", "9:16"))
        self.assertTrue(all(c[2] == "sk-test" and "sk-test" not in str(c[3]) + c[1] for c in calls))  # header only
        self.assertIn("model_name=agnes-video-2.5-flash", calls[2][1])
        self.assertEqual(len(slept), 2)

    def test_a_failed_task_or_a_refused_create_stops_loudly(self):
        with self.assertRaises(SystemExit):
            ac.wait("v1", "k", call=lambda *a, **k: {"_http": 200, "data": {"status": "failed"}}, sleep=lambda s: None)
        with self.assertRaises(SystemExit):
            ac.create("x", "k", call=lambda *a, **k: {"_http": 401, "error": "bad key"}, sleep=lambda s: None)


if __name__ == "__main__":
    unittest.main()
