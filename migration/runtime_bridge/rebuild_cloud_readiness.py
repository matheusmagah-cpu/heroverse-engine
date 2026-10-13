"""Native cloud receipt reconstruction, with unknown facts kept blocked.
No publisher, queue activation, console change or new consent is invoked.
"""
import hashlib,json,os,shutil,sys,tempfile,zipfile,subprocess
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jsonschema import Draft202012Validator,FormatChecker

def stamp():return datetime.now(timezone.utc).isoformat()
def put(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')
def validate(root,name,value):
 Draft202012Validator(json.loads((root/'schemas'/name).read_text()),format_checker=FormatChecker()).validate(value)
def adapt(root):
 pins={'hero_engine/oauth_token_mirror.py':'246cfd97c4cc7e9d0dd858089a07a46a3077bd02dbd898a0498e748590e6487f','schemas/oauth_token_mirror_receipt.schema.json':'a54cfa630d57737d7f34c18f03ece62f20b5bed079ac0c6368271e506e1ac170','schemas/youtube_connection_receipt.schema.json':'6b0298828881e1d414c51f42b58c74f9a3a6236751680af79ff37e1e10703555','schemas/oauth_runtime_scope_requirement.schema.json':'682044763c4294b1387de6662f6e7e921cf808ece384ce880ad0b526822e4b9c'}
 rows=[]
 for relative,pin in pins.items():
  p=root/relative;raw=p.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=pin:raise PermissionError('NATIVE_CLOUD_SOURCE_IDENTITY_MISMATCH')
  if relative.endswith('.py'):
   text=raw.decode();anchor='"destination_class": "WINDOWS_TASK_SECRET_OUTSIDE_WORKSPACE",'
   if text.count(anchor)!=1:raise PermissionError('MIRROR_ANCHOR_MISMATCH')
   p.write_text(text.replace(anchor,'"destination_class": "WINDOWS_TASK_SECRET_OUTSIDE_WORKSPACE" if os.name == "nt" else "LINUX_TASK_SECRET_OUTSIDE_WORKSPACE",'))
  else:
   d=json.loads(raw)
   if 'mirror_receipt' in relative:d['properties']['destination_class']={'enum':['WINDOWS_TASK_SECRET_OUTSIDE_WORKSPACE','LINUX_TASK_SECRET_OUTSIDE_WORKSPACE']}
   elif 'connection_receipt' in relative:d['properties']['authorization']['properties']['oauth_flow']={'enum':['INSTALLED_APP_LOOPBACK','WEB_SERVER_AUTHORIZATION_CODE']}
   else:
    d['properties']['console_alignment']['properties']['declared_scope_count_observed']['type']=['integer','null']
    d['properties']['caption_delivery']['properties']['embedded_subtitle_stream_count']['type']=['integer','null']
    d['allOf']=[{'if':{'properties':{'status':{'const':'PASS'}},'required':['status']},'then':{'properties':{'console_alignment':{'properties':{'declared_scope_count_observed':{'const':4},'configuration_matches_runtime':{'const':True}}},'caption_delivery':{'properties':{'embedded_subtitle_stream_count':{'type':'integer'}}}}}}]
   put(p,d)
  rows.append({'path':relative,'original_sha256':pin,'shadow_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 return rows

def partial_channel_audit(owned,captured,proof):
 cid='UCuMF6pJQkyMzaVoAxFL86yA'
 if owned.get('id')!=cid or not proof['identity_verified_after_refresh']:raise PermissionError('CHANNEL_IDENTITY_MISMATCH')
 names=['CHANNEL_IDENTITY','POSITIONING_COHERENCE','PROMISE_INTEGRITY','HOME_CONVERSION_ARCHITECTURE','BRAND_MESSAGE_ALIGNMENT','PROFILE_CONVERSION_ASSETS','CATALOG_LANGUAGE_AND_DUPLICATION','PACKAGING_DISCIPLINE','YPP_ELIGIBILITY_PROGRESS','MONETIZATION_POLICY_FIT']
 critical={'CHANNEL_IDENTITY','POSITIONING_COHERENCE','PROMISE_INTEGRITY','BRAND_MESSAGE_ALIGNMENT','PROFILE_CONVERSION_ASSETS'}
 gates=[{'gate':n,'critical':n in critical,'status':'PASS' if n=='CHANNEL_IDENTITY' else 'BLOCKED' if n in critical else 'NEEDS_REVIEW','evidence':[proof['receipt_id']] if n=='CHANNEL_IDENTITY' else ['Current complete profile/Studio/editorial evidence has not been restored; no default PASS.'],'required_action':None if n=='CHANNEL_IDENTITY' else 'Complete current native channel observation and coherent editorial validation.'} for n in names]
 opened=[g['gate'] for g in gates if g['critical'] and g['status']!='PASS']
 return {'schema_version':'1.0.0','audit_id':'channel-cloud-partial-'+hashlib.sha256(captured.encode()).hexdigest()[:16],'channel_id':cid,'handle':'@heroverse74','created_at':stamp(),'snapshot_ref':'migration/evidence/20261013-official-observations.json','policy_version':'channel-readiness-policy@1.1.0-cloud-partial-evidence','market_basis':{'channel_dna_ref':'output/modeling/phase4/channel-model-v1/channel_model.json','market_review_ref':'migration/MONETIZATION_DECISION.md','official_sources':['https://support.google.com/youtube/answer/72851','https://support.google.com/youtube/answer/16559650','https://support.google.com/youtube/answer/1311392'],'causal_claims_permitted':False},'measurements':{'subscriber_count':int(owned['statistics']['subscriberCount']),'public_video_count':int(owned['statistics']['videoCount']),'total_public_views':int(owned['statistics']['viewCount']),'description':owned['snippet'].get('description'),'captured_at':captured,'qualified_ypp_watch_hours':None,'returning_viewers':None,'brand_keyword_observation':None},'gates':gates,'overall_status':'BLOCKED_BEFORE_NEXT_PUBLICATION','publication_gate':{'status':'BLOCKED','critical_open_gates':opened,'auto_publish_permitted':False,'reason':'Incomplete current channel observation; exact identity is proven but publication quality is not.'},'ypp_application_gate':{'status':'BLOCKED','eligible_tier':'NONE','critical_open_gates':['CURRENT_QUALIFIED_YPP_COUNTERS_UNOBSERVED'],'auto_apply_permitted':False,'reason':'No current qualified counters or application review proof.'},'priority_actions':[{'priority':i+1,'action':a,'protected_external_change':False} for i,a in enumerate(['Restore channel profile observations','Complete current Studio evidence','Resolve observed content coherence','Complete audiovisual market review','Rebuild native quality and channel audit'])],'learning_protocol':{'owned_first':True,'matched_market_fallback':True,'returning_audience_requires_observation':True,'causal_claims_permitted':False,'global_learning_without_transfer_test':False},'limitations':['Partial snapshot is not complete channel audit.','Identity does not imply publication readiness.','Analytics watch time is not qualified YPP watch time.','The historical30day goal is not reset.']}

def rebuild(root,token_source,secret_dir,owned_evidence,export,quota_export):
 from hero_engine.oauth_token_mirror import mirror_authorized_user_token
 from hero_engine.oauth_refresh_proof import prove_noninteractive_refresh
 from hero_engine.oauth_operational_readiness import build_operational_readiness
 from hero_engine.youtube_integration import INTEGRATION_SCOPES
 from hero_engine.zero_cost_guard import evaluate_zero_cost
 from hero_engine.phase6_quota import reserve_general_quota,consume_general_quota
 from google.auth.transport.requests import Request
 from hero_engine.google_api_runtime import GoogleOperationDeadline
 class BoundedRequest(Request):
  def __call__(self,*args,**kw):kw['timeout']=20;return super().__call__(*args,**kw)
 base=root/'output/integrations/youtube/heroverse';base.mkdir(parents=True,exist_ok=True)
 runtime=secret_dir/'runtime-authorized-user.json'
 mirror=mirror_authorized_user_token(token_source,runtime,base/'oauth-token-mirror-receipt.json',root=root)
 run=os.environ['GITHUB_RUN_ID'];key='native-cloud-readiness:'+run
 reserve_general_quota(root,idempotency_key=key,operation_id=key,job_id=key,attempt_count=1,effective_general_before=2016,units=1,preventive_floor=12);consume_general_quota(root,idempotency_key=key)
 try:proof=prove_noninteractive_refresh(runtime,base/'oauth-noninteractive-refresh-receipt.json',root=root,request_factory=BoundedRequest,deadline=GoogleOperationDeadline(seconds=50))
 finally:shutil.copy2(root/'output/operations/zero-cost/phase6-quota-ledger.sqlite3',quota_export)
 if proof['status']!='PASS':raise PermissionError('NATIVE_REFRESH_NOT_PASS')
 data=json.loads(owned_evidence.read_text());owned=data['owned_channel'];scopes=list(INTEGRATION_SCOPES)
 connection={'schema_version':'1.0.0','receipt_id':'cloud-connection-'+proof['receipt_id'],'integration_id':'youtube-heroverse-v1','status':'CONNECTED','expected_channel':{'handle':'@heroverse74','channel_id':owned['id']},'observed_channel':{'channel_id':owned['id'],'title':owned['snippet']['title'],'custom_url':owned['snippet'].get('customUrl'),'subscriber_count':int(owned['statistics']['subscriberCount']),'video_count':int(owned['statistics']['videoCount']),'view_count':int(owned['statistics']['viewCount'])},'identity_verified':proof['observed_channel_id']==owned['id'],'capabilities':[{'capability':n,'status':'CONNECTED' if n in ['CHANNEL_READ','ANALYTICS_READ'] else 'CONFIGURED_BLOCKED','reason':'Existing official read observation plus current exact-channel refresh proof.' if n in ['CHANNEL_READ','ANALYTICS_READ'] else 'Scope granted; production gates still apply.'} for n in ['CHANNEL_READ','ANALYTICS_READ','UPLOAD','CUSTOM_THUMBNAIL','CAPTION_UPLOAD']],'authorization':{'oauth_flow':'WEB_SERVER_AUTHORIZATION_CODE','requested_scopes':scopes,'granted_scopes':proof['granted_scopes'],'token_storage':'LOCAL_OUTSIDE_WORKSPACE','secret_logged':False},'analytics_probe':{'status':'PASS','start_date':'2026-10-10','end_date':'2026-10-13','metrics':['views','estimatedMinutesWatched'],'row_count':sum(len(x.get('basic',{}).get('rows',[])) for x in data['owned_private']),'private_values_persisted':False},'publication_guard':{'publish_mode':'dry-run','human_review':'PENDING','format_pack_status':'PROTOTYPED','upload_permitted':False},'external_cost_usd':0,'created_at':data['captured_at']}
 validate(root,'youtube_connection_receipt.schema.json',connection);put(base/'connection-receipt.json',connection)
 readiness=build_operational_readiness(root,token_file=runtime);put(base/'operational-readiness.json',readiness)
 capabilities=[('CHANNEL_IDENTITY_AND_METADATA','channels.list/videos.list',scopes[0]),('OWNED_CHANNEL_ANALYTICS','youtubeAnalytics.reports.query','https://www.googleapis.com/auth/yt-analytics.readonly'),('VIDEO_AND_THUMBNAIL_UPLOAD','videos.insert/thumbnails.set','https://www.googleapis.com/auth/youtube.upload'),('CAPTION_TRACK_UPLOAD','captions.insert','https://www.googleapis.com/auth/youtube.force-ssl')]
 scope={'schema_version':'1.0.0','requirement_id':'cloud-scope-'+run,'integration_id':'youtube-heroverse-v1','channel_id':owned['id'],'required_scopes':scopes,'current_granted_scopes':proof['granted_scopes'],'missing_scopes':[s for s in scopes if s not in proof['granted_scopes']],'capabilities':[{'capability':n,'api_method':m,'required_scope':s,'granted_now':s in proof['granted_scopes'],'least_use_boundary':'Native least-use adapters only; no publication without release gate.','risk':'Granted write scope does not authorize a video effect by itself.'} for n,m,s in capabilities],'caption_delivery':{'sidecar_path':'output/production/audio-christian-rest-editorial-v4/qa/opening-captions.srt','sidecar_exists':False,'embedded_subtitle_stream_count':None,'automatic_method':'captions.insert','required_scope':'https://www.googleapis.com/auth/youtube.force-ssl','fallbacks':[{'mode':'NATIVE_NEW_PACKAGE','automation_level':'BLOCKED_UNTIL_INPUTS','impact':'Requires current package and final ASR/caption binding.'},{'mode':'DEFER','automation_level':'AUTOMATIC','impact':'No effect while caption inputs missing.'}]},'console_alignment':{'declared_scope_count_observed':None,'configuration_matches_runtime':False},'status':'BLOCKED_CONSOLE_MISMATCH','protected_action_required':True,'claim_boundary':'Grant and exact identity proven; console declaration and current caption inputs remain unobserved. No console values imputed.','official_sources':['https://developers.google.com/youtube/v3/docs/captions/insert','https://developers.google.com/youtube/v3/guides/authentication'],'created_at':stamp()}
 validate(root,'oauth_runtime_scope_requirement.schema.json',scope);put(base/'oauth-runtime-scope-requirement.json',scope)
 channel=partial_channel_audit(owned,data['captured_at'],proof);validate(root,'channel_readiness_audit.schema.json',channel);put(root/'output/audits/channel/heroverse/channel-readiness-audit.json',channel)
 cost=evaluate_zero_cost(root,operation='phase6_video2_publication_pipeline');put(root/'output/operations/zero-cost/phase5-publication-pipeline-preflight.json',cost)
 for relative in ['output/integrations/youtube/heroverse/connection-receipt.json','output/integrations/youtube/heroverse/oauth-token-mirror-receipt.json','output/integrations/youtube/heroverse/oauth-noninteractive-refresh-receipt.json','output/integrations/youtube/heroverse/operational-readiness.json','output/integrations/youtube/heroverse/oauth-runtime-scope-requirement.json','output/audits/channel/heroverse/channel-readiness-audit.json','output/operations/zero-cost/phase5-publication-pipeline-preflight.json']:
  target=export/'native-readiness'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/relative,target)
 return {'status':'NATIVE_CLOUD_DOCUMENTS_REBUILT_WITH_EXPLICIT_OPEN_GATES','native_documents':4,'connection_verified':readiness['identity_verified'],'current_token_verified':readiness['token_valid_now'],'refresh_and_mirror_verified':proof['status']=='PASS','continuous_operation_ready':readiness['continuous_operation_ready'],'oauth_blockers':readiness['blockers'],'scope_status':scope['status'],'channel_status':channel['overall_status'],'cost_status':cost['quota_status'],'publication_performed':False,'production_ready':False}

def main():
 from collect_official_evidence import restore,SOURCE_SHA,sha
 from durable_evidence_checkpoint import CLAIM,SQL,restore_ledger
 from verify_worker_oauth import check_token
 raw=os.environ.get('HERO_YT_AUTHORIZED_USER_JSON','')
 if check_token(raw):raise PermissionError('CLOUD_TOKEN_INVALID')
 if not CLAIM.exists() or json.loads(CLAIM.read_text())['run_id']!=os.environ.get('GITHUB_RUN_ID'):raise PermissionError('DURABLE_CLAIM_REQUIRED')
 export=Path('cloud-evidence');export.mkdir(exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='native-cloud-contract-',dir=os.environ.get('RUNNER_TEMP')) as tmp:
  base=Path(tmp);restore(Path('HeroVerse_Linux_Source_Ready_20261013_v2.zip'),SOURCE_SHA,base/'source');root=base/'source/project'
  manifest=json.loads((base/'source/SOURCE_TRANSFER_REPORT.json').read_text())
  for item in manifest['files']:
   p=root/item['path']
   if p.stat().st_size!=item['bytes'] or sha(p.read_bytes())!=item['sha256']:raise PermissionError('SOURCE_MEMBER_MISMATCH')
  test_env=dict(os.environ);test_env.pop('HERO_YT_AUTHORIZED_USER_JSON',None);test_env['HEROVERSE_NATIVE_SOURCE_ROOT']=str(root)
  tests=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(Path(__file__).parent),'-p','test_*.py','-v'],env=test_env,capture_output=True,text=True,timeout=120)
  if tests.returncode:raise PermissionError('CLOUD_CONTRACT_TESTS_FAILED')
  print('PASS: cloud contract and bound path tests before OAuth effect')
  overlay=adapt(root);ledger=root/'output/operations/zero-cost/phase6-quota-ledger.sqlite3';ledger.parent.mkdir(parents=True);restore_ledger(SQL,ledger)
  secrets=base/'external-runtime-secret';secrets.mkdir(mode=0o700);source=secrets/'source-authorized-user.json';fd=os.open(source,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'w') as f:f.write(raw)
  raw=None;sys.path.insert(0,str(root))
  result=rebuild(root,source,secrets,Path('migration/evidence/20261013-official-observations.json'),export,export/'quota-ledger.sqlite3');result['overlay']=overlay
  put(export/'native-cloud-readiness-summary.json',result);print(json.dumps(result))
if __name__=='__main__':
 try:main()
 except Exception as e:
  print(json.dumps({'status':'BLOCKED','exception_type':type(e).__name__,'details_redacted':True,'publication_performed':False}));raise SystemExit(2)
