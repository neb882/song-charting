"""Album art and a background image (songcharter.art, M4-11), with pictures made here (no real photo): the song
file's embedded picture (an MP3's and a FLAC's) becomes a 512x512 album.jpg, centre-cropped; a given album art wins
over it; a given background is scaled down to fit 1920x1080 and never up; no EXIF, comment or ICC profile survives;
a bad or oversized given image is an InputError (exit 2) before any work, and an embedded picture that fails a
warning; the same inputs give byte-identical files. Through the pipeline (test_pipeline's stand-in engines): the song
folder gets the pictures and nothing else in it changes, pipeline.json and report.json say where each came from with
no path of the person's, and scan-chart stops reporting noAlbumArt."""
import io
import json
import subprocess
import sys
import tracemalloc
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

import songcharter.pipeline as P  # noqa: E402
from songcharter import art as ART  # noqa: E402
from songcharter import audio as A  # noqa: E402
from songcharter.assemble import find_scan_chart, parse_config  # noqa: E402
from songcharter.cli import main  # noqa: E402
from songcharter.errors import InputError, ToolError  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from test_pipeline import standins, write_song  # noqa: E402

RED, BLUE, GREEN = (220, 20, 20), (20, 20, 220), (20, 200, 40)


# ------------------------------------------------------------------------------------------------ pictures

def picture(size, fmt="PNG", centre=RED, band=BLUE, **save) -> bytes:
    """A picture whose centre square is `centre` and whose bands beside it (or above and below) are `band`."""
    w, h = size
    img = Image.new("RGB", size, band)
    side = min(w, h)
    img.paste(Image.new("RGB", (side, side), centre), ((w - side) // 2, (h - side) // 2))
    out = io.BytesIO()
    img.save(out, fmt, **save)
    return out.getvalue()


def write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def tone(path: Path, codec: str = "flac", seconds: float = 1.0) -> Path:
    """A short tone with no picture, as FLAC or MP3 (libmp3lame), with no ID3 tag."""
    subprocess.run([A.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=f=440:d={seconds}", "-c:a", codec, *(["-write_id3v2", "0"] if codec == "libmp3lame" else []),
                    str(path)], check=True)
    return path


def with_picture(song: Path, out: Path, image: Path, front: bool = True) -> Path:
    """`song` with `image` muxed in as its attached picture (ffmpeg, stream copy: the audio as it was)."""
    subprocess.run([A.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(song), "-i", str(image),
                    "-map", "0:a", "-map", "1:v", "-c", "copy", "-disposition:v", "attached_pic",
                    "-metadata:s:v", f"comment={'Cover (front)' if front else 'Other'}", str(out)], check=True)
    return out


def id3_mp3(out: Path, plain_mp3: Path, *pictures: tuple[str, bytes, int]) -> Path:
    """An MP3 with a hand-made ID3v2.3 tag holding APIC frames (mime, data, picture type: 3 the front cover), so the
    picture's bytes can be anything at all."""
    frames = b""
    for mime, data, kind in pictures:
        payload = b"\x00" + mime.encode() + b"\x00" + bytes([kind]) + b"\x00" + data
        frames += b"APIC" + len(payload).to_bytes(4, "big") + b"\x00\x00" + payload
    n = len(frames)
    size = bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F])
    out.write_bytes(b"ID3\x03\x00\x00" + size + frames + plain_mp3.read_bytes())
    return out


def opened(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


def near(pixel, colour, tol=40) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(pixel, colour))


