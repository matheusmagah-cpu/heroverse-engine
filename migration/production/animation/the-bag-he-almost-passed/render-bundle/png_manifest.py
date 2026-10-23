"""Canonical render-file encoding: omit nondeterministic PNG metadata only.

Pixel/colour chunks are byte-preserved, including their original CRCs. Blender
writes Date and RenderTime text even when burn-in stamps are disabled.
"""
import struct
import zlib


def canonical_png(data):
    if data[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('NOT_PNG')
    result=bytearray(data[:8]);offset=8;ended=False
    while offset<len(data):
        if offset+12>len(data):raise ValueError('TRUNCATED_PNG')
        length=struct.unpack('>I',data[offset:offset+4])[0];end=offset+length+12
        if end>len(data):raise ValueError('TRUNCATED_PNG')
        kind=data[offset+4:offset+8];payload=data[offset+8:end-4]
        if zlib.crc32(kind+payload)&0xffffffff!=struct.unpack('>I',data[end-4:end])[0]:raise ValueError('PNG_CRC')
        if kind not in (b'tEXt',b'zTXt',b'iTXt',b'tIME'):result.extend(data[offset:end])
        offset=end
        if kind==b'IEND':ended=True;break
    if not ended or offset!=len(data):raise ValueError('INVALID_PNG_END')
    return bytes(result)
