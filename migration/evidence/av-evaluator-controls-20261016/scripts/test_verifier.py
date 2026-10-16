#!/usr/bin/env python3
"""Known-bad substitutions must be rejected. Offline, temporary copies only."""
import json
import shutil
import tempfile
from pathlib import Path
import build_and_verify as av

root=Path(__file__).resolve().parents[1]
cases=[
    ('silence_replaced_by_tone','c03.mp4','c04.mp4','pulse count'),
    ('lag_replaced_by_alignment','c01.mp4','c04.mp4','onset'),
    ('constant_replaced_by_flashes','c02.mp4','c04.mp4','supposedly constant image changed'),
]
results=[]
for label,target,replacement,expected_message in cases:
    with tempfile.TemporaryDirectory(prefix='av_negative_') as temp:
        copied=Path(temp)
        shutil.copytree(root/'stimuli',copied/'stimuli')
        shutil.copyfile(root/'stimuli'/replacement,copied/'stimuli'/target)
        try:
            av.analyze(copied,{})
        except AssertionError as error:
            message=str(error)
            av.require(expected_message in message,f'Wrong rejection for {label}: {message}')
            results.append({'case':label,'rejected':True,'reason':message})
        else:
            raise AssertionError(f'Bad input was accepted: {label}')
result={'all_negative_tests_passed':True,'tests':results}
av.dump(root/'operator-only'/'negative-tests.json',result)
print(json.dumps(result,indent=2))
