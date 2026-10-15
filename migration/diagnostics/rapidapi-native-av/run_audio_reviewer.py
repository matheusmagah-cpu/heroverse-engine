"""Bounded blind native-audio inference; a candidate reviewer, not a QA bypass."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import resource
import struct

def inspect_pcm_wave(data):
    result = {
        'version': 'pcm-digital-silence-v1',
        'source_audio_sha256': hashlib.sha256(data).hexdigest(),
        'status': 'INVALID_OR_UNSUPPORTED_PCM',
        'digital_silence': None,
        'allow_model_inference': False,
        'perceptual_quality_approved': False,
    }
    try:
        if len(data) < 12 or data[:4] != b'RIFF' or data[8:12] != b'WAVE':
            raise ValueError('Expected a RIFF/WAVE file')
        if struct.unpack_from('<I', data, 4)[0] + 8 != len(data):
            raise ValueError('RIFF length mismatch')
        chunks = {}
        pos = 12
        while pos < len(data):
            if pos + 8 > len(data):
                raise ValueError('Truncated chunk header')
            tag, size = struct.unpack_from('<4sI', data, pos)
            start = pos + 8
            end = start + size
            if end + (size & 1) > len(data):
                raise ValueError('Truncated chunk or padding')
            if tag in (b'fmt ', b'data'):
                if tag in chunks:
                    raise ValueError('Ambiguous duplicate PCM chunk')
                chunks[tag] = data[start:end]
            pos = end + (size & 1)
        fmt, pcm = chunks.get(b'fmt ', b''), chunks.get(b'data', b'')
        if len(fmt) not in (16, 18):
            raise ValueError('Unsupported format chunk')
        encoding, channels, rate, byte_rate, align, bits = struct.unpack_from('<HHIIHH', fmt)
        if encoding != 1 or bits not in (8, 16, 24, 32):
            raise ValueError('Only 8/16/24/32-bit integer PCM is supported')
        if len(fmt) == 18 and fmt[16:] != b'\0\0':
            raise ValueError('Unsupported PCM format extension')
        width = bits // 8
        if channels < 1 or rate < 1 or align != channels * width or byte_rate != rate * align:
            raise ValueError('Invalid PCM format parameters')
        if not pcm or len(pcm) % align:
            raise ValueError('Empty or incomplete PCM frames')
        # WAV 8-bit PCM is unsigned: its digital zero is 128, not byte 0.
        zero = 128 if bits == 8 else 0
        silent = all(value == zero for value in pcm)
        result.update({
            'status': 'DIGITAL_SILENCE' if silent else 'NONZERO_PCM',
            'digital_silence': silent,
            'allow_model_inference': not silent,
            'channels': channels, 'sample_rate': rate, 'bits_per_sample': bits,
            'frames': len(pcm) // align,
        })
        if silent:
            result['description'] = 'digital silence'
    except (ValueError, struct.error) as error:
        result['reason'] = str(error)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', choices=['silence', 'speech', 'tone', 'opening-full', 'opening-0', 'opening-10', 'opening-20', 'opening-30'], required=True)
    p.add_argument('--model',choices=['gemma','qwen'],default='gemma')
    args = p.parse_args()
    root = Path('rapidapi-native-av')
    out = root / ('audio-reviewer-results' if args.model=='gemma' else 'qwen-audio-reviewer-results')
    out.mkdir(exist_ok=True)
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
    pcm_guard = inspect_pcm_wave(audio.read_bytes())
    if not pcm_guard['allow_model_inference']:
        result = {
            'case': args.case,
            'source_audio_sha256': pcm_guard['source_audio_sha256'],
            'pcm_guard': pcm_guard,
            'description': pcm_guard.get('description'),
            'exit_code': 'SKIPPED_DIGITAL_SILENCE' if pcm_guard['digital_silence'] else 'BLOCKED_INVALID_PCM',
            'model_inference_performed': False,
            'model_stdout_used_as_evidence': False,
            'stdout_file': None,
            'stderr_file': None,
            'prior_stdout_stderr_ignored': True,
            'api_inference_calls': 0,
            'perceptual_quality_approved': False,
            'candidate_not_adopted': True,
            'semantic_approval_from_model_prose': False,
            'qualification_scope': 'Exact PCM zero detection only; no perceptual or production approval.',
        }
        (out/(args.case+'.json')).write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result))
        return 0 if pcm_guard['digital_silence'] else 2

    manifest = json.loads((root / ('reviewer-model-receipt.json' if args.model=='gemma' else 'qwen-reviewer-model-receipt.json')).read_text())
    assert len(manifest['files']) == 2
    for item in manifest['files']:
        assert Path(item['path']).stat().st_size == item['bytes']
    weights, projector = [item['path'] for item in manifest['files']]
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
        'pcm_guard':pcm_guard,'model_inference_performed':True,
        'semantic_approval_from_model_prose':False,'model_manifest':manifest,'binary_release':'ggml-org/llama.cpp b11658 official Ubuntu CPU',
        'binary_archive_sha256':'457c7145ecdf7d9cf575b4c7357ab8cf6eed3943576b3e9955b02bd7488e7174',
        'prompt':prompt,'input_was_actual_audio':True,'title_or_transcript_or_classifier_fed_to_model':False,
        'exit_code':code,'elapsed_seconds':time.monotonic()-started,'api_inference_calls':0,
        'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        'perceptual_quality_approved':False,'candidate_not_adopted':True,
        'stdout_file':args.case+'.stdout.txt','stderr_file':args.case+'.stderr.txt'}
    (out/(args.case+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'case':args.case,'exit_code':code,'elapsed_seconds':result['elapsed_seconds']}))

if __name__ == '__main__':
    raise SystemExit(main())
