#!/usr/bin/env python3
"""SyncNet (Chung & Zisserman, "Out of time: automated lip sync in the wild", ACCV 2016) on CPU in numpy: the
LSE-C / LSE-D lip-sync measure used by the Wav2Lip, LatentSync and MuseTalk papers (E120).

Weights: the public syncnet_v2.model of joonson/syncnet_python (MIT licence), pinned by SYNCNET_SHA256 and read
without torch (the legacy torch.save format is parsed here with a restricted unpickler: only OrderedDict, float
storages and the tensor rebuild are allowed). The network, the MFCC front end (python_speech_features 0.6 defaults)
and the measure are the official SyncNetInstance.evaluate:
  - video at 25 fps, the face crop of syncnet_python's crop_video (box size s = max(w, h) / 2 and centre, median
    filtered over 13 frames, crop [y - s, y + 1.8 s] x [x - 1.4 s, x + 1.4 s] on a 110-grey padded frame, 224 x 224),
    the box taken from our pinned MediaPipe Face Landmarker instead of S3FD;
  - 5-frame lip windows against 20 MFCC frames (0.2 s) of 16 kHz audio;
  - distances over offsets -VSHIFT..VSHIFT frames, averaged over the clip: AV offset = VSHIFT - argmin,
    min dist (LSE-D) = the minimum, confidence (LSE-C) = median - minimum.

usage: syncnet.py --selftest SYNCNET.model     loads the pinned weights, prints layer count (exit 1 on a mismatch)
"""
import collections
import hashlib
import math
import pickle
import struct
import sys

import numpy as np

SYNCNET_URL = "https://www.robots.ox.ac.uk/~vgg/software/lipsync/data/syncnet_v2.model"
SYNCNET_SHA256 = "961e8696f888fce4f3f3a6c3d5b3267cf5b343100b238e79b2659bff2c605442"
FPS = 25
VSHIFT = 15
CROP_SCALE = 0.4
BOX_SMOOTH = 13
BATCH = 24
BN_EPS = 1e-5

_DTYPES = {"FloatStorage": np.float32, "DoubleStorage": np.float64, "HalfStorage": np.float16,
           "LongStorage": np.int64, "IntStorage": np.int32}


class _Storage:
    def __init__(self, name):
        self.name = name


def _rebuild(storage, offset, size, stride, *_):
    return ("tensor", storage, offset, tuple(size), tuple(stride))


class _Unpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module == "collections" and name == "OrderedDict":
            return collections.OrderedDict
        if module == "torch._utils" and name in ("_rebuild_tensor_v2", "_rebuild_tensor"):
            return _rebuild
        if module == "torch" and name in _DTYPES:
            return _Storage(name)
        raise pickle.UnpicklingError(f"SYNCNET_MODEL_FORBIDDEN {module}.{name}")

    def persistent_load(self, pid):
        _, storage, key, _location, _size, _view = pid
        self.storages[key] = storage.name
        return key


def load(path):
    """The pinned weights as {name: float32 array}; SYNCNET_MODEL_HASH_MISMATCH on any other file."""
    raw = open(path, "rb").read()
    if hashlib.sha256(raw).hexdigest() != SYNCNET_SHA256:
        raise SystemExit("SYNCNET_MODEL_HASH_MISMATCH")
    return _parse(raw)


def _parse(raw):
    """A legacy torch.save state dict (magic, protocol, sys info, the pickled dict with persistent storage ids, the
    storage keys, then each storage as an int64 count and its raw little-endian data) without torch. Private: its only
    caller is load(), after the sha256 check (security sweep of #457, H1)."""
    import io
    f = io.BytesIO(raw)

    def restricted():
        u = _Unpickler(f)
        u.storages = storages
        return u.load()
    storages = {}
    for _ in range(3):              # magic number, protocol version, sys info: plain values, same restricted loader
        restricted()
    state = restricted()
    keys = restricted()
    if not isinstance(state, dict) or not isinstance(keys, list):
        raise pickle.UnpicklingError("SYNCNET_MODEL_FORBIDDEN layout")
    data = {}
    for key in keys:
        n, = struct.unpack("<q", f.read(8))
        dt = np.dtype(_DTYPES[storages[key]])
        data[key] = np.frombuffer(f.read(n * dt.itemsize), dtype=dt)
    weights = {}
    for name, (_, key, offset, size, _stride) in state.items():
        count = int(np.prod(size)) if size else 1
        weights[name] = data[key][offset:offset + count].reshape(size).astype(np.float32)
    return weights


