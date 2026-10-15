"""One fixed cloud media request; never retries a start or approves production."""
from __future__ import annotations
import datetime as dt
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rapidapi-mcp"))
from connection_probe import Client, ENDPOINT, NoRedirect, ProbeError, read_reply, _validate_reply
from preflight import HOST, quota_headers

REQUEST_ID = "20261015-rapidapi-native-j2rk8ycXe3c-0-40-v1"
PARAMS = {"_endpoint":"/ajax/download.php","_method":"GET",
    "url":"https://www.youtube.com/watch?v=j2rk8ycXe3c","format":"1080",
    "start_time":0,"end_time":40,"add_info":"1","allow_extended_duration":"1","max_duration":240}
MAX_MEDIA_BYTES = 64 * 1024 * 1024
MAX_CONTROL_BYTES = 262144
MAX_POLLS = 24
EXPECTED_RUN_NUMBER = "2"  # Run 1 stopped before any effect: NATIVE_DECODER_UNAVAILABLE.


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def private_json(path, value, key):
    encoded = json.dumps(value, indent=2)
    if key:
        encoded = encoded.replace(key, "[REDACTED]")
    path.write_text(encoded + "\n")
    path.chmod(0o600)


def validate_preflight(value, now):
    if value.get("result", {}).get("status") != "CONTRACT_AND_QUOTA_RESPONSE_RECEIVED":
        raise ProbeError("QUOTA_PREFLIGHT_NOT_ACCEPTED")
    observed = dt.datetime.fromisoformat(value["observed_at"].replace("Z", "+00:00"))
    age = (now-observed).total_seconds()
    if age < 0 or age > 3600:
        raise ProbeError("QUOTA_PREFLIGHT_EXPIRED")
    q = value["result"].get("quota_headers", {})
    if (q.get("x-ratelimit-units-limit") != "500"
            or int(q.get("x-ratelimit-units-remaining", "0")) < 12
            or q.get("x-ratelimit-requests-limit") != "500000"
            or q.get("x-ratelimit-requests-remaining") != "499999"):
        raise ProbeError("UNEXPECTED_OR_INSUFFICIENT_INCLUDED_QUOTA")
    if value["result"].get("info_public_fields", {}).get("id") != "j2rk8ycXe3c":
        raise ProbeError("SOURCE_ID_NOT_BOUND")
    if value["result"].get("info_received_bytes", MAX_CONTROL_BYTES+1) > MAX_CONTROL_BYTES:
        raise ProbeError("CONTROL_BANDWIDTH_BASELINE_TOO_LARGE")
    schemas = {t["name"]:t["inputSchema"] for t in value["result"]["public_tool_schemas"]}
    for name, path in (("download","/ajax/download.php"),("progress","/api/progress")):
        props = schemas[name]["properties"]
        if props["_endpoint"].get("default") != path or props["_method"].get("default") != "GET":
            raise ProbeError("TOOL_ROUTE_CHANGED")
    props = schemas["download"]["properties"]
    if set(PARAMS)-set(props) or "1080" not in props["format"]["enum"]:
        raise ProbeError("DOWNLOAD_CONTRACT_CHANGED")
    return q


class OneStart:
    def __init__(self):
        self.attempts = 0

    def take(self):
        if self.attempts:
            raise ProbeError("DUPLICATE_START_REFUSED")
        self.attempts = 1


