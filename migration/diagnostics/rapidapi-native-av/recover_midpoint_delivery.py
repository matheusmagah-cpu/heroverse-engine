"""One delivery-only recovery; no API secret, job start or provider polling."""
import hashlib
import json
from pathlib import Path
import time
import argparse
import native_probe as n
from next_window import inspect

p = argparse.ArgumentParser()
p.add_argument('--attempt-dir',type=Path,default=Path('rapidapi-native-av/midpoint-attempt'))
p.add_argument('--output-dir',type=Path,default=Path('rapidapi-native-av/midpoint-recovered'))
args=p.parse_args()
source = args.attempt_dir
out = args.output_dir
out.mkdir(exist_ok=True)
prior = json.loads((source/'receipt.json').read_text())
assert prior['provider_job_id'] == 'v2_stream_065e6ed9572627501de7'
assert prior['download_tools_call_requests'] == 1 and prior['failure_code'] == 'TimeoutError'
assert 'delivery_http_status' not in prior and not (source/'native.mp4').exists()
value = json.loads((source/'progress-03.json').read_text())
assert value['success'] == 1 and value['progress'] == 1000
url = value['download_url']
receipt = {'version':'native-midpoint-delivery-recovery-v1',
    'provider_job_id':prior['provider_job_id'],'source_video_id':'j2rk8ycXe3c',
    'source_requested_seconds':[6354,6364], 'new_provider_jobs':0,'provider_api_calls':0,
    'delivery_attempt':2, 'first_delivery_received_bytes':0,
    'prior_error':'TimeoutError before response headers',
    'concrete_change':'Same destination validation and credential-free client; socket timeout90s instead of30s; no acquisition retry.',
    'delivery_url_sha256':hashlib.sha256(url.encode()).hexdigest(),
    'status':'DELIVERY_ATTEMPTED_RESULT_NOT_YET_KNOWN',
    'production':False,'publication':False,'supervisor':False,
    'recurring_capacity_qualified':False,'perceptual_audio_review_completed':False}
with (out/'recovery-claim.json').open('x') as f:
    json.dump(receipt,f,indent=2)
started = time.monotonic()
try:
    n.fetch_media(url,out,receipt,timeout=90)
    inspect(out,receipt)
    receipt['status']='EXISTING_MIDPOINT_DELIVERED_AND_DECODED'
except n.HTTPError as error:
    receipt['status']='DELIVERY_RECOVERY_FAILED_NO_AUTOMATIC_RETRY'
    receipt['failure_type']='HTTPError'
    receipt['failure_code']='HTTP_'+str(error.code)
    receipt['delivery_http_status']=error.code
except Exception as error:
    receipt['status']='DELIVERY_RECOVERY_FAILED_NO_AUTOMATIC_RETRY'
    receipt['failure_type']=type(error).__name__
    if isinstance(error,n.ProbeError):
        receipt['failure_code']=str(error)
finally:
    receipt['elapsed_seconds']=time.monotonic()-started
    (out/'recovery-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))
raise SystemExit(0 if receipt['status']=='EXISTING_MIDPOINT_DELIVERED_AND_DECODED' else 2)

