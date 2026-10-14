"""Sanitized observations from the existing refresh, never Cloud Console claims."""
from datetime import datetime,timezone
from verify_worker_oauth import check_token

def record(status,failure_code=None):
    return {'version':'heroverse-existing-grant-health-v1','observed_at':datetime.now(timezone.utc).isoformat(),
        'status':status,'failure_code':failure_code,'console_publishing_status':'UNOBSERVED',
        'configuration_verified':False,'production_ready':False,'publication_authorized':False,
        'secret_values_logged':False,'new_consent_performed':False,'automatic_retry_performed':False}

def observe_refresh(raw,renew):
    failure=check_token(raw)
    if failure:return None,record('CONFIGURATION_BLOCKED',failure)
    try:
        credentials=renew(raw)
    except Exception as error:
        # Read only a stable OAuth code, never serialize arbitrary exception text.
        code=None
        for item in getattr(error,'args',()):
            if isinstance(item,dict) and item.get('error') in {'invalid_grant','invalid_client','temporarily_unavailable','server_error'}:
                code=item['error'];break
        if code in {'invalid_grant','invalid_client'}:
            return None,record('AUTHORIZATION_ACTION_REQUIRED',code.upper())
        return None,record('REFRESH_UNAVAILABLE','TRANSIENT_OR_UNCLASSIFIED_REFRESH_FAILURE')
    return credentials,record('REFRESH_PASSED_IDENTITY_NOT_YET_OBSERVED')

def identity_health(refresh,channel_id,expected):
    if refresh['status']!='REFRESH_PASSED_IDENTITY_NOT_YET_OBSERVED' or channel_id!=expected:
        raise PermissionError('AUTH_HEALTH_IDENTITY_MISMATCH')
    result=record('REFRESH_AND_EXACT_CHANNEL_PASSED');result['channel_id']=channel_id
    result['refresh_observed_at']=refresh['observed_at']
    return result

def validate_health(value):
    required=set(record('CONFIGURATION_BLOCKED'))
    allowed=required|{'channel_id','refresh_observed_at'}
    statuses={'CONFIGURATION_BLOCKED','AUTHORIZATION_ACTION_REQUIRED','REFRESH_UNAVAILABLE',
        'REFRESH_PASSED_IDENTITY_NOT_YET_OBSERVED','REFRESH_AND_EXACT_CHANNEL_PASSED'}
    if (not isinstance(value,dict) or not required<=set(value)<=allowed
            or value['version']!='heroverse-existing-grant-health-v1' or value['status'] not in statuses
            or value['console_publishing_status']!='UNOBSERVED'
            or any(value[k] is not False for k in ['configuration_verified','production_ready',
                'publication_authorized','secret_values_logged','new_consent_performed','automatic_retry_performed'])):
        raise ValueError('AUTH_HEALTH_CONTRACT_INVALID')
    codes={'CLOUD_TOKEN_NOT_PROVISIONED','INVALID_TOKEN_JSON','AUTHORIZED_USER_REQUIRED',
        'EXISTING_CLIENT_ID_MISMATCH','UNAPPROVED_TOKEN_ENDPOINT','INCOMPLETE_AUTHORIZED_USER_TOKEN',
        'REQUIRED_SCOPES_MISSING','INVALID_GRANT','INVALID_CLIENT','TRANSIENT_OR_UNCLASSIFIED_REFRESH_FAILURE'}
    if value['failure_code'] is not None and value['failure_code'] not in codes:
        raise ValueError('AUTH_HEALTH_CODE_INVALID')
    if datetime.fromisoformat(value['observed_at']).tzinfo is None:raise ValueError('AUTH_HEALTH_TIME_INVALID')
    if value['status']=='REFRESH_AND_EXACT_CHANNEL_PASSED' and value.get('channel_id')!='UCuMF6pJQkyMzaVoAxFL86yA':
        raise ValueError('AUTH_HEALTH_CHANNEL_INVALID')
    return value