def media_url(value, resolver=socket.getaddrinfo):
    if not isinstance(value, str) or len(value)>8192:
        raise ProbeError("INVALID_DELIVERY_URL")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in (None,443) or parsed.fragment):
        raise ProbeError("UNSAFE_DELIVERY_URL")
    if parsed.hostname == HOST or parsed.hostname.endswith((".rapidapi.com", ".youtube.com", ".googlevideo.com")):
        raise ProbeError("EXPECTED_PROVIDER_DELIVERY_NOT_SOURCE_OR_API")
    addresses = resolver(parsed.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ProbeError("NONPUBLIC_DELIVERY_ADDRESS")
    return parsed.hostname


def unpack_mcp(result):
    if result.get("isError"):
        raise ProbeError("MCP_TOOL_EXECUTION_ERROR")
    if isinstance(result.get("structuredContent"), dict):
        return result["structuredContent"]
    content = result.get("content", [])
    texts = [c.get("text") for c in content if isinstance(c, dict) and c.get("type")=="text"]
    if len(texts)!=1 or not isinstance(texts[0], str):
        raise ProbeError("UNEXPECTED_TOOL_RESULT")
    value = json.loads(texts[0])
    if not isinstance(value, dict):
        raise ProbeError("INVALID_TOOL_BODY")
    return value


def start_download(client, guard, evidence, out):
    guard.take()
    evidence["download_tools_call_requests"] = guard.attempts
    evidence["effect_status"] = "START_ATTEMPTED_RESULT_NOT_YET_KNOWN"
    private_json(out/"receipt.json",evidence,client._key)
    print("HEROVERSE_NATIVE_EFFECT_BEGIN="+json.dumps({"request_id":REQUEST_ID,"started_at":utc_now()}),flush=True)
    req_id = client._next_id
    client._next_id += 1
    payload = {"jsonrpc":"2.0","id":req_id,"method":"tools/call","params":{"name":"download","arguments":PARAMS}}
    headers = {"Content-Type":"application/json","Accept":"application/json, text/event-stream",
        "x-api-host":HOST,"x-api-key":client._key,"MCP-Protocol-Version":client._protocol}
    if client._session:
        headers["Mcp-Session-Id"]=client._session
    req = Request(ENDPOINT,data=json.dumps(payload).encode(),headers=headers,method="POST")
    with build_opener(NoRedirect()).open(req,timeout=25) as response:
        if response.headers.get("Content-Type","").split(";",1)[0].strip()=="application/json":
            raw=response.read(1048577)
            if len(raw)>1048576: raise ProbeError("START_RESPONSE_TOO_LARGE")
            evidence["start_reply_received_bytes"]=len(raw)
            envelope=json.loads(raw)
            private_json(out/"start-rpc-response.json",envelope,client._key)
            if isinstance(envelope,dict) and isinstance(envelope.get("error"),dict):
                code=envelope["error"].get("code")
                if type(code) is int and -32768<=code<=-32000:
                    evidence["start_rpc_error_code"]=code
            raw_result=_validate_reply(envelope,req_id)
            if raw_result is None: raise ProbeError("START_REPLY_ID_MISMATCH")
        else:
            raw_result = read_reply(response,req_id,time.monotonic()+25)
        private_json(out/"start-result.json",raw_result,client._key)
        value = unpack_mcp(raw_result)
    private_json(out/"start-body.json",value,client._key)
    return value


def progress(job_id,key,evidence,out,index):
    req = Request("https://"+HOST+"/api/progress?"+urlencode({"id":job_id}),
        headers={"Accept":"application/json","x-rapidapi-host":HOST,"x-rapidapi-key":key})
    with build_opener(NoRedirect()).open(req,timeout=15) as response:
        q=quota_headers(response.headers)
        raw=response.read(MAX_CONTROL_BYTES+1)
        evidence["control_response_bytes"]+=len(raw)
        evidence["progress_polls"]+=1
        evidence["last_quota_headers"]=q
        evidence.setdefault("quota_observations",[]).append({"poll_index":index,
            "units_remaining":q.get("x-ratelimit-units-remaining"),
            "requests_remaining":q.get("x-ratelimit-requests-remaining")})
        if q.get("x-ratelimit-units-remaining","").isdigit():
            evidence["observed_units_change_since_info"]=int(evidence["baseline_quota_headers"]["x-ratelimit-units-remaining"])-int(q["x-ratelimit-units-remaining"])
        if len(raw)>MAX_CONTROL_BYTES:
            raise ProbeError("CONTROL_RESPONSE_TOO_LARGE")
        if int(q.get("x-ratelimit-units-remaining","0"))<0:
            raise ProbeError("INCLUDED_QUOTA_EXHAUSTED")
        value=json.loads(raw)
        private_json(out/("progress-%02d.json"%index),value,key)
        if not isinstance(value,dict):
            raise ProbeError("INVALID_PROGRESS_BODY")
        return value


def bounded_file(response,path,cap=MAX_MEDIA_BYTES):
    size=response.headers.get("Content-Length")
    if size and (not size.isdigit() or int(size)>cap):
        raise ProbeError("DELIVERY_EXCEEDS_BYTE_BUDGET")
    total=0
    digest=hashlib.sha256()
    with path.open("xb") as f:
        while True:
            chunk=response.read(min(65536,cap-total+1))
            if not chunk: break
            total+=len(chunk)
            if total>cap:
                raise ProbeError("DELIVERY_EXCEEDS_BYTE_BUDGET")
            f.write(chunk);digest.update(chunk)
    if total<16 or path.read_bytes()[:8][4:]!=b"ftyp":
        raise ProbeError("NOT_AN_MP4_FILE")
    return {"bytes":total,"sha256":digest.hexdigest()}


def fetch_media(url,out,evidence):
    host=media_url(url)
    class DeliveryRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            chain=evidence.setdefault("delivery_redirect_hosts",[])
            if len(chain)>=3:
                raise ProbeError("DELIVERY_REDIRECT_LIMIT")
            chain.append(media_url(newurl))
            return Request(newurl,headers={"Accept":"video/mp4, application/octet-stream"})
    # Separate opener and request: provider API key/session is never sent to CDN.
    with build_opener(DeliveryRedirect()).open(Request(url,headers={"Accept":"video/mp4, application/octet-stream"}),timeout=30) as response:
        evidence["delivery_http_status"]=response.status
        evidence["delivery_host"]=urlsplit(response.geturl()).hostname
        evidence["media_file"]=bounded_file(response,out/"native.mp4")


def command(args,timeout=120):
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if result.returncode or result.stderr.strip():
        raise ProbeError("NATIVE_MEDIA_COMMAND_FAILED")
    return result.stdout


def inspect_media(out,evidence):
    path=out/"native.mp4"
    data=json.loads(command(["ffprobe","-v","error","-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,duration,nb_read_frames",
        "-of","json",str(path)]))
    videos=[s for s in data.get("streams",[]) if s.get("codec_type")=="video"]
    audios=[s for s in data.get("streams",[]) if s.get("codec_type")=="audio"]
    if len(videos)!=1 or not audios:
        raise ProbeError("VIDEO_AND_AUDIO_STREAMS_REQUIRED")
    evidence["native_probe"]=data
    duration=float(data.get("format",{}).get("duration","0"))
    evidence["requested_duration_seconds"]=40
    evidence["technical_trim_tolerance_seconds"]=0.1
    if abs(duration-40)>0.1:
        raise ProbeError("RETURNED_DURATION_DOES_NOT_MATCH_REQUEST")
    if videos[0].get("height")!=1080:
        raise ProbeError("RETURNED_VIDEO_IS_NOT_REQUESTED_1080P")
    frames=json.loads(command(["ffprobe","-v","error","-count_frames","-select_streams","v:0",
        "-show_entries","stream=nb_read_frames","-of","json",str(path)]))
    evidence["decoded_video_frames"]=int(frames["streams"][0]["nb_read_frames"])
    command(["ffmpeg","-nostdin","-v","error","-i",str(path),"-map","0:v:0","-map","0:a:0","-f","null","-"])
    evidence["complete_clip_decode_passed"]=True
    for n in (0,10,20,30,39):
        command(["ffmpeg","-nostdin","-v","error","-ss",str(n),"-i",str(path),"-frames:v","1","-q:v","2",str(out/("frame-%02d.jpg"%n))])
    command(["ffmpeg","-nostdin","-v","error","-i",str(path),"-map","0:a:0","-c:a","copy",str(out/"audio.mka")])
    command(["ffmpeg","-nostdin","-v","error","-i",str(path),"-map","0:a:0","-c:a","pcm_s16le",str(out/"audio-review.wav")])
    if any(not (out/("frame-%02d.jpg"%n)).is_file() for n in (0,10,20,30,39)):
        raise ProbeError("REQUESTED_REVIEW_FRAME_MISSING")
    evidence["status"]="NATIVE_CLIP_RECEIVED_AND_DECODED_AWAITING_PERCEPTUAL_REVIEW"
    evidence["perceptual_video_review_completed"]=False
    evidence["perceptual_audio_review_completed"]=False
    evidence["recurring_capacity_qualified"]=False


def run(out,evidence,key,baseline):
    evidence["baseline_quota_headers"]=validate_preflight(baseline,dt.datetime.now(dt.timezone.utc))
    if os.environ.get("GITHUB_RUN_NUMBER")!=EXPECTED_RUN_NUMBER or os.environ.get("GITHUB_RUN_ATTEMPT")!="1":
        raise ProbeError("REPEAT_OR_RERUN_OF_FIXED_REQUEST_REFUSED")
    previous=json.loads((Path(__file__).resolve().parents[2]/"evidence/cloud-video-player-20261015/rapidapi-native-no-effect-38741186634.json").read_text())["result"]
    if (previous.get("download_tools_call_requests")!=0 or previous.get("effect_status")!="NOT_SENT"
            or previous.get("failure_code")!="NATIVE_DECODER_UNAVAILABLE"):
        raise ProbeError("PRIOR_ZERO_EFFECT_NOT_PROVEN")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ProbeError("NATIVE_DECODER_UNAVAILABLE")
    client=Client(key)
    client.send("initialize",{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"heroverse-native-av-one-start","version":"0.1.0"}})
    client.send("notifications/initialized")
    evidence["source_requested_seconds"]=[0,40]
    evidence["control_response_bytes"]=0
    value=start_download(client,OneStart(),evidence,out)
    evidence["start_body_keys"]=[k for k in value if re.fullmatch(r"[a-zA-Z0-9_]{1,60}",k)]
    job_id=value.get("id")
    if not isinstance(job_id,str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,160}",job_id):
        raise ProbeError("START_RESPONSE_HAS_NO_RESUMABLE_JOB_ID")
    if key and key in job_id:
        raise ProbeError("UNSAFE_REFLECTED_CREDENTIAL_IN_JOB_ID")
    evidence["provider_job_id"]=job_id
    evidence["provider_job_id_sha256"]=hashlib.sha256(job_id.encode()).hexdigest()
    evidence["effect_status"]="JOB_ID_RECEIVED_NO_RESTART_ALLOWED"
    private_json(out/"job.json",{"request_id":REQUEST_ID,"provider_job_id":job_id,"parameters":PARAMS},key)
    private_json(out/"receipt.json",evidence,key)
    print("HEROVERSE_NATIVE_JOB_SAVED="+json.dumps({"request_id":REQUEST_ID,"provider_job_id":job_id,"provider_job_id_sha256":evidence["provider_job_id_sha256"]}),flush=True)
    poll_deadline=time.monotonic()+270
    for index in range(MAX_POLLS):
        if time.monotonic()>poll_deadline:
            raise ProbeError("JOB_STILL_PENDING_RESUME_EXISTING_ID_ONLY")
        if index: time.sleep(10)
        value=progress(job_id,key,evidence,out,index)
        url=value.get("download_url") or value.get("downloadUrl") or value.get("file_url")
        if url:
            evidence["delivery_url_sha256"]=hashlib.sha256(url.encode()).hexdigest()
            fetch_media(url,out,evidence)
            inspect_media(out,evidence)
            return
        if value.get("status") in ("error","failed","FAILED") or value.get("error"):
            raise ProbeError("PROVIDER_JOB_FAILED_STOP_NO_RESTART")
    raise ProbeError("JOB_STILL_PENDING_RESUME_EXISTING_ID_ONLY")


