#!/usr/bin/env python3
"""Derive contiguous scene frames and sentence-aligned Shorts from real voice.

Usage: timing.py TIMELINE SCENES OUT_DIR
Leading silence belongs to S01; inter-segment pauses belong to the preceding
scene. End-exclusive frames use Python round(seconds * fps). The only optional
trim defined by the current scene plan is short2/S14 to its last sentence.
No narration is stretched or silently removed to force a duration pass.
"""
import json
import math
from pathlib import Path
import sys


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("INVALID_TIME")
    return value


def build(timeline, scenes, criteria):
    fps = criteria['master']['fps']
    if scenes['master']['fps'] != fps:
        raise ValueError('FPS_MISMATCH')
    planned = scenes['scenes']
    segments = timeline['segments']
    ids = [s['id'] for s in planned]
    if not ids or ids[0] != 'S01' or len(set(ids)) != len(ids) or [s['id'] for s in segments] != ids:
        raise ValueError('SCENE_SEGMENTS_MISMATCH')
    end = number(timeline['voice_seconds'])
    previous = 0
    sentences = timeline['sentences']
    grouped = {key: [] for key in ids}
    segment_map = {s['id']: s for s in segments}
    for s in segments:
        start, stop = number(s['start']), number(s['end'])
        if start < previous or stop <= start or stop > end:
            raise ValueError('INVALID_SEGMENT_RANGE')
        previous = stop
    previous = 0
    for sentence in sentences:
        key = sentence['segment']
        start, stop = number(sentence['start']), number(sentence['end'])
        if key not in grouped or start < previous or stop <= start or not isinstance(sentence['text'], str) or not sentence['text'].strip():
            raise ValueError('INVALID_SENTENCE')
        segment = segment_map[key]
        if start < segment['start'] or stop > segment['end']:
            raise ValueError('SENTENCE_OUTSIDE_SEGMENT')
        grouped[key].append(sentence)
        previous = stop
    if any(not grouped[key] for key in ids):
        raise ValueError('MISSING_SCENE_SENTENCES')
    result = {'fps': fps, 'frames_total': round(end * fps), 'scenes': []}
    for i, scene in enumerate(planned):
        start = 0 if i == 0 else segments[i]['start']
        stop = segments[i+1]['start'] if i+1 < len(planned) else end
        first, last = round(start * fps), round(stop * fps)
        if last <= first:
            raise ValueError('EMPTY_SCENE_FRAMES')
        result['scenes'].append({'id': scene['id'], 'start_s': start, 'end_s': stop,
                                 'first_frame': first, 'end_frame': last})
    shorts = {}
    for name, limits in criteria['shorts']['duration_seconds'].items():
        plan = scenes['shorts'][name]
        selected = plan['scenes']
        if len(selected) != len(set(selected)) or any(s not in grouped for s in selected):
            raise ValueError('INVALID_SHORT_SCENES')
        if selected[-1] != ids[-1]:
            raise ValueError('SHORT_CTA_MISSING')
        spans = [{'scene': key, 'master_start_s': grouped[key][0]['start'],
                  'master_end_s': grouped[key][-1]['end']} for key in selected]
        total = sum(s['master_end_s'] - s['master_start_s'] for s in spans)
        if total > limits[1] and name == 'short2' and 'S14' in selected and 'S14 trimmed to its last sentence if needed to fit' in plan.get('note', ''):
            span = spans[selected.index('S14')]
            span['master_start_s'] = grouped['S14'][-1]['start']
            total = sum(s['master_end_s'] - s['master_start_s'] for s in spans)
        total = round(total, 6)
        if not limits[0] <= total <= limits[1]:
            raise ValueError(f'SHORT_DURATION {name} {total:g}')
        shorts[name] = {'spans': spans, 'total_s': total}
    return result, shorts


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        print('usage: timing.py TIMELINE SCENES OUT_DIR', file=sys.stderr)
        return 1
    try:
        timeline = json.loads(Path(argv[0]).read_text())
        scenes = json.loads(Path(argv[1]).read_text())
        criteria = json.loads(Path(__file__).with_name('qa_criteria_animation_v1.json').read_text())
        timing, shorts = build(timeline, scenes, criteria)
        out = Path(argv[2])
        out.mkdir(parents=True, exist_ok=True)
        for name, data in [('timing.json', timing), ('shorts-map.json', shorts)]:
            (out / name).write_text(json.dumps(data, indent=2) + '\n')
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
