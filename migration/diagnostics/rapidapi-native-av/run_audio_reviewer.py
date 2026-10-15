"""Bounded blind native-audio inference; a candidate reviewer, not a QA bypass."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import resource

p = argparse.ArgumentParser()
p.add_argument('--case', choices=['silence', 'speech', 'tone', 'opening-full', 'opening-0', 'opening-10', 'opening-20', 'opening-30'], required=True)
p.add_argument('--model',choices=['gemma','qwen'],default='gemma')
args = p.parse_args()
root = Path('rapidapi-native-av')
out = root / ('audio-reviewer-results' if args.model=='gemma' else 'qwen-audio-reviewer-results')
out.mkdir(exist_ok=True)
manifest = json.loads((root / ('reviewer-model-receipt.json' if args.model=='gemma' else 'qwen-reviewer-model-receipt.json')).read_text())
assert len(manifest['files']) == 2
for item in manifest['files']:
    assert Path(item['path']).stat().st_size == item['bytes']
weights, projector = [item['path'] for item in manifest['files']]
audio = out / (args.case + '.wav')
if args.case == 'silence':
    command = ['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','anullsrc=r=16000:cl=mono','-t','10',str(audio)]
elif args.case == 'speech':
    command = ['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
        'flite=text=The blue train arrived after midnight. There are seven yellow lamps.:voice=kal',
        '-ar','16000','-ac','1',str(audio)]
elif args.case == 'tone':
    command = ['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','sine=frequency=440:sample_rate=16000:duration=8',str(audio)]
else:
    start = 0 if args.case=='opening-full' else int(args.case.split('-')[1])
    command = ['ffmpeg','-nostdin','-v','error','-ss',str(start),'-i',str(root/'received/audio-review.wav'),
        '-t','40' if args.case=='opening-full' else '10','-ar','16000','-ac','1',str(audio)]
if not audio.exists():
    subprocess.run(command, check=True, timeout=30, capture_output=True)
prompt = ('Describe only the sounds in the attached audio. Distinguish speech, singing, instruments, '
    'ambience and noise. If words are audible, transcribe only words you actually hear. '
    'Describe pace and any abrupt cuts or distortion. Say uncertain where necessary. '
    'Do not infer video content. Answer concisely in English.')
binary = root / 'llama-cpu/llama-b11658/llama-cli'
invocation = [str(binary),'-m',weights,'--mmproj',projector,
    '--no-mmproj-offload','--audio',str(audio),'-p',prompt,'-c','2048','-n','192',
    '-t','2','-tb','2','-b','32','-ub','32','--temp','0','--seed','17','--no-warmup',
    '--log-colors','off','--jinja','--single-turn','--reasoning','off','--no-display-prompt']
started = time.monotonic()
with (out/(args.case+'.stdout.txt')).open('wb') as stdout, (out/(args.case+'.stderr.txt')).open('wb') as stderr:
    try:
        run = subprocess.run(invocation, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, timeout=300)
        code = run.returncode
    except subprocess.TimeoutExpired:
        code = 'TIMEOUT_300_SECONDS'
result = {'case':args.case,'source_audio_sha256':hashlib.sha256(audio.read_bytes()).hexdigest(),
    'model_manifest':manifest,'binary_release':'ggml-org/llama.cpp b11658 official Ubuntu CPU',
    'binary_archive_sha256':'457c7145ecdf7d9cf575b4c7357ab8cf6eed3943576b3e9955b02bd7488e7174',
    'prompt':prompt,'input_was_actual_audio':True,'title_or_transcript_or_classifier_fed_to_model':False,
    'exit_code':code,'elapsed_seconds':time.monotonic()-started,'api_inference_calls':0,
    'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    'perceptual_quality_approved':False,'candidate_not_adopted':True,
    'stdout_file':args.case+'.stdout.txt','stderr_file':args.case+'.stderr.txt'}
(out/(args.case+'.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'case':args.case,'exit_code':code,'elapsed_seconds':result['elapsed_seconds']}))
