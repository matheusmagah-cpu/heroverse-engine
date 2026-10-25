"""Local input images for Flash frames/reference generation, checked against the public capability spec.

Only PNG/JPEG files inside this repository are read (our approved stills and character sheets).
Spec (model-capability-spec, agnes-video-new-flash, 2026-10-25): up to 5 images, 15 MiB each,
side 256-5760 px, aspect ratio 0.4-2.5.
"""
from pathlib import Path
import struct

from client import PavoError

REPO = Path(__file__).resolve().parents[3]
MAX_IMAGES = 5
MAX_IMAGE_BYTES = 15 * 1024 * 1024
SIDE = (256, 5760)
ASPECT = (0.4, 2.5)


def _png_size(head):
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise PavoError("INPUT_IMAGE_INVALID")
    return struct.unpack(">II", head[16:24])


def _jpeg_size(data):
    if data[:2] != b"\xff\xd8":
        raise PavoError("INPUT_IMAGE_INVALID")
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            raise PavoError("INPUT_IMAGE_INVALID")
        marker = data[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return width, height
        i += 2 + length
    raise PavoError("INPUT_IMAGE_INVALID")


def image(path, repo=None):
    """Validated local image: {"path", "data", "mime", "width", "height", "filename"}; no network."""
    if not isinstance(path, str) or not path or len(path) > 512 or "\x00" in path:
        raise PavoError("INPUT_IMAGE_PATH_REFUSED")
    root = Path(repo or REPO).resolve()
    target = (root / path).resolve()
    if root not in target.parents or not target.is_file():
        raise PavoError("INPUT_IMAGE_PATH_REFUSED")
    suffix = target.suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(suffix)
    if not mime:
        raise PavoError("INPUT_IMAGE_TYPE_REFUSED")
    size = target.stat().st_size
    if not 0 < size <= MAX_IMAGE_BYTES:
        raise PavoError("INPUT_IMAGE_SIZE_REFUSED")
    data = target.read_bytes()
    width, height = _png_size(data[:24]) if mime == "image/png" else _jpeg_size(data)
    if not (SIDE[0] <= width <= SIDE[1] and SIDE[0] <= height <= SIDE[1]):
        raise PavoError("INPUT_IMAGE_SIDE_REFUSED")
    if not ASPECT[0] <= width / height <= ASPECT[1]:
        raise PavoError("INPUT_IMAGE_ASPECT_REFUSED")
    return {"path": str(target.relative_to(root)), "data": data, "mime": mime,
            "width": width, "height": height, "filename": target.name}


def plan(first_frame="", last_frame="", references=None, repo=None):
    """(mode, images): frames_to_video with [first, last?], omni_to_video with references, or text only."""
    if references is not None and not isinstance(references, (list, tuple)):
        raise PavoError("INPUT_REFERENCES_REFUSED")
    references = list(references or [])
    if not all(isinstance(r, str) for r in references) or len(references) > MAX_IMAGES:
        raise PavoError("INPUT_REFERENCES_REFUSED")
    if not isinstance(first_frame, str) or not isinstance(last_frame, str):
        raise PavoError("INPUT_IMAGE_PATH_REFUSED")
    if references and (first_frame or last_frame):
        raise PavoError("FRAMES_AND_REFERENCES_EXCLUSIVE")
    if last_frame and not first_frame:
        raise PavoError("LAST_FRAME_NEEDS_FIRST_FRAME")
    if references:
        return "omni_to_video", [image(r, repo) for r in references]
    return "frames_to_video", [image(p, repo) for p in (first_frame, last_frame) if p]
