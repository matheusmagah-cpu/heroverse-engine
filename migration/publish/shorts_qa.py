#!/usr/bin/env python3
"""Technical gate for one Short before upload (frozen; never edited to pass a file).

PASS needs: full decode without errors; one H.264 video stream 1080x1920 at
30 fps; one AAC stereo 48 kHz audio stream; 15-60 s; integrated loudness
-16..-12 LUFS; true peak <= -1.0 dBTP.
usage: shorts_qa.py SHORT.mp4
"""
import json
import re
import subprocess
import sys

CRITERIA = {"width": 1080, "height": 1920, "fps": 30, "seconds": [15, 60], "lufs": [-16.0, -12.0], "true_peak_max": -1.0}


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def loudness(path):
    err = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    summary = err[err.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    return (float(i.group(1)) if i else None), (float(tp.group(1)) if tp else None)


def check(path):
    p = probe(path)
    v = [s for s in p["streams"] if s["codec_type"] == "video"]
    a = [s for s in p["streams"] if s["codec_type"] == "audio"]
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], capture_output=True, text=True).stderr.strip()
    seconds = float(p["format"]["duration"])
    lufs, tp = loudness(path)
    checks = {
        "decode_clean": decode == "",
        "one_h264_1080x1920": len(v) == 1 and v[0]["codec_name"] == "h264" and (v[0]["width"], v[0]["height"]) == (1080, 1920),
        "fps_30": len(v) == 1 and v[0]["r_frame_rate"] in ("30/1", "30000/1000"),
        "one_aac_stereo_48k": len(a) == 1 and a[0]["codec_name"] == "aac" and a[0]["channels"] == 2 and a[0]["sample_rate"] == "48000",
        "duration": CRITERIA["seconds"][0] <= seconds <= CRITERIA["seconds"][1],
        "loudness": lufs is not None and CRITERIA["lufs"][0] <= lufs <= CRITERIA["lufs"][1],
        "true_peak": tp is not None and tp <= CRITERIA["true_peak_max"],
    }
    return {"file": str(path), "seconds": round(seconds, 2), "lufs": lufs, "true_peak_dbtp": tp, "checks": checks,
            "status": "PASS" if all(checks.values()) else "FAIL"}


if __name__ == "__main__":
    r = check(sys.argv[1])
    print(json.dumps(r, indent=1))
    sys.exit(0 if r["status"] == "PASS" else 1)
