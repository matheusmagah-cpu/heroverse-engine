"""Restore exact public upstream model bytes without private repository authority."""
import hashlib,json,os,tempfile,urllib.request
from pathlib import Path
ASSETS=[{"name":"kokoro-v1.0.fp16.onnx","size":163527961,"sha256":"f3a290d384fbb27966d462905c71a46cef9e5fd00516b40df32a0b4afe77ac96","url":"https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.fp16.onnx"},{"name":"voices-v1.0.bin","size":28214398,"sha256":"bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d","url":"https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin"}]
def main():
    results=[]
    with tempfile.TemporaryDirectory(prefix='heroverse-public-voice-') as tmp:
        for a in ASSETS:
            digest=hashlib.sha256(); size=0; path=Path(tmp)/a['name']
            with urllib.request.urlopen(a['url'],timeout=30) as response,path.open('xb') as out:
                while chunk:=response.read(1024*1024):
                    size+=len(chunk)
                    if size>a['size']: raise ValueError('oversized upstream asset')
                    digest.update(chunk); out.write(chunk)
            assert size==a['size'] and digest.hexdigest()==a['sha256']
            results.append({'name':a['name'],'bytes':size,'sha256':digest.hexdigest()})
    print(json.dumps({'status':'EXACT_UPSTREAM_VOICE_RESTORE_PASS','assets':results,'credentials_used':False,'windows_contact':False,'model_executed':False,'production_ready':False,'release_authority':False}))
if __name__=='__main__':main()