def exif_jpeg(size=(400, 200), orientation: int = 6) -> bytes:
    """A JPEG as a phone writes one: EXIF with a GPS position, the maker and an orientation, a comment, an ICC
    profile and XMP."""
    exif = Image.Exif()
    exif[0x0112] = orientation
    exif[0x010F] = "MadeUpPhoneCo"
    exif[0x8825] = {1: "N", 2: (51.0, 30.0, 12.5), 3: "W", 4: (0.0, 7.0, 39.0)}
    out = io.BytesIO()
    img = Image.new("RGB", size, RED)
    img.paste(Image.new("RGB", (size[0] // 4, size[1]), BLUE), (0, 0))   # a blue band on the left, as taken
    img.save(out, "JPEG", exif=exif.tobytes(), comment=b"made-up secret comment", icc_profile=b"\0" * 300,
             xmp=b"<x:xmpmeta>made-up xmp place</x:xmpmeta>")
    return out.getvalue()


NO_METADATA = (b"Exif", b"MadeUpPhoneCo", b"secret", b"ICC_PROFILE", b"xmpmeta", b"made-up")


# ------------------------------------------------------------------------------------------------ the album art

def test_an_mp3_and_a_flac_with_a_picture_give_a_512_album_jpg(tmp_path):
    """The embedded picture, a JPEG in an MP3 and a PNG in a FLAC, becomes album.jpg: 512x512, a JPEG, recorded as
    "embedded" with its source's format and size (the PNG's transparency on black)."""
    jpeg = write(tmp_path / "cover.jpg", picture((640, 400), "JPEG", quality=95))
    png = io.BytesIO()
    Image.new("RGBA", (300, 500), (*GREEN, 255)).save(png, "PNG")
    png = write(tmp_path / "cover.png", png.getvalue())
    for ext, codec, image, fmt, size in (("mp3", "libmp3lame", jpeg, "JPEG", (640, 400)),
                                         ("flac", "flac", png, "PNG", (300, 500))):
        song = with_picture(tone(tmp_path / f"t.{ext}", codec), tmp_path / f"pictured.{ext}", image)
        got = ART.prepare(song)
        assert set(got.files) == {"album.jpg"} and got.warnings == []
        img = opened(got.files["album.jpg"])
        assert img.format == "JPEG" and img.size == (512, 512) and img.mode == "RGB"
        assert got.record["album_art"] == {"added": True, "from": "embedded", "file": "album.jpg", "width": 512,
                                           "height": 512, "bytes": len(got.files["album.jpg"]),
                                           "source": {"format": fmt, "width": size[0], "height": size[1]}}
        assert got.record["background"] == {"added": False, "from": None, "why": "none given"}
        assert near(img.getpixel((256, 256)), RED if fmt == "JPEG" else GREEN)


def test_a_non_square_picture_is_centre_cropped(tmp_path):
    """A wide picture loses its sides and a tall one its top and bottom: no band survives, at the edges or the
    corners, and the square is not squashed."""
    for size in ((800, 400), (400, 900)):
        img, _ = ART.decode(picture(size), "test picture")
        out = opened(ART.album_jpeg(img))
        assert out.size == (512, 512)
        for xy in ((2, 2), (509, 2), (2, 509), (509, 509), (2, 256), (509, 256), (256, 2), (256, 509), (256, 256)):
            assert near(out.getpixel(xy), RED), (size, xy, out.getpixel(xy))
    small, _ = ART.decode(picture((100, 60)), "test picture")   # a small one is resized up to 512 all the same
    assert opened(ART.album_jpeg(small)).size == (512, 512)


def test_no_picture_gives_none(tmp_path):
    for song in (tone(tmp_path / "plain.flac"), tone(tmp_path / "plain.mp3", "libmp3lame"), tmp_path / "missing.wav"):
        got = ART.prepare(song)
        assert got.files == {} and got.warnings == []
        assert got.record["album_art"] == {"added": False, "from": None,
                                           "why": "no album art given, and the song file has no picture"}


def test_the_front_cover_is_the_one_taken(tmp_path):
    """Of a file's attached pictures, the one marked "Cover (front)", else the first; a real video stream, or an
    audio-only file, has none."""
    mp3 = tone(tmp_path / "plain.mp3", "libmp3lame")
    back = picture((300, 300), centre=BLUE)
    front = picture((300, 300), "JPEG", centre=GREEN)
    song = id3_mp3(tmp_path / "two.mp3", mp3, ("image/png", back, 4), ("image/jpeg", front, 3))
    assert ART.embedded_picture(song) == front
    assert near(opened(ART.prepare(song).files["album.jpg"]).getpixel((256, 256)), GREEN)
    song = id3_mp3(tmp_path / "two-others.mp3", mp3, ("image/png", back, 4), ("image/jpeg", front, 0))
    assert ART.embedded_picture(song) == back   # neither is the front cover: the first
    listing = ("  Stream #0:0: Audio: aac (LC), 44100 Hz, stereo, fltp\n"
               "  Stream #0:1[0x2](und): Video: h264 (High), yuv420p, 1280x720, 25 fps\n"
               "      Metadata:\n        comment         : Cover (front)\n")
    assert ART.picture_stream(listing) is None
    listing += ("  Stream #0:2: Video: png, rgba, 300x300, 90k tbr, 90k tbn (attached pic)\n"
                "      Metadata:\n        comment         : Other\n"
                "  Stream #0:3: Video: mjpeg (Baseline), 600x600, 90k tbn (attached pic)\n"
                "      Metadata:\n        comment         : Cover (front)\n")
    assert ART.picture_stream(listing) == 3
    assert ART.picture_stream(listing.replace("Cover (front)\n", "Cover (back)\n")) == 2


def test_a_given_album_art_wins_over_the_embedded_one(tmp_path):
    song = with_picture(tone(tmp_path / "t.flac"), tmp_path / "pictured.flac",
                        write(tmp_path / "red.png", picture((300, 300))))
    given = write(tmp_path / "mine" / "green.webp", picture((700, 500), "WEBP", centre=GREEN, band=GREEN))
    got = ART.prepare(song, album_art=given)
    assert near(opened(got.files["album.jpg"]).getpixel((256, 256)), GREEN)
    assert got.record["album_art"]["from"] == "given" and got.record["album_art"]["source"] == {
        "format": "WEBP", "width": 700, "height": 500}
    assert str(tmp_path) not in json.dumps(got.record)   # no path of the person's in the record


# ------------------------------------------------------------------------------------------------ the background

def test_the_background_is_scaled_down_to_fit_never_up(tmp_path):
    for size, want in (((3840, 1600), (1920, 800)), ((1080, 2400), (486, 1080)), ((4000, 2250), (1920, 1080)),
                       ((1920, 1080), (1920, 1080)), ((800, 600), (800, 600)), ((1921, 1080), (1920, 1079))):
        assert ART.background_size(*size) == want, size
        path = write(tmp_path / f"bg{size[0]}.png", picture(size))
        got = ART.prepare(tone(tmp_path / "t.flac"), background=path)
        img = opened(got.files["background.jpg"])
        assert img.format == "JPEG" and img.size == want, size
        assert got.record["background"] == {"added": True, "from": "given", "file": "background.jpg",
                                            "width": want[0], "height": want[1],
                                            "bytes": len(got.files["background.jpg"]),
                                            "source": {"format": "PNG", "width": size[0], "height": size[1]}}
        assert near(img.getpixel((img.width // 2, img.height // 2)), RED)


# ------------------------------------------------------------------------------------------------ what survives

def test_no_metadata_survives_and_the_orientation_is_applied(tmp_path):
    """A phone-like JPEG (EXIF with GPS, the maker and orientation 6, a comment, an ICC profile, XMP): nothing of it
    survives in either file, and both stand as the photo is shown (turned a quarter: the blue band on top). A PNG's
    text chunks do not survive either."""
    data = exif_jpeg()
    assert all(m in data for m in NO_METADATA) and opened(data).getexif().get_ifd(0x8825)[2] == (51.0, 30.0, 12.5)
    photo = write(tmp_path / "photo.jpg", data)
    got = ART.prepare(tone(tmp_path / "t.flac"), album_art=photo, background=photo)
    for name, blob in got.files.items():
        assert not any(m in blob for m in NO_METADATA), name
        img = opened(blob)
        assert set(img.info) <= {"jfif", "jfif_version", "jfif_unit", "jfif_density", "dpi"}, (name, img.info)
        assert not img.getexif() and "icc_profile" not in img.info
    bg = opened(got.files["background.jpg"])
    assert bg.size == (200, 400)   # 400x200 stored, orientation 6: shown upright as 200x400
    assert near(bg.getpixel((100, 20)), BLUE) and near(bg.getpixel((100, 380)), RED)
    from PIL import PngImagePlugin
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Comment", "made-up secret comment")
    meta.add_itxt("XML:com.adobe.xmp", "<x:xmpmeta>made-up xmp place</x:xmpmeta>")
    png = write(tmp_path / "tagged.png", picture((600, 600), pnginfo=meta))
    got = ART.prepare(tone(tmp_path / "t.flac"), album_art=png, background=png)
    assert not any(m in blob for blob in got.files.values() for m in NO_METADATA)


def as_png(img: Image.Image, **save) -> bytes:
    out = io.BytesIO()
    img.save(out, "PNG", **save)
    return out.getvalue()


def test_transparency_goes_on_black_and_16_bit_greys_are_scaled(tmp_path):
    """RGBA, LA and a palette with a transparent entry (tRNS) go onto black, their opaque halves as they are; a 16-bit
    grey is rounded to 8 bits exactly, round(x / 257), at the edges of the rounding too."""
    rgba = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
    rgba.paste((*RED, 255), (32, 0, 64, 64))
    la = Image.new("LA", (64, 64), (255, 0))
    la.paste((200, 255), (32, 0, 64, 64))
    palette = Image.new("P", (64, 64), 0)
    palette.putpalette([255, 255, 255, *RED])   # entry 0 white and transparent, entry 1 red
    palette.paste(1, (32, 0, 64, 64))
    for img, opaque, save in ((rgba, RED, {}), (la, (200, 200, 200), {}), (palette, RED, {"transparency": 0})):
        got, _ = ART.decode(as_png(img, **save), "test picture")
        assert got.mode == "RGB" and got.getpixel((5, 5)) == (0, 0, 0) and got.getpixel((40, 5)) == opaque, img.mode
    values = [0, 128, 129, 32896, 65406, 65407, 65535]   # 128/257 rounds down, 129/257 up; 65407/257 is 254.502
    grey = Image.fromarray(np.repeat(np.array([values], dtype=np.uint16), 4, axis=0))
    got, source = ART.decode(as_png(grey), "test picture")
    assert source["format"] == "PNG" and [got.getpixel((x, 2)) for x in range(len(values))] == [
        (v, v, v) for v in (0, 0, 1, 128, 254, 255, 255)]


def test_a_16_bit_grey_is_scaled_without_big_arrays():
    """As float64 arrays, a 64 MP 16-bit grey took 2 GB; scaled by Pillow's table it takes none. tracemalloc sees
    numpy's arrays and Python's objects (not Pillow's own image memory): under a byte a pixel here."""
    data = as_png(Image.fromarray(np.full((2000, 2000), 32896, dtype=np.uint16)))
    tracemalloc.start()
    try:
        img, _ = ART.decode(data, "test picture")
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert img.getpixel((5, 5)) == (128, 128, 128) and peak < 2000 * 2000, peak


def test_the_same_inputs_give_byte_identical_files(tmp_path):
    song = with_picture(tone(tmp_path / "t.flac"), tmp_path / "pictured.flac",
                        write(tmp_path / "cover.jpg", picture((640, 400), "JPEG")))
    bg = write(tmp_path / "bg.jpg", exif_jpeg((2600, 1500), 1))
    first = ART.prepare(song, background=bg)
    again = ART.prepare(song, background=bg)
    assert set(first.files) == {"album.jpg", "background.jpg"} and first.files == again.files
    assert first.record == again.record
    assert ART.JPEG_SETTINGS == {"quality": 90, "subsampling": 2, "optimize": False, "progressive": False}


# ------------------------------------------------------------------------------------------------ what is refused

def bad_images(tmp_path: Path) -> list[tuple[Path, str]]:
    """Given images that must be refused, each with the words of its error."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    gif = io.BytesIO()
    Image.new("RGB", (40, 40), RED).save(gif, "GIF")
    bmp = io.BytesIO()
    Image.new("RGB", (40, 40), RED).save(bmp, "BMP")
    big = tmp_path / "huge.jpg"
    with open(big, "wb") as f:   # sparse: no disk used
        f.truncate(ART.MAX_BYTES + 1)
    wide = io.BytesIO()
    Image.new("1", (8001, 8000)).save(wide, "PNG")   # 64.008 megapixels, a few KB
    bomb = io.BytesIO()
    Image.new("1", (13500, 13500)).save(bomb, "PNG")   # past Pillow's own decompression-bomb limit
    cut = picture((600, 600), "JPEG")
    return [(write(tmp_path / "notes.jpg", b"just some text, not a picture"), "is not a JPEG, PNG or WebP image"),
            (write(tmp_path / "anim.gif", gif.getvalue()), "is not a JPEG, PNG or WebP image"),
            (write(tmp_path / "bitmap.png", bmp.getvalue()), "is not a JPEG, PNG or WebP image"),
            (tmp_path / "nowhere.png", "nowhere.png does not exist"),
            (tmp_path, f"{tmp_path.name} is not a file"),
            (big, "is 20.0 MB, over the limit of 20 MB"),
            (write(tmp_path / "wide.png", wide.getvalue()), "is 8001x8000, 64.0 megapixels, over the limit of 64 "
                                                            "megapixels"),
            (write(tmp_path / "bomb.png", bomb.getvalue()), "over the limit of 64 megapixels"),
            (write(tmp_path / "cut.jpg", cut[:len(cut) // 3]), "could not be decoded")]


def test_a_bad_or_oversized_given_image_is_an_input_error(tmp_path):
    song = tone(tmp_path / "t.flac")
    for path, words in bad_images(tmp_path / "bad"):
        for key in ("album_art", "background"):
            with pytest.raises(InputError, match=None) as e:
                ART.prepare(song, **{key: path})
            assert words in str(e.value) and str(e.value).startswith(f"the {ART.WHAT[key]} {path.name}"), str(e.value)
            assert str(path.parent) not in str(e.value)   # its name only, never where it is


def test_an_embedded_picture_that_fails_is_a_warning(tmp_path):
    mp3 = tone(tmp_path / "plain.mp3", "libmp3lame")
    gif = io.BytesIO()
    Image.new("RGB", (40, 40), RED).save(gif, "GIF")
    flac = with_picture(tone(tmp_path / "t.flac"), tmp_path / "pictured.flac",
                        write(tmp_path / "c.png", picture((300, 300))))
    data = bytearray(flac.read_bytes())
    at = data.index(b"\x89PNG\r\n\x1a\n")
    data[at + 8:at + 40] = b"X" * 32   # the PNG's header chunk broken: the audio as it was
    broken = write(tmp_path / "broken.flac", bytes(data))
    for song in (id3_mp3(tmp_path / "gif.mp3", mp3, ("image/gif", gif.getvalue(), 3)),
                 id3_mp3(tmp_path / "junk.mp3", mp3, ("image/jpeg", b"not a picture" * 20, 3)), broken):
        got = ART.prepare(song)
        assert got.files == {} and got.warnings == [
            "album art: the song file's picture is not a JPEG, PNG or WebP image: no album art"], song.name
        assert got.record["album_art"] == {"added": False, "from": None,
                                           "why": "the song file's picture is not a JPEG, PNG or WebP image"}


def test_without_pillow_a_given_image_is_a_tool_error_and_an_embedded_one_a_warning(tmp_path, monkeypatch):
    song = with_picture(tone(tmp_path / "t.flac"), tmp_path / "pictured.flac",
                        write(tmp_path / "c.png", picture((300, 300))))
    given = write(tmp_path / "c2.png", picture((300, 300)))
    monkeypatch.setitem(sys.modules, "PIL", None)
    with pytest.raises(ToolError, match="need Pillow: pip install pillow"):
        ART.prepare(song, background=given)
    got = ART.prepare(song)
    assert got.files == {} and got.warnings == [f"album art: the song file's picture is not used: {ART.PILLOW}: no "
                                                "album art"]
    assert ART.prepare(tone(tmp_path / "plain.flac")).warnings == []   # no picture: nothing to say


# ------------------------------------------------------------------------------------------------ assemble

def test_assembles_config_takes_a_background(tmp_path):
    base = {"audio": "a.wav", "parts": [{"instrument": "bass", "source": "b.chart"}], "output": "out",
            "metadata": {"name": "n", "artist": "a", "album": "b", "genre": "g", "year": "2001"}}
    cfg = parse_config({**base, "album_art": "art/album.jpg", "background": "art/background.jpg"}, tmp_path)
    assert cfg.album_art == tmp_path / "art" / "album.jpg" and cfg.background == tmp_path / "art" / "background.jpg"
    assert parse_config(base, tmp_path).background is None
    for bad in ("bg.gif", "bg.webp", 3):
        with pytest.raises(InputError, match="background"):
            parse_config({**base, "background": bad}, tmp_path)


# ------------------------------------------------------------------------------------------------ the pipeline

@pytest.fixture(scope="module")
def songs(tmp_path_factory):
    """test_pipeline's song as a FLAC, the same with an embedded picture (a wide one, so it is cropped), and a work
    folder all the runs here share (one song's samples: its decode and stand-in engines are made once)."""
    root = tmp_path_factory.mktemp("art")
    write_song(root / "song.flac")
    with_picture(root / "song.flac", root / "pictured.flac", write(root / "cover.png", picture((900, 600))))
    return root


def chart_it(songs, song: str, out: Path, *extra: str, capsys=None) -> tuple[int, str, str]:
    code = main(["chart", str(songs / song), "--out", str(out), "--work", str(songs / "work"), "--instruments",
                 "bass,drums", *extra])
    got = capsys.readouterr() if capsys is not None else None
    return code, got.out if got else "", got.err if got else ""


def test_the_song_folder_gets_the_art_and_nothing_else_changes(songs, tmp_path, monkeypatch, capsys):
    """album.jpg from the song file's picture and background.jpg from the image given: the gate passes, scan-chart no
    longer reports noAlbumArt, and notes.chart and song.ini are byte for byte the chart made without them. The
    records say where each came from and hold no path of the person's; a second run gives the same bytes; a given
    album art wins; a later build without a background takes the earlier one away."""
    monkeypatch.setattr(P, "Engines", standins())
    photos = tmp_path / "My Made-Up Photos"
    bg = write(photos / "bg.jpg", exif_jpeg((2400, 1350), 1))
    code, out, err = chart_it(songs, "song.flac", tmp_path / "A", capsys=capsys)
    assert code == 0, err
    plain = tmp_path / "A"
    assert sorted(p.name for p in plain.iterdir()) == ["notes.chart", "report.json", "song.ini", "song.ogg"]
    assert "art: " not in out
    code, out, err = chart_it(songs, "pictured.flac", tmp_path / "B", "--background", str(bg), capsys=capsys)
    assert code == 0, err
    built = tmp_path / "B"
    assert sorted(p.name for p in built.iterdir()) == ["album.jpg", "background.jpg", "notes.chart", "report.json",
                                                       "song.ini", "song.ogg"]
    assert opened((built / "album.jpg").read_bytes()).size == (512, 512)
    assert opened((built / "background.jpg").read_bytes()).size == (1920, 1080)
    assert not any(m in (built / "background.jpg").read_bytes() for m in NO_METADATA)
    for name in ("notes.chart", "song.ini"):
        assert (built / name).read_bytes() == (plain / name).read_bytes(), name
    assert "art: album.jpg (the song file), background.jpg (given)" in out.splitlines()
    report = json.loads((built / "report.json").read_text(encoding="utf-8"))
    assert report["gate"]["ok"]
    assert report["art"]["album_art"] == {"added": True, "file": "album.jpg", "from": "embedded", "width": 512,
                                          "height": 512, "bytes": (built / "album.jpg").stat().st_size,
                                          "source": {"format": "PNG", "width": 900, "height": 600}}
    assert report["art"]["background"]["from"] == "given" and report["art"]["background"]["file"] == "background.jpg"
    if find_scan_chart()[0] is not None:
        assert "noAlbumArt" not in report["gate"]["scan_chart"]["folder_issues"]
        before = json.loads((plain / "report.json").read_text(encoding="utf-8"))
        assert "noAlbumArt" in before["gate"]["scan_chart"]["folder_issues"]
        assert before["art"]["album_art"] == {"added": False, "file": None, "from": None,
                                              "why": "no album art given, and the song file has no picture"}
    work = songs / "work"
    pipeline = json.loads((work / "pipeline.json").read_text(encoding="utf-8"))
    assert pipeline["options"]["album_art"] is False and pipeline["options"]["background"] is True
    assert pipeline["art"]["album_art"]["from"] == "embedded" and pipeline["art"]["background"]["from"] == "given"
    cfg = json.loads((work / "assemble.json").read_text(encoding="utf-8"))
    assert cfg["album_art"] == str(work / "art" / "album.jpg") and cfg["background"] == str(work / "art" /
                                                                                           "background.jpg")
    for record in (work / "pipeline.json", work / "assemble.json", built / "report.json"):
        assert photos.name not in record.read_text(encoding="utf-8"), record   # no path of the person's
    # the same song and image: the same bytes
    code, _, err = chart_it(songs, "pictured.flac", tmp_path / "C", "--background", str(bg), capsys=capsys)
    assert code == 0, err
    for name in ("album.jpg", "background.jpg"):
        assert (tmp_path / "C" / name).read_bytes() == (built / name).read_bytes(), name
    # a given album art wins over the song file's; built again without a background, the old one goes
    mine = write(photos / "mine.png", picture((500, 500), centre=GREEN, band=GREEN))
    code, out, err = chart_it(songs, "pictured.flac", built, "--album-art", str(mine), capsys=capsys)
    assert code == 0, err
    assert sorted(p.name for p in built.iterdir()) == ["album.jpg", "notes.chart", "report.json", "song.ini",
                                                       "song.ogg"]
    assert near(opened((built / "album.jpg").read_bytes()).getpixel((256, 256)), GREEN)
    assert "art: album.jpg (given)" in out.splitlines()
    pipeline = json.loads((work / "pipeline.json").read_text(encoding="utf-8"))
    assert pipeline["options"]["album_art"] is True and pipeline["art"]["album_art"]["from"] == "given"
    assert not (work / "art" / "background.jpg").exists()


def test_a_bad_given_image_is_exit_2_before_any_work(songs, tmp_path, monkeypatch, capsys):
    engines = standins()
    monkeypatch.setattr(P, "Engines", engines)
    for path, words in bad_images(tmp_path / "bad"):
        for flag in ("--album-art", "--background"):
            code = main(["chart", str(songs / "song.flac"), "--out", str(tmp_path / "X"), "--work", str(tmp_path / "w"),
                         flag, str(path)])
            err = capsys.readouterr().err
            assert code == 2 and words in err and err.startswith("songcharter: error: the "), (flag, path, err)
    assert engines.calls == [] and not (tmp_path / "X").exists() and not (tmp_path / "w").exists()


def test_an_embedded_picture_that_fails_warns_and_the_chart_goes_on(songs, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(P, "Engines", standins())
    data = bytearray((songs / "pictured.flac").read_bytes())
    at = data.index(b"\x89PNG\r\n\x1a\n")
    data[at + 8:at + 40] = b"X" * 32
    write(songs / "broken.flac", bytes(data))
    code, out, err = chart_it(songs, "broken.flac", tmp_path / "D", "--events", capsys=capsys)
    assert code == 0, err
    warning = "album art: the song file's picture is not a JPEG, PNG or WebP image: no album art"
    assert f"songcharter: warning: {warning}" in err.splitlines()
    events = [json.loads(x[len("@@songcharter "):]) for x in err.splitlines() if x.startswith("@@songcharter ")]
    assert {"event": "warning", "text": warning} in events   # the page lists it with the others
    assert not (tmp_path / "D" / "album.jpg").exists()
    record = json.loads((songs / "work" / "pipeline.json").read_text(encoding="utf-8"))
    assert warning in record["warnings"] and record["art"]["album_art"]["added"] is False
