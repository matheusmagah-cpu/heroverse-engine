#!/usr/bin/env python3
"""Assemble native animation frames with timeline-exact audio and captions."""
from pathlib import Path


def timestamp(seconds):
    """SRT uses milliseconds; round once before decomposing the clock."""
    milliseconds = round(seconds * 1000)
    if milliseconds < 0:
        raise ValueError('NEGATIVE_CUE_TIME')
    seconds, ms = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'


def write_srt(path, sentences):
    blocks = []
    for index, sentence in enumerate(sentences, 1):
        if sentence['end'] <= sentence['start']:
            raise ValueError('INVALID_CUE_RANGE')
        blocks.append(f"{index}\n{timestamp(sentence['start'])} --> {timestamp(sentence['end'])}\n{sentence['text']}\n")
    Path(path).write_text('\n'.join(blocks), encoding='utf-8')
