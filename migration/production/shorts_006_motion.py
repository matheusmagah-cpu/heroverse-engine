#!/usr/bin/env python3
"""Closed v2 native-camera and source-texture treatment; no provider or grading.

The input is the already graded native source. Water luminance modulation is
source-bound, not a fluid simulation. Pond motion is camera-only. Pixel centers
use integer source indices; sampling is one explicit bilinear interpolation.
"""
from functools import lru_cache
import math
import numpy as np

COUNTS = (637, 638)
POLYGONS = (
    ((620,1530),(760,1515),(910,1530),(1070,1520),(1070,1650),(930,1650),(780,1625),(620,1635)),
    ((760,1290),(850,1280),(950,1300),(1070,1280),(1070,1380),(940,1380),(850,1405),(760,1380)),
)


def _clock(scene_index, frame_index, frame_count):
    if (type(scene_index) is not int or scene_index not in (0, 1)
            or type(frame_index) is not int or type(frame_count) is not int
            or frame_count != COUNTS[scene_index] or not 0 <= frame_index < frame_count):
        raise ValueError("MATERIAL_MOTION_CLOCK")
    return frame_index / 30, (frame_count - 1) / 30


def hermite(a, b, ma, mb, duration, u):
    return ((2*u**3-3*u**2+1)*a + (u**3-2*u**2+u)*duration*ma
            + (-2*u**3+3*u**2)*b + (u**3-u**2)*duration*mb)


def camera_x(scene_index, seconds):
    if (type(scene_index) is not int or scene_index not in (0, 1)
            or isinstance(seconds, bool) or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds) or not 0 <= seconds <= (COUNTS[scene_index]-1)/30):
        raise ValueError("MATERIAL_CAMERA_CLOCK")
    total = (COUNTS[scene_index]-1)/30
    if scene_index == 0:
        if seconds <= 3:
            return hermite(0, 40, 20, .5, 3, seconds/3)
        return hermite(40, 48, .5, .3, total-3, (seconds-3)/(total-3))
    u = seconds/total
    return 448 + 32*(3*u*u-2*u*u*u)


def polygon_mask(u, v, polygon):
    """Exact edge-segment distance with an inward-only, strict-interior mask."""
    u, v = np.broadcast_arrays(np.asarray(u, dtype=np.float64), np.asarray(v, dtype=np.float64))
    distance2 = np.full(u.shape, np.inf)
    inside = np.zeros(u.shape, dtype=bool)
    boundary = np.zeros(u.shape, dtype=bool)
    for (ax,ay),(bx,by) in zip(polygon, polygon[1:]+polygon[:1]):
        dx,dy = bx-ax,by-ay
        cross = (u-ax)*dy-(v-ay)*dx
        dot = (u-ax)*dx+(v-ay)*dy
        boundary |= (cross == 0) & (dot >= 0) & (dot <= dx*dx+dy*dy)
        projection = np.clip(((u-ax)*dx+(v-ay)*dy)/(dx*dx+dy*dy),0,1)
        distance2 = np.minimum(distance2,(u-ax-projection*dx)**2+(v-ay-projection*dy)**2)
        if dy:
            inside ^= ((ay > v) != (by > v)) & (u < ax+(v-ay)*dx/dy)
    result = np.where(inside & ~boundary & (distance2 > 0),np.minimum(1,np.sqrt(distance2)/12),0)
    return result.astype(np.float32)


@lru_cache(maxsize=1)
def _water_patches():
    patches = []
    for index,polygon in enumerate(POLYGONS):
        x0,x1 = min(p[0] for p in polygon),max(p[0] for p in polygon)+1
        v0,v1 = min(p[1] for p in polygon),max(p[1] for p in polygon)+1
        u,v = np.meshgrid(np.arange(x0,x1),np.arange(v0,v1))
        mask = polygon_mask(u,v,polygon)
        phase = 2*np.pi*((v+.15*u)/96)+(0 if index == 0 else np.pi/3)
        mask.setflags(write=False);phase.setflags(write=False)
        patches.append((slice(v0+64,v1+64),slice(x0,x1),mask,phase))
    return tuple(patches)


def _base(base_rgb):
    base = np.asarray(base_rgb)
    if base.shape != (2048,2048,3) or base.dtype.kind not in 'uif':
        raise ValueError("MATERIAL_NATIVE_IMAGE")
    value = base.astype(np.float32) / (255 if base.dtype == np.uint8 else 1)
    if not np.isfinite(value).all() or np.any(value < 0) or np.any(value > 1):
        raise ValueError("MATERIAL_NATIVE_IMAGE")
    return value


def texture_frame(base_rgb, seconds):
    """Native-space texture only, exposed for independent no-camera diagnostics."""
    if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not math.isfinite(seconds):
        raise ValueError("MATERIAL_TEXTURE_CLOCK")
    base = _base(base_rgb)
    for ys,xs,mask,phase in _water_patches():
        original = base[ys,xs].copy()
        delta = mask*np.sin(phase-2*np.pi*seconds/4)
        base[ys,xs] = np.clip(original+np.minimum(.06,.16*original)*delta[...,None],0,1)
    return base


def bilinear_sample(base, x, y):
    """Separable sample at supplied pixel-center coordinates, not cv2 lookup tables."""
    x,y = np.asarray(x,np.float64),np.asarray(y,np.float64)
    if (x.ndim != 1 or y.ndim != 1 or not np.isfinite(x).all() or not np.isfinite(y).all()
            or np.any(x < 0) or np.any(y < 0) or np.any(x > base.shape[1]-1) or np.any(y > base.shape[0]-1)):
        raise ValueError("MATERIAL_SAMPLE_BOUNDS")
    x0,y0 = np.floor(x).astype(int),np.floor(y).astype(int)
    x1,y1 = np.minimum(x0+1,base.shape[1]-1),np.minimum(y0+1,base.shape[0]-1)
    wx,wy = (x-x0).astype(np.float32)[None,:,None],(y-y0).astype(np.float32)[:,None,None]
    top = base[y0[:,None],x0[None,:]]*(1-wx)+base[y0[:,None],x1[None,:]]*wx
    bottom = base[y1[:,None],x0[None,:]]*(1-wx)+base[y1[:,None],x1[None,:]]*wx
    return (top*(1-wy)+bottom*wy).astype(np.float32)


def source_frame(base_rgb, scene_index, frame_index, frame_count):
    seconds,_ = _clock(scene_index,frame_index,frame_count)
    base = texture_frame(base_rgb,seconds) if scene_index == 0 else _base(base_rgb)
    width,height,y = (1080,1920,64) if scene_index == 0 else (1152,2048,0)
    xx = camera_x(scene_index,seconds)+(np.arange(1080)+.5)*width/1080-.5
    yy = y+(np.arange(1920)+.5)*height/1920-.5
    return bilinear_sample(base,xx,yy)
