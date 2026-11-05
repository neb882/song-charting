"""Album art and a background image for the song folder (M4-11, DESIGN.md 2.16).

    pictures = art.prepare(song, album_art=None, background=None)   # before any audio work: a bad given image raises
    pictures.files    # {"album.jpg": bytes, "background.jpg": bytes}, those made
    pictures.record   # pipeline.json's and report.json's `art`: whether each was added and where it came from

  * **album.jpg**: the image a person gives (`album_art`), else the song file's embedded cover picture (an attached
    picture: MP3's APIC frame, FLAC's PICTURE block, M4A's covr, as ffmpeg lists them: the one marked "Cover (front)",
    else the first), else none. Centre-cropped to a square and resized to ALBUM_SIZE, 512x512 (scan-chart wants
    500x500 or 512x512: its albumArtSize issue otherwise), up or down. scan-chart and Clone Hero read album.jpg,
    album.jpeg or album.png (scan-chart's hasAlbumName).
  * **background.jpg**: the image a person gives (`background`), scaled down to fit BACKGROUND_FIT, 1920x1080, never
    up, its shape kept. Clone Hero shows a song's own background from an image named "background" (.png, .jpg or
    .jpeg) in its folder when Settings > Gameplay > "Use Song Backgrounds" is on (the Clone Hero wiki, Guides and
    Tutorials, Custom Content: "Adding Song-specific Content"; it recommends 1920x1080 for backgrounds).
  * **Checks.** A given image must be a JPEG, PNG or WebP by its content (ALLOWED; the extension is not trusted), at
    most MAX_BYTES (20 MB) and MAX_PIXELS (64 megapixels, about 192 MB once decoded), and decode whole: anything else
    is an InputError naming the limit, raised before any audio work. The embedded picture failing the same checks is
    a warning and no album art: a picture never fails a chart.
  * **No metadata survives.** Every image is decoded and encoded again from its pixels alone, as a new image, with
    fixed settings (JPEG_SETTINGS), so no EXIF (a phone photo's can hold its GPS position), XMP, ICC profile or
    comment reaches the song folder. EXIF's orientation is applied first, so a phone photo stands as it is shown.
    Transparency goes onto black; 16-bit greys are scaled to 8 bits. The same image gives byte-identical files.
  * **Records** name no file outside the work folder: where each image came from ("embedded", "given", or None), its
    source's format and size, and what was written.

The images are made with Pillow, which songcharter's preview brings (matplotlib needs it): without it a given image is
a ToolError with the fix, and an embedded picture a warning. ffmpeg (audio.ffmpeg_exe) finds the embedded picture.
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import audio as A
from .errors import InputError, ToolError

ALBUM = "album.jpg"                 # the album art's name in the song folder (scan-chart's hasAlbumName)
BACKGROUND = "background.jpg"       # the background's (Clone Hero's song-specific "background" image)
ALBUM_SIZE = 512                    # pixels a side: scan-chart's albumArtSize
BACKGROUND_FIT = (1920, 1080)       # the background fits inside this, scaled down only
MAX_BYTES = 20 * 10 ** 6            # 20 MB (10^6 bytes, the project's unit): a given image's file
MAX_PIXELS = 64 * 10 ** 6           # 64 megapixels: a 48 MP phone photo fits; decoded, about 192 MB of RGB
ALLOWED = ("JPEG", "PNG", "WEBP")   # Pillow's names of the formats taken
FORMATS = "JPEG, PNG or WebP"
EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")   # the page's picker and upload (the content decides, all the same)
JPEG_SETTINGS = {"quality": 90, "subsampling": 2, "optimize": False, "progressive": False}  # 2: 4:2:0, baseline
WHAT = {"album_art": "album art", "background": "background image"}
PILLOW = "album art and backgrounds need Pillow: pip install pillow (songcharter[preview] brings it)"
STREAM = re.compile(r"^\s*Stream #0:(\d+)\S*: Video: ")


@dataclass
class Pictures:
    """What `prepare` made: the files for the song folder (name -> JPEG bytes), the record, and its warnings."""
    files: dict[str, bytes] = field(default_factory=dict)
    record: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _pil():
    """Pillow's Image and ImageOps, or a ToolError with the fix."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        raise ToolError(PILLOW) from None
    return Image, ImageOps


