"""Read one pinned private release asset using the job-scoped token."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request
import zipfile

ASSET=637720288
SIZE=191743202
DIGEST='da369014614e6df046d8b43065d77b92c32e6c2d49617b154be9e118a1ee9171'

class NoCrossOriginCredentialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        redirected=super().redirect_request(request,fp,code,message,headers,newurl)
        if redirected:
            redirected.remove_header('Authorization')
        return redirected

def main():
    token=os.environ['HEROVERSE_JOB_TOKEN']
    url=f'https://api.github.com/repos/matheusmagah-cpu/heroverse-engine/releases/assets/{ASSET}'
    request=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,
        'Accept':'application/octet-stream','X-GitHub-Api-Version':'2022-11-28'})
    opener=urllib.request.build_opener(NoCrossOriginCredentialRedirect())
    with tempfile.TemporaryDirectory(prefix='heroverse-voice-') as tmp:
        archive=Path(tmp)/'voice.zip'; digest=hashlib.sha256(); size=0
        with opener.open(request,timeout=30) as response,archive.open('xb') as stream:
            while chunk:=response.read(1024*1024):
                size+=len(chunk)
                if size>SIZE:raise ValueError('oversized private asset')
                stream.write(chunk);digest.update(chunk)
        assert size==SIZE and digest.hexdigest()==DIGEST
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            names=set(z.namelist())
            assert names=={'models/kokoro/kokoro-v1.0.fp16.onnx','models/kokoro/voices-v1.0.bin','MANIFEST.json'}
        print(json.dumps({'status':'PRIVATE_VOICE_ASSET_ACCESS_AND_HASH_PASS','asset_id':ASSET,
          'bytes':size,'sha256':DIGEST,'windows_contact':False,'model_executed':False,
          'production_ready':False,'publication_authority':False}))

if __name__=='__main__':main()
