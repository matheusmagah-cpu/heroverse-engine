# Kaggle job: full HeroVerse production of one pilot (voice, cut-out, assembly,
# QA, package, Shorts, inspection sheets) with the same pinned runtimes as the
# GitHub route. PAYLOAD (prepended by kaggle_run.py): {"pilot": "pilot-00N", "shorts": 3}.
# Inputs come from the owner's private Kaggle dataset; heavy intermediates stay
# in /tmp so only the deliverables are saved as kernel output.
import glob
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

P = json.loads(PAYLOAD)  # noqa: F821
PILOT = P["pilot"]
T0 = time.time()


def sh(cmd, **kw):
    print("+", cmd if isinstance(cmd, str) else " ".join(map(str, cmd)), f"[{round(time.time() - T0)} s]", flush=True)
    subprocess.run(cmd, check=True, shell=isinstance(cmd, str), **kw)


src = Path(next(p for p in glob.glob("/kaggle/input/**/engine.tar", recursive=True))).parent
W = Path("/tmp/hv")
W.mkdir(parents=True, exist_ok=True)
sh(["tar", "-xf", str(src / "engine.tar"), "-C", str(W)])
repo = W / "repo"
OUT = Path("/kaggle/working/out")
OUT.mkdir(parents=True, exist_ok=True)

# ffmpeg with libass (static build fallback) and DejaVu fonts for libass
ok = shutil.which("ffmpeg") and "ass" in subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
if not ok:
    sh("cd /tmp && curl -sSL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | tar -xJ "
       "&& cp /tmp/ffmpeg-*-amd64-static/ffmpeg /tmp/ffmpeg-*-amd64-static/ffprobe /usr/local/bin/")
fonts = Path.home() / ".fonts"
fonts.mkdir(exist_ok=True)
for f in glob.glob(str(src / "fonts" / "*.ttf")):
    shutil.copy(f, fonts)
Path("/usr/share/fonts/truetype/dejavu").mkdir(parents=True, exist_ok=True)
for f in glob.glob(str(src / "fonts" / "*.ttf")):
    shutil.copy(f, "/usr/share/fonts/truetype/dejavu/")
subprocess.run(["fc-cache", "-f"], check=False)

# Python 3.12 virtual environments, pinned exactly as on GitHub
sh([sys.executable, "-m", "pip", "install", "-q", "uv"])
venvs = {
    "voice": ["kokoro-onnx==0.4.9", "onnxruntime==1.20.1", "numpy==2.2.6", "espeakng-loader==0.2.4", "soundfile==0.13.1"],
    "qa": ["ai-edge-litert==2.3.0", "faster-whisper==1.2.1"],
    "cut": ["rembg==2.0.59", "onnxruntime==1.20.1", "pillow==11.0.0"],
}
for name, pkgs in venvs.items():
    sh(["uv", "venv", "-q", "-p", "3.12", str(W / name)])
    sh(["uv", "pip", "install", "-q", "-p", str(W / name / "bin/python"), *pkgs])
py = {n: str(W / n / "bin/python") for n in venvs}
env = dict(os.environ, OMP_NUM_THREADS="4")
prod = repo / "migration/production"
work, inp = W / "work", W / "in"
(inp / "img").mkdir(parents=True, exist_ok=True)
for f in glob.glob(str(src / "img" / "*")):
    shutil.copy(f, inp / "img")
script = prod / PILOT / "script.json"
os.chdir(repo)
sh([py["voice"], "-I", "-B", str(prod / "pilot_render.py"), "prepare", str(work), str(repo / "HeroVerse_Linux_Source_Ready_20261013_v2.zip")], env=env)
sh([py["voice"], "-I", "-B", str(prod / "pilot_render.py"), "voice", str(work), str(script)], env=env)
figure = json.loads(script.read_text())["figure"]
sh([py["cut"], "-I", "-B", str(repo / "migration/production/imagegen/cutout.py"), str(inp / "img" / f"{figure}.png"),
    str(inp / "img" / f"{figure}.json"), str(inp / "figure.png")], env=env)
music = str(src / "original-rest-music.lossless.flac")
sh([py["voice"], "-I", "-B", str(prod / "still_render.py"), "assemble", str(work), str(script), str(inp / "img"),
    str(inp / "figure.png"), music], env=env)
models = W / "models"
models.mkdir(exist_ok=True)
sh([py["qa"], "-I", "-c", f"import sys; from pathlib import Path; sys.path.insert(0, '{repo / 'migration'}'); "
    f"import second_opening_asr as a; a.extract_model(Path('{src / 'HeroVerse_ASR_base_en_preservado.zip'}'), Path('{models / 'whisper'}'))"])
qa = subprocess.run([py["qa"], "-I", "-B", str(prod / "qa_pilot.py"), str(work / "pilot.mp4"), str(work / "manifest.json"),
                     str(script), str(prod / PILOT / "qa_criteria.json"), str(src / "yamnet.tflite"), str(models / "whisper"),
                     str(work / "qa.json")], env=env)
sh([py["voice"], "-I", "-B", str(prod / "package_pilot.py"), str(work), str(script), str(work / "package")], env=env)
sh([py["voice"], "-I", "-B", str(prod / "shorts_cut.py"), str(work), str(script), str(inp / "img"), str(inp / "figure.png"),
    music, str(OUT / "shorts"), str(P.get("shorts", 3))], env=env)
insp = OUT / "inspection"
insp.mkdir(exist_ok=True)
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(work / "pilot.mp4")],
                           capture_output=True, text=True).stdout)
rows = -(-int(dur // 20 + 1) // 4)
sh(["ffmpeg", "-v", "error", "-y", "-i", str(work / "pilot.mp4"), "-vf", f"fps=1/20,scale=480:270,tile=4x{rows}", "-frames:v", "1",
    "-q:v", "4", str(insp / "pilot-contact-sheet.jpg")])
sh(["ffmpeg", "-v", "error", "-y", "-t", "40", "-i", str(work / "pilot.mp4"), "-vf", "fps=1/2.5,scale=480:270,tile=4x4",
    "-frames:v", "1", "-q:v", "4", str(insp / "opening-sheet.jpg")])
sh(["ffmpeg", "-v", "error", "-y", "-i", str(inp / "figure.png"), "-vf", "scale=-1:540,pad=iw+40:ih+40:20:20:color=0x808080",
    str(insp / "figure-cutout.jpg")])
for name in ("pilot.mp4", "manifest.json", "timeline.json", "captions.ass", "qa.json"):
    if (work / name).exists():
        shutil.copy(work / name, OUT / name)
shutil.copytree(work / "package", OUT / "package", dirs_exist_ok=True)
print(json.dumps({"qa_exit": qa.returncode, "elapsed_s": round(time.time() - T0)}), flush=True)
