"""Measure the complete, pinned final audio using the native QA loudnorm filter."""
import hashlib,json,math,re,subprocess,time
from pathlib import Path

video=Path('output/HeroVerse_Rest_Corrected_3h_Metricool.mp4')
expected='55c2a047e107ce42469261978ab34353e58622ec436e40876f6a8fc71c882c46'
assert hashlib.sha256(video.read_bytes()).hexdigest()==expected
inventory=json.loads(Path('production-review/native-frame-inventory.json').read_text())
assert inventory['decoded_frames']==324000 and inventory['decode_errors']==0
command=['ffmpeg','-hide_banner','-nostats','-v','info','-i',str(video),'-map','0:a:0','-vn',
    '-af','loudnorm=I=-16:TP=-1.5:LRA=8:print_format=json','-f','null','-']
start=time.monotonic();result=subprocess.run(command,capture_output=True,text=True,timeout=600)
Path('production-review/final-audio-measurement.stderr.txt').write_text(result.stderr)
if result.returncode:raise PermissionError('FULL_FINAL_AUDIO_DECODE_FAILED')
matches=re.findall(r'\{\s*"input_i".*?\}',result.stderr,re.S)
if not matches:raise PermissionError('COMPLETE_LOUDNESS_REPORT_REQUIRED')
raw=json.loads(matches[-1]);i=float(raw['input_i']);tp=float(raw['input_tp'])
if not all(math.isfinite(v) for v in (i,tp)):raise PermissionError('FINITE_AUDIO_MEASUREMENT_REQUIRED')
profile_path=Path('source-recovered/native/project/config/production_quality_profiles/standard-v1.json')
profile=json.loads(profile_path.read_text());minimum=profile['technical_minimums']
level=minimum['loudness_lufs'];gates={'FINAL_LOUDNESS':abs(i-level['target'])<=level['tolerance'],
    'FINAL_TRUE_PEAK':tp<=minimum['true_peak_dbtp']}
assert hashlib.sha256(video.read_bytes()).hexdigest()==expected
report={'status':'COMPLETE_FINAL_MASTER_AUDIO_MEASURED','master_sha256':expected,
    'integrated_lufs':i,'true_peak_dbtp':tp,'lra_lu':float(raw['input_lra']),
    'profile_sha256':hashlib.sha256(profile_path.read_bytes()).hexdigest(),
    'target_lufs':level,'maximum_true_peak_dbtp':minimum['true_peak_dbtp'],
    'gates':{k:'PASS' if v else 'FAIL' for k,v in gates.items()},
    'native_filter':'loudnorm=I=-16:TP=-1.5:LRA=8:print_format=json',
    'method':'FULL_AUDIO_ONLY_DECODE_NATIVE_INPUT_MEASUREMENTS_NO_FILE_MODIFICATION',
    'elapsed_seconds':round(time.monotonic()-start,3),'final_production_approved':False,
    'publication_authorized':False}
Path('production-review/final-audio-measurement.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report),flush=True)