def check_file(path: Path | str, what: str) -> bytes:
    """A given image's bytes: it exists, is a file and is at most MAX_BYTES; else an InputError naming it by its file
    name only (records and logs keep no path of the person's)."""
    p = Path(path).expanduser()
    if not p.is_file():
        raise InputError(f"the {what} {p.name} {'is not a file' if p.exists() else 'does not exist'}")
    size = p.stat().st_size
    if size > MAX_BYTES:
        raise InputError(f"the {what} {p.name} is {size / 10 ** 6:.1f} MB, over the limit of {MAX_BYTES // 10 ** 6} "
                         "MB")
    try:
        return p.read_bytes()
    except OSError as e:
        raise InputError(f"cannot read the {what} {p.name} ({e.strerror or type(e).__name__})") from None


def decode(data: bytes, what: str):
    """The image in `data` as an 8-bit RGB Pillow image, upright, with no metadata, and its source ({"format",
    "width", "height"}); an InputError when it is not a JPEG, PNG or WebP, is over MAX_BYTES or MAX_PIXELS, or does
    not decode whole."""
    Image, ImageOps = _pil()
    if len(data) > MAX_BYTES:
        raise InputError(f"the {what} is {len(data) / 10 ** 6:.1f} MB, over the limit of {MAX_BYTES // 10 ** 6} MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)   # MAX_PIXELS is the limit here
            img = Image.open(io.BytesIO(data), formats=list(ALLOWED))
    except Image.DecompressionBombError:
        raise InputError(f"the {what} is over the limit of {MAX_PIXELS // 10 ** 6} megapixels") from None
    except Exception:  # noqa: BLE001  UnidentifiedImageError, or a header Pillow cannot parse
        raise InputError(f"the {what} is not a {FORMATS} image") from None
    w, h = img.size
    if w * h > MAX_PIXELS:
        raise InputError(f"the {what} is {w}x{h}, {w * h / 10 ** 6:.1f} megapixels, over the limit of "
                         f"{MAX_PIXELS // 10 ** 6} megapixels")
    source = {"format": img.format, "width": w, "height": h}
    try:
        img.load()
    except Exception as e:  # noqa: BLE001  truncated or corrupt data
        raise InputError(f"the {what} could not be decoded ({type(e).__name__})") from None
    try:
        img = ImageOps.exif_transpose(img)   # the EXIF orientation, before the EXIF goes
    except Exception:  # noqa: BLE001  an EXIF block Pillow cannot read: the picture as it is stored
        pass
    try:
        img = _rgb(img, Image)
    except Exception as e:  # noqa: BLE001  a mode Pillow cannot turn into RGB
        raise InputError(f"the {what} could not be decoded ({type(e).__name__}: mode {img.mode})") from None
    return Image.frombytes("RGB", img.size, img.tobytes()), source   # a new image: nothing of the file's info


def _rgb(img, Image):
    """8-bit RGB: transparency onto black, 16-bit and 32-bit greys scaled to 8 bits."""
    if img.mode in ("I", "F") or img.mode.startswith("I;16"):
        import numpy as np
        a = np.asarray(img, dtype=np.float64)
        a = a / 257.0 if img.mode != "F" else a
        img = Image.fromarray(np.clip(np.rint(a), 0, 255).astype(np.uint8), "L")
    if img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        base = Image.new("RGB", rgba.size, (0, 0, 0))
        base.paste(rgba, mask=rgba.getchannel("A"))
        return base
    return img.convert("RGB") if img.mode != "RGB" else img


def encode(img) -> bytes:
    """`img` as a JPEG with JPEG_SETTINGS and nothing else (no EXIF, ICC profile or comment)."""
    Image, _ = _pil()
    fresh = Image.frombytes("RGB", img.size, img.tobytes())   # resize keeps the source's info: start from pixels
    out = io.BytesIO()
    fresh.save(out, "JPEG", **JPEG_SETTINGS)
    return out.getvalue()


def album_jpeg(img) -> bytes:
    """album.jpg: the centre square of `img`, resized to ALBUM_SIZE (Lanczos)."""
    Image, _ = _pil()
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    square = img.resize((ALBUM_SIZE, ALBUM_SIZE), Image.Resampling.LANCZOS, box=(left, top, left + side, top + side))
    return encode(square)


def background_size(w: int, h: int, fit: tuple[int, int] = BACKGROUND_FIT) -> tuple[int, int]:
    """The background's size: (w, h) scaled down to fit inside `fit`, its shape kept; never scaled up."""
    scale = min(fit[0] / w, fit[1] / h, 1.0)
    return (w, h) if scale >= 1.0 else (max(1, round(w * scale)), max(1, round(h * scale)))


def background_jpeg(img) -> bytes:
    """background.jpg: `img` scaled down to fit BACKGROUND_FIT (Lanczos), or as it is when it fits."""
    Image, _ = _pil()
    size = background_size(*img.size)
    return encode(img if size == img.size else img.resize(size, Image.Resampling.LANCZOS))


def picture_stream(text: str) -> int | None:
    """The index of the cover among the attached pictures ffmpeg lists in `text` (its stderr for `-i FILE`): the one
    whose metadata says "Cover (front)", else the first; None when there is none."""
    blocks: list[tuple[int, str]] = []
    for line in text.splitlines():
        m = STREAM.match(line)
        if m:
            blocks.append((int(m.group(1)), line))
        elif line.lstrip().startswith("Stream #"):
            blocks.append((-1, line))   # an audio or data stream: it ends the block before it
        elif blocks:
            blocks[-1] = (blocks[-1][0], blocks[-1][1] + "\n" + line)
    pictures = [(i, b) for i, b in blocks if i >= 0 and "(attached pic)" in b.splitlines()[0]]
    front = next((i for i, b in pictures if re.search(r":\s*Cover \(front\)\s*$", b, re.M)), None)
    return front if front is not None else (pictures[0][0] if pictures else None)


def embedded_picture(song: Path | str, ffmpeg: str | None = None) -> bytes | None:
    """The song file's embedded cover picture, as stored (ffmpeg's stream copy of the attached picture): None when
    there is none, or ffmpeg cannot read the file (its decode says so)."""
    exe = ffmpeg or A.ffmpeg_exe()
    probe = subprocess.run([exe, "-hide_banner", "-nostdin", "-i", str(song)], capture_output=True)  # exits 1: no output
    index = picture_stream(probe.stderr.decode("utf-8", "replace"))
    if index is None:
        return None
    got = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(song), "-map", f"0:{index}",
                          "-c", "copy", "-frames:v", "1", "-f", "image2pipe", "pipe:1"], capture_output=True)
    return got.stdout if got.returncode == 0 and got.stdout else None


