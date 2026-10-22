"""Admission guard only; never manufacture an audience forecast or calibration."""
def require_prediction_basis(snapshot, outcomes):
    if not isinstance(snapshot, dict):
        raise PermissionError('PREDICTION_FEATURE_SOURCE_REQUIRED')
    # The frozen v1 emitter writes this exact cohort. It cannot honestly emit
    # records for rest music/Shorts or a missing/unknown family.
    expected = {'content_format': 'LONG', 'quality_profile': 'STANDARD',
                'format_pack_id': 'fp-broll-cinematic-narration',
                'format_pack_version': '1.1.0'}
    if any(snapshot.get(key) != value for key, value in expected.items()):
        raise PermissionError('PREDICTION_COHORT_PROVENANCE_MISSING_OR_INCOMPATIBLE')
    # The old API accepts naked numbers. Neither identities, original windows,
    # traffic scope nor out-of-sample evaluation can be reconstructed from
    # those numbers. No number of them proves calibration.
    if outcomes is not None and (type(outcomes) is not list or outcomes):
        raise PermissionError('PREDICTION_OUTCOME_PROVENANCE_AND_CALIBRATION_REQUIRED')
    return {'status': 'WITHHELD_BASIS_ONLY_NO_CALIBRATED_FORECAST',
            'quality_authorized': False, 'publication_authorized': False}
