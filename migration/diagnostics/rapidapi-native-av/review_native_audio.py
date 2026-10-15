from pathlib import Path
import hashlib,json,time,datetime,subprocess
import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.utils import download_model
root=Path('rapidapi-native-av/received')
audio=root/'audio-review.wav'
started=time.monotonic()
model_path=Path(download_model('base',cache_dir='rapidapi-native-av/model-cache'))
weights=model_path/'model.bin'
model=WhisperModel(str(model_path),device='cpu',compute_type='int8',cpu_threads=4,num_workers=1)
decoded=subprocess.run(['ffmpeg','-v','error','-i',str(audio),'-f','f32le','-ac','1','-ar','16000','pipe:1'],capture_output=True,check=True,timeout=30)
assert not decoded.stderr, 'ASR derivative decode emitted errors'
asr_audio=np.frombuffer(decoded.stdout,dtype='<f4').copy()
assert len(asr_audio)>0 and np.isfinite(asr_audio).all()
segments,info=model.transcribe(asr_audio,beam_size=5,vad_filter=True,word_timestamps=True,condition_on_previous_text=False)
rows=[{'start':s.start,'end':s.end,'text':s.text,'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'words':[{'start':w.start,'end':w.end,'word':w.word,'probability':w.probability} for w in (s.words or [])]} for s in segments]
result={'version':'native-reference-audio-asr-v1','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'input_pcm_sha256':hashlib.sha256(audio.read_bytes()).hexdigest(),'source_video_sha256':'5dca962757c952c8048c746f23f96a325cf15258f429e1e79e7b5ddf72fb0fb5','model':'faster-whisper 1.2.1 / base / cpu int8','model_weights_sha256':hashlib.sha256(weights.read_bytes()).hexdigest(),'model_cache_snapshot':str(model_path),'duration':info.duration,'duration_after_vad':info.duration_after_vad,'detected_language':info.language,'language_probability':info.language_probability,'segments':rows,'elapsed_seconds':time.monotonic()-started,'human_or_direct_model_listening_completed':False,'no_external_audio_upload':True,'gemini_calls':0,'qualification_scope':'Native PCM machine transcription only; no perceptual-quality or whole-reference approval.'}
result['asr_derivative']={'sample_rate':16000,'channels':1,'format':'float32 little-endian','samples':len(asr_audio),'sha256':hashlib.sha256(decoded.stdout).hexdigest(),'native_pcm_unchanged':True,'reason':'Documented ndarray input avoids installed PyAV metadata_errors incompatibility; FFmpeg explicitly creates only an ASR derivative.'}
(root/'native-audio-asr.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(result,ensure_ascii=False))