def _made(name: str, data: bytes, source: dict, origin: str) -> dict:
    Image, _ = _pil()
    w, h = Image.open(io.BytesIO(data)).size
    return {"added": True, "from": origin, "file": name, "width": w, "height": h, "bytes": len(data), "source": source}


def prepare(song: Path | str, album_art: Path | str | None = None, background: Path | str | None = None, *,
            ffmpeg: str | None = None) -> Pictures:
    """album.jpg and background.jpg for the song (the module docstring), in memory, one image at a time. A given image
    that fails its checks is an InputError (Pillow missing: a ToolError); the embedded picture failing is a warning."""
    out = Pictures()
    if album_art is not None:
        img, source = decode(check_file(album_art, WHAT["album_art"]), f"{WHAT['album_art']} {Path(album_art).name}")
        out.files[ALBUM] = album_jpeg(img)
        out.record["album_art"] = _made(ALBUM, out.files[ALBUM], source, "given")
    else:
        out.record["album_art"] = _embedded(song, ffmpeg, out)
    if background is not None:
        img, source = decode(check_file(background, WHAT["background"]), f"{WHAT['background']} "
                             f"{Path(background).name}")
        out.files[BACKGROUND] = background_jpeg(img)
        out.record["background"] = _made(BACKGROUND, out.files[BACKGROUND], source, "given")
    else:
        out.record["background"] = {"added": False, "from": None, "why": "none given"}
    return out


def _embedded(song: Path | str, ffmpeg: str | None, out: Pictures) -> dict:
    """album.jpg from the song file's own picture, into `out`; its record. A picture that fails is a warning."""
    data = embedded_picture(song, ffmpeg)
    if data is None:
        return {"added": False, "from": None, "why": "no album art given, and the song file has no picture"}
    try:
        img, source = decode(data, "song file's picture")
        jpeg = album_jpeg(img)
    except (InputError, ToolError) as e:
        why = str(e)
        why = why.removeprefix("the song file's picture ") if why.startswith("the song") else f"is not used: {why}"
        out.warnings.append(f"album art: the song file's picture {why}: no album art")
        return {"added": False, "from": None, "why": f"the song file's picture {why}"}
    out.files[ALBUM] = jpeg
    return _made(ALBUM, jpeg, source, "embedded")


def write(pictures: Pictures, folder: Path) -> dict[str, Path]:
    """The pictures' files into `folder` (made when needed; the old ones there go first): name -> path."""
    folder.mkdir(parents=True, exist_ok=True)
    for name in (ALBUM, BACKGROUND):
        if name not in pictures.files:
            (folder / name).unlink(missing_ok=True)
    out = {}
    for name, data in pictures.files.items():
        part = folder / f"{name}.part"
        part.write_bytes(data)
        os.replace(part, folder / name)
        out[name] = folder / name
    return out