def main():
    out=Path("output/qualification/rapidapi-native-j2rk8ycXe3c-0-40-v1")
    out.mkdir(parents=True,exist_ok=True)
    key=os.environ.get("HERO_RAPIDAPI_KEY","")
    evidence={"version":"heroverse-native-av-one-start-v1","request_id":REQUEST_ID,"started_at":utc_now(),
        "status":"BLOCKED","effect_status":"NOT_SENT","download_tools_call_requests":0,"progress_polls":0,
        "production":False,"publication":False,"supervisor":False,"recurring_capacity_qualified":False}
    started=time.monotonic()
    try:
        baseline=json.loads((Path(__file__).resolve().parents[2]/"evidence/cloud-video-player-20261015/rapidapi-native-quota-preflight.json").read_text())
        run(out,evidence,key,baseline)
    except HTTPError as error:
        evidence["failure_code"]="HTTP_"+str(error.code)
        evidence["last_http_error_quota_headers"]=quota_headers(error.headers)
        private_json(out/"http-error.json",{"status":error.code,"body":error.read(MAX_CONTROL_BYTES).decode("utf-8",errors="replace")},key)
    except (URLError,TimeoutError,socket.timeout):
        evidence["failure_code"]="TRANSPORT_UNAVAILABLE_OR_TIMEOUT_NO_RESTART"
    except ProbeError as error:
        evidence["failure_code"]=str(error)
    except (ValueError,UnicodeError,TypeError,AttributeError,KeyError,FileNotFoundError):
        evidence["failure_code"]="INVALID_OR_MISSING_REQUIRED_RESPONSE"
    except subprocess.TimeoutExpired:
        evidence["failure_code"]="NATIVE_INSPECTION_DEADLINE"
    evidence["elapsed_seconds"]=round(time.monotonic()-started,3)
    evidence["completed_at"]=utc_now()
    private_json(out/"receipt.json",evidence,key)
    text=json.dumps(evidence,separators=(",",":"))
    if key: text=text.replace(key,"[REDACTED]")
    print("HEROVERSE_NATIVE_AV_RECEIPT="+text,flush=True)
    return 0 if evidence["status"]=="NATIVE_CLIP_RECEIVED_AND_DECODED_AWAITING_PERCEPTUAL_REVIEW" else 2


if __name__=="__main__": raise SystemExit(main())
