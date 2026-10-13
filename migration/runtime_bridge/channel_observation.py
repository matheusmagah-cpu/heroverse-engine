"""Merge observed Studio evidence without promoting editorial or publication gates."""
from copy import deepcopy

CHANNEL = 'UCuMF6pJQkyMzaVoAxFL86yA'
REF = 'migration/evidence/20261013-studio-configuration-observation.json'

def reconcile(audit, observation):
    if audit['channel_id'] != CHANNEL or observation['channel_id'] != CHANNEL:
        raise PermissionError('STUDIO_CHANNEL_IDENTITY_MISMATCH')
    if observation['content_coherence']['status'] != 'BLOCKED':
        raise PermissionError('NEW_EDITORIAL_APPROVAL_REQUIRED')
    result = deepcopy(audit)
    profile = observation['profile']
    if not (profile['description_full_observed'] and profile['banner_present'] and profile['avatar_present']):
        raise PermissionError('INCOMPLETE_PROFILE_OBSERVATION')
    if not observation['upload_defaults']['persistence_verified_by_reopened_dialog']:
        raise PermissionError('UPLOAD_DEFAULT_SAVE_UNVERIFIED')
    for gate in result['gates']:
        if gate['gate'] in ['BRAND_MESSAGE_ALIGNMENT', 'PROFILE_CONVERSION_ASSETS']:
            gate.update(status='PASS', evidence=[REF], required_action=None)
        elif gate['gate'] in ['POSITIONING_COHERENCE', 'PROMISE_INTEGRITY']:
            gate.update(status='BLOCKED', evidence=[REF, observation['content_coherence']['evidence_ref']], required_action='Approve a complete coherent production; preserve existing published history.')
        elif gate['gate'] == 'HOME_CONVERSION_ARCHITECTURE':
            gate.update(status='NEEDS_REVIEW', evidence=[REF], required_action='Review playlist content and coherent series before optimizing the home layout.')
        elif gate['gate'] == 'YPP_ELIGIBILITY_PROGRESS':
            gate.update(status='NEEDS_REVIEW', evidence=[REF], required_action='Continue qualified audience growth; observed counters are dated and insufficient.')
    ypp = observation['ypp']
    result['measurements'].update(qualified_ypp_watch_hours=ypp['qualified_watch_hours_365days'], brand_keyword_observation=observation['channel_settings']['keywords'])
    result['measurements']['qualified_ypp_data_as_of'] = ypp['data_as_of']
    result['measurements']['qualified_shorts_views_90days'] = ypp['qualified_shorts_views_90days']
    result['publication_gate']['critical_open_gates'] = [g['gate'] for g in result['gates'] if g['critical'] and g['status'] != 'PASS']
    result['publication_gate']['reason'] = 'Current profile observed; confirmed editorial coherence remains blocked.'
    result['ypp_application_gate'].update(critical_open_gates=['QUALIFIED_YPP_THRESHOLDS_NOT_MET_AS_OF_2026_10_08'], reason='Studio counters observed with processing delay; eligibility thresholds not met in that snapshot.')
    result['priority_actions'] = [{'priority':i+1,'action':a,'protected_external_change':False} for i,a in enumerate(['Resolve observed content coherence','Complete audiovisual market review','Qualify full production and replay','Observe Google Auth production settings and actual quota usage'])]
    result['limitations'].append('Studio qualified counters are as of 2026-10-08, not current Analytics watch time. Upload UI defaults do not configure the API publisher.')
    return result