# ---- MFCC: python_speech_features 0.6 mfcc() with its defaults, numpy only ----

def _mel(hz):
    return 2595 * np.log10(1 + hz / 700.0)


def _hz(mel):
    return 700 * (10 ** (mel / 2595.0) - 1)


def mfcc(signal, rate=16000, numcep=13, nfilt=26, nfft=512, preemph=0.97, ceplifter=22):
    """MFCC frames (n, 13) of int16-scaled samples: 25 ms rectangular windows every 10 ms, energy in coefficient 0."""
    signal = np.asarray(signal, dtype=np.float64)
    signal = np.append(signal[:1], signal[1:] - preemph * signal[:-1])
    flen, step = int(round(0.025 * rate)), int(round(0.01 * rate))
    n = 1 if len(signal) <= flen else 1 + int(math.ceil((len(signal) - flen) / step))
    pad = np.concatenate([signal, np.zeros((n - 1) * step + flen - len(signal))])
    idx = np.arange(flen)[None, :] + (np.arange(n) * step)[:, None]
    pspec = np.square(np.abs(np.fft.rfft(pad[idx], nfft))) / nfft
    energy = pspec.sum(1)
    energy = np.where(energy == 0, np.finfo(float).eps, energy)
    pts = _hz(np.linspace(_mel(0), _mel(rate / 2), nfilt + 2))
    bins = np.floor((nfft + 1) * pts / rate)
    fb = np.zeros((nfilt, nfft // 2 + 1))
    for j in range(nfilt):
        for i in range(int(bins[j]), int(bins[j + 1])):
            fb[j, i] = (i - bins[j]) / (bins[j + 1] - bins[j])
        for i in range(int(bins[j + 1]), int(bins[j + 2])):
            fb[j, i] = (bins[j + 2] - i) / (bins[j + 2] - bins[j + 1])
    feat = pspec @ fb.T
    feat = np.log(np.where(feat == 0, np.finfo(float).eps, feat))
    k = np.arange(nfilt)
    dct = np.cos(np.pi * np.arange(numcep)[:, None] * (2 * k[None, :] + 1) / (2 * nfilt)) * np.sqrt(2.0 / nfilt)
    dct[0] /= np.sqrt(2.0)
    feat = feat @ dct.T
    feat *= 1 + (ceplifter / 2.0) * np.sin(np.pi * np.arange(numcep) / ceplifter)
    feat[:, 0] = np.log(energy)
    return feat


# ---- the network (SyncNetModel.S), inference only ----

def _patches(x, kh, kw, stride, pad):
    """(N, C, H, W) -> contiguous (N * Ho * Wo, C * kh * kw) patches and (Ho, Wo)."""
    if pad != (0, 0):
        x = np.pad(x, ((0, 0), (0, 0), (pad[0], pad[0]), (pad[1], pad[1])))
    v = np.lib.stride_tricks.sliding_window_view(x, (kh, kw), axis=(2, 3))[:, :, ::stride[0], ::stride[1]]
    n, c, ho, wo = v.shape[:4]
    return np.ascontiguousarray(v.transpose(0, 2, 3, 1, 4, 5)).reshape(n * ho * wo, c * kh * kw), (ho, wo)


def _conv(x, w, b, stride=(1, 1), pad=(0, 0)):
    p, (ho, wo) = _patches(x, w.shape[-2], w.shape[-1], stride, pad)
    out = (p @ w.reshape(len(w), -1).T).reshape(len(x), ho, wo, len(w))
    return np.ascontiguousarray(out.transpose(0, 3, 1, 2)) + b[None, :, None, None]


def _pool(x, k, stride, pad=(0, 0)):
    if pad != (0, 0):
        x = np.pad(x, ((0, 0), (0, 0), (pad[0], pad[0]), (pad[1], pad[1])), constant_values=-np.inf)
    ho = (x.shape[2] - k[0]) // stride[0] + 1
    wo = (x.shape[3] - k[1]) // stride[1] + 1
    out = None
    for dy in range(k[0]):
        for dx in range(k[1]):
            v = x[:, :, dy:dy + stride[0] * (ho - 1) + 1:stride[0], dx:dx + stride[1] * (wo - 1) + 1:stride[1]]
            out = v.copy() if out is None else np.maximum(out, v, out=out)
    return out


def _bn(x, W, name, relu=True):
    shape = (1, -1) + (1,) * (x.ndim - 2)
    scale = W[name + ".weight"] / np.sqrt(W[name + ".running_var"] + np.float32(BN_EPS))
    shift = W[name + ".bias"] - W[name + ".running_mean"] * scale
    x *= scale.reshape(shape)
    x += shift.reshape(shape)
    return np.maximum(x, 0, out=x) if relu else x


def _fc(x, W, name):
    x = x @ W[name + ".0.weight"].T + W[name + ".0.bias"]
    x = _bn(x, W, name + ".1")
    return x @ W[name + ".3.weight"].T + W[name + ".3.bias"]


def forward_aud(W, x):
    """x: (N, 1, 13, 20) MFCC windows -> (N, 1024)."""
    a = "netcnnaud."
    x = _bn(_conv(x, W[a + "0.weight"], W[a + "0.bias"], pad=(1, 1)), W, a + "1")
    x = _bn(_conv(x, W[a + "4.weight"], W[a + "4.bias"], pad=(1, 1)), W, a + "5")
    x = _pool(x, (3, 3), (1, 2))
    x = _bn(_conv(x, W[a + "8.weight"], W[a + "8.bias"], pad=(1, 1)), W, a + "9")
    x = _bn(_conv(x, W[a + "11.weight"], W[a + "11.bias"], pad=(1, 1)), W, a + "12")
    x = _bn(_conv(x, W[a + "14.weight"], W[a + "14.bias"], pad=(1, 1)), W, a + "15")
    x = _pool(x, (3, 3), (2, 2))
    x = _bn(_conv(x, W[a + "18.weight"], W[a + "18.bias"]), W, a + "19")
    return _fc(x.reshape(len(x), -1), W, "netfcaud")


def _lip_rest(W, x):
    a = "netcnnlip."
    sq = lambda name: W[a + name][:, :, 0]                          # noqa: E731  (O, C, 1, kh, kw) -> 2-D kernel
    x = _pool(_bn(x, W, a + "1"), (3, 3), (2, 2))
    x = _bn(_conv(x, sq("4.weight"), W[a + "4.bias"], (2, 2), (1, 1)), W, a + "5")
    x = _pool(x, (3, 3), (2, 2), (1, 1))
    x = _bn(_conv(x, sq("8.weight"), W[a + "8.bias"], pad=(1, 1)), W, a + "9")
    x = _bn(_conv(x, sq("11.weight"), W[a + "11.bias"], pad=(1, 1)), W, a + "12")
    x = _bn(_conv(x, sq("14.weight"), W[a + "14.bias"], pad=(1, 1)), W, a + "15")
    x = _pool(x, (3, 3), (2, 2))
    x = _bn(_conv(x, sq("18.weight"), W[a + "18.bias"]), W, a + "19")
    return _fc(x.reshape(len(x), -1), W, "netfclip")


def conv3d_first(x, w0, b0, stride=2):
    """Conv3d(kernel (t, kh, kw), stride (1, s, s), no padding) of frames x (T, C, H, W) -> (T - t + 1, O, Ho, Wo):
    the sum over its t time slices of a 2-D convolution of each frame (patches built once per frame)."""
    t, kh, kw = w0.shape[2:]
    n = len(x) - t + 1
    p, (ho, wo) = _patches(x, kh, kw, (stride, stride), (0, 0))
    p = p.reshape(len(x), ho * wo, -1)
    out = np.zeros((n, ho * wo, len(w0)), np.float32)
    for k in range(t):
        out += p[k:k + n] @ w0[:, :, k].reshape(len(w0), -1).T
    out += b0
    return np.ascontiguousarray(out.transpose(0, 2, 1)).reshape(n, len(w0), ho, wo)


def forward_lip(W, frames):
    """frames: (T, 224, 224, 3) BGR 0-255 face crops -> (T - 4, 1024), one per 5-frame window. The first Conv3d
    (kernel 5 x 7 x 7) is the sum over its 5 time slices of a 2-D convolution of each frame, computed once per frame."""
    out = []
    n = len(frames) - 4
    for i in range(0, n, BATCH):
        j = min(n, i + BATCH)
        x = np.ascontiguousarray(np.asarray(frames[i:j + 4], dtype=np.float32).transpose(0, 3, 1, 2))
        out.append(_lip_rest(W, conv3d_first(x, W["netcnnlip.0.weight"], W["netcnnlip.0.bias"])))
    return np.concatenate(out) if out else np.zeros((0, 1024), np.float32)


# ---- face crop and the measure ----

def _medfilt(x, k):
    h = k // 2
    p = np.pad(np.asarray(x, dtype=float), h, mode="edge")
    return np.array([np.median(p[i:i + k]) for i in range(len(x))])


def crop_boxes(boxes):
    """(T, 4) x0, y0, x1, y1 per frame (NaN where no face; filled from the nearest found frame) -> smoothed
    (size, cx, cy) per frame as syncnet_python's crop_video; None when no frame has a face."""
    b = np.asarray(boxes, dtype=float)
    ok = ~np.isnan(b[:, 0])
    if not ok.any():
        return None
    idx = np.arange(len(b))
    b = np.stack([np.interp(idx, idx[ok], b[ok, c]) for c in range(4)], axis=1)
    s = np.maximum(b[:, 2] - b[:, 0], b[:, 3] - b[:, 1]) / 2
    return np.stack([_medfilt(s, BOX_SMOOTH), _medfilt((b[:, 0] + b[:, 2]) / 2, BOX_SMOOTH),
                     _medfilt((b[:, 1] + b[:, 3]) / 2, BOX_SMOOTH)], axis=1)


def crop(frame, size, cx, cy, cs=CROP_SCALE):
    import cv2
    bsi = int(size * (1 + 2 * cs))
    f = np.pad(frame, ((bsi, bsi), (bsi, bsi), (0, 0)), constant_values=110)
    my, mx = cy + bsi, cx + bsi
    face = f[int(my - size):int(my + size * (1 + 2 * cs)), int(mx - size * (1 + cs)):int(mx + size * (1 + cs))]
    return cv2.resize(face, (224, 224))


def distances(lip, aud, vshift=VSHIFT):
    """(n, 2 vshift + 1) euclidean distances of each lip window to the audio windows -vshift..vshift (zero-padded,
    torch pairwise_distance with eps 1e-6)."""
    pad = np.concatenate([np.zeros((vshift, aud.shape[1]), aud.dtype), aud, np.zeros((vshift, aud.shape[1]), aud.dtype)])
    n = len(lip)
    out = np.empty((n, 2 * vshift + 1), dtype=np.float64)
    for k in range(2 * vshift + 1):
        out[:, k] = np.linalg.norm(lip - pad[k:k + n] + 1e-6, axis=1)
    return out


def measure(dists, vshift=VSHIFT):
    """AV offset (frames), confidence (LSE-C) and min distance (LSE-D) from the distance table, as
    SyncNetInstance.evaluate."""
    if not len(dists):
        return None
    return measure_mean(np.asarray(dists).mean(axis=0), vshift)


def measure_mean(mdist, vshift=VSHIFT):
    """The same from the distances averaged over the clip (one per offset -vshift..vshift)."""
    mdist = np.asarray(mdist, dtype=float)
    k = int(np.argmin(mdist))
    return {"offset": int(vshift - k), "conf": round(float(np.median(mdist) - mdist[k]), 3),
            "min_dist": round(float(mdist[k]), 3)}


def embed(W, crops, samples, rate=16000):
    """Lip and audio embeddings of the windows SyncNetInstance.evaluate uses: crops (T, 224, 224, 3) at 25 fps,
    samples int16-scaled mono audio of the same clip."""
    cc = mfcc(samples, rate).T                                     # 13, n
    length = min(len(crops), int(math.floor(len(samples) / 640)))
    last = length - 5
    if last <= 0:
        return np.zeros((0, 1024)), np.zeros((0, 1024))
    lip = forward_lip(W, crops[:last + 4])[:last]
    windows = np.stack([cc[:, 4 * i:4 * i + 20] for i in range(last)])[:, None].astype(np.float32)
    aud = np.concatenate([forward_aud(W, windows[i:i + 256]) for i in range(0, last, 256)])
    return lip, aud


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--selftest":
        weights = load(sys.argv[2])
        print(len(weights))
        sys.exit(0)
    raise SystemExit(__doc__)
