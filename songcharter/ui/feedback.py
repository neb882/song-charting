"""The friend's word on each chart (M8-14, DESIGN.md 4.5): how it played, 1 to 5, and the spots he marks, kept with
the chart and sent back in the diagnostics zip.

    record = feedback.read(home, chart_id, folder)            # {"chart", "rating", "spots", ...}; an empty one first
    record = feedback.change(home, chart_id, body, length=245.3, notes=sha)   # an InputError for a bad body
    feedback.for_diagnostics(home, find)                      # every chart's, with its report.json's `pipeline`
                                                              # and the guitar's notes around each spot

  * **Where:** <home>/state/feedback/<24 hex>.json, the hex the SHA-256 of the chart's library id (jobs.LIBRARY_ID:
    `<16 hex>:<name>[:v<N>]`, which the record holds), so no name of a song is made into a file's name. Not in the
    song folder, which Install copies into Clone Hero. Written whole, through a temporary file; a re-chart never
    writes it (a new version is a new chart, with its own), and nothing deletes it: a chart deleted in Windows keeps
    its record, which the diagnostics still send.
  * **What:** `rating` (1 to 5, or None: optional, and changeable, and taken back with None); `spots`, at most
    SPOTS_MAX, each {"id" (8 hex), "at" (whole seconds of the song as Clone Hero plays it), "reasons" (one or more of
    REASONS, in their order), "note" (his own words, at most NOTE_MAX characters, kept as he wrote them; None
    without)}; `notes_sha` (the first 16 hex of the SHA-256 of the chart's notes.chart when he last changed the record:
    which chart he rated, should the folder be charted again); `updated` (the time); `earlier` (below).
  * **A chart made again into the same folder** (a plain chart of the song with other options: a seed 0's folder is
    the same whatever its options, jobs.output_folder; the advisor's 1): the rating and spots given to the chart
    before are not this one's. Read with its folder (`read`, `as_now`), a record whose notes_sha is not the folder's
    notes.chart now reads as none yet, with the earlier one's rating and spot count for the page's line ("You rated
    an earlier chart of this song ..."); the first change then saves it that way: the earlier rating and spots go to
    `earlier` (newest first, at most EARLIER_MAX, each with its notes_sha and updated), and a chart charted back to
    one rated before gets its own again from there. Nothing he gave is deleted but past EARLIER_MAX.
  * **The checks** (`change`): a body is {"rating": 1-5 or null}, {"add": {"at": "m:ss", "reasons": [...], "note":
    "..."}} or {"remove": <a spot's id>}; `at` within the song (`length`, the song.ogg's seconds: the song and the
    lead-in, which Clone Hero's clock counts); anything else is an InputError in plain words.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from ..errors import InputError

FOLDER = ("state", "feedback")    # <home>/state/feedback
# the reasons a spot can have, in the page's order, with its words (the brief's list; "great part": praise is data too)
REASONS = {"too_many_chords": "Too many chords", "missing_notes": "Missing notes", "extra_notes": "Extra notes",
           "off_beat": "Off the beat", "hard_to_read": "Hard to read", "great": "Great part"}
RATINGS = range(1, 6)
NOTE_MAX = 300                    # a note's characters at most
SPOTS_MAX = 50                    # spots a chart at most [judgement: far more than a song has bad spots]
EARLIER_MAX = 5                   # earlier charts' ratings a record keeps, the newest [judgement: a few re-charts]
EARLIER_KEYS = ("rating", "spots", "notes_sha", "updated")   # what an `earlier` entry keeps
TIME = re.compile(r"^\s*(\d{1,3}):([0-5][0-9])\s*$")   # m:ss
MAX_AT = 999 * 60 + 59            # the latest time m:ss can write: a number past it is no time either
_lock = threading.Lock()          # one change at a time (the server's request threads)
# a spot's notes in feedback.json (the gate advisor's 3: the owner's GPU may not chart the friend's chart again)
AROUND_S = 10                     # the Expert guitar's notes this many seconds before a spot to as many after
AROUND_NOTES = 400                # at most this many a spot, the nearest it [judgement: 20 notes a second for 20 s]
AROUND_TOTAL = 10000              # and in the whole file: about 2 MB at about 200 bytes a note as written, under
                                  # diagnostics.MAX_BYTES (5 MB) with room for the rest [tests/test_ui_feedback.py]


def folder(home: Path) -> Path:
    return Path(home).joinpath(*FOLDER)


def path_for(home: Path, chart: str) -> Path:
    """The record's file: <home>/state/feedback/<the first 24 hex of the SHA-256 of the chart's id>.json."""
    return folder(home) / (hashlib.sha256(chart.encode("utf-8")).hexdigest()[:24] + ".json")


def empty(chart: str) -> dict:
    return {"version": 1, "chart": chart, "rating": None, "spots": [], "notes_sha": None, "updated": None,
            "earlier": []}


def _valid(record: Any, chart: str | None = None) -> bool:
    return (isinstance(record, dict) and isinstance(record.get("chart"), str)
            and (chart is None or record["chart"] == chart) and isinstance(record.get("spots"), list))


def _spot_ok(x: Any) -> bool:
    """A saved spot that reads as one: an object with its id, a time that is a number from 0 to MAX_AT, its reasons as
    text and its note as text or None (a damaged one is left out where it is read: the review's F5). The bounds alone
    refuse NaN and the infinities; math.isfinite would raise on a whole number too long for a float (R2)."""
    at = x.get("at") if isinstance(x, dict) else None
    return (isinstance(x, dict) and isinstance(x.get("id"), str) and isinstance(at, (int, float))
            and not isinstance(at, bool) and 0 <= at <= MAX_AT and isinstance(x.get("reasons"), list)
            and all(isinstance(r, str) for r in x["reasons"]) and (x.get("note") is None or isinstance(x["note"], str)))


def _whole(record: dict, chart: str) -> dict:
    """A record as read: the empty record's keys, then its own, its damaged spots left out (its earlier ones' too)."""
    earlier = record.get("earlier") if isinstance(record.get("earlier"), list) else []
    return {**empty(chart), **record, "spots": [x for x in record["spots"] if _spot_ok(x)],
            "earlier": [{**{k: e.get(k) for k in EARLIER_KEYS}, "spots": [x for x in e["spots"] if _spot_ok(x)]}
                        for e in earlier if isinstance(e, dict) and isinstance(e.get("spots"), list)]}


def as_now(record: dict, notes: str | None) -> dict:
    """The record of the chart in the folder now (`notes`: its notes_id; the module docstring): itself, unless its
    notes_sha is another chart's: then its rating and spots (if any) go first in `earlier`, and the chart has its own
    from there (an earlier entry of its notes_sha), else none yet. Either identity unknown: itself."""
    sha = record.get("notes_sha")
    if not isinstance(notes, str) or not isinstance(sha, str) or sha == notes:
        return record
    earlier = ([{k: record.get(k) for k in EARLIER_KEYS}] if rated(record) else []) + record["earlier"]
    own = next((e for e in earlier if e.get("notes_sha") == notes), {"notes_sha": notes})
    return {**record, "rating": None, "spots": [], "updated": None, **own,
            "earlier": [e for e in earlier if e is not own][:EARLIER_MAX]}


def read(home: Path, chart: str, folder: Path | None = None) -> dict:
    """The chart's record, or an empty one (none yet, or a file that does not read as one: never an error); a spot
    that does not read as one is left out, the others kept (F5). With the chart's `folder`, as it stands for the
    notes.chart there now (as_now)."""
    try:
        record = json.loads(path_for(home, chart).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty(chart)
    record = _whole(record, chart) if _valid(record, chart) else empty(chart)
    return record if folder is None or record["notes_sha"] is None else as_now(record, notes_id(folder))


def _write(home: Path, record: dict) -> None:
    path = path_for(home, record["chart"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.part")
    try:
        tmp.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def mmss(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 60}:{s % 60:02d}"


def parse_time(value: Any, length: float | None) -> int:
    """A spot's time: "m:ss" (or whole seconds as a number), within the song's `length` (seconds; None: unknown, not
    checked); an InputError in plain words otherwise."""
    if isinstance(value, str):
        m = TIME.match(value)
        if m is None:
            shown = value.strip()[:20] or "nothing"
            raise InputError(f"{shown} is not a time: write minutes and seconds, such as 2:28")
        at = int(m[1]) * 60 + int(m[2])
    elif isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= MAX_AT:
        at = int(value)
    else:   # not a number, a bool, NaN, infinite (JSON's 1e400), negative or past m:ss (F5), a whole number too long
        # for a float among them: the bounds alone refuse NaN and the infinities, and never overflow (R2)
        raise InputError("the time is minutes and seconds, such as 2:28")
    if length is not None and at > length:
        raise InputError(f"{mmss(at)} is after the song's end ({mmss(length)})")
    return at


def _reasons(value: Any) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(r, str) for r in value):
        raise InputError("choose at least one reason for the spot")
    unknown = [r for r in value if r not in REASONS]
    if unknown:
        raise InputError(f"{unknown[0][:40]!r} is not a reason (the reasons: {', '.join(REASONS)})")
    return [r for r in REASONS if r in value]


def _note(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InputError("the note is text")
    if len(value) > NOTE_MAX:
        raise InputError(f"the note is {len(value)} characters: at most {NOTE_MAX}")
    return value if value.strip() else None


def change(home: Path, chart: str, body: Mapping[str, Any], length: float | None,
           notes: str | None = None, now: Callable[[], float] = time.time) -> dict:
    """Apply one change to the chart's record and save it (the module docstring): the record. `length`: the song's
    seconds as Clone Hero plays it (None: not checked); `notes`: the chart's notes.chart identity, recorded with the
    change (a record of another chart's starts afresh first: as_now)."""
    if not isinstance(body, Mapping):
        raise InputError("the request body is a JSON object")
    kinds = [k for k in ("rating", "add", "remove") if k in body]
    if len(kinds) != 1:
        raise InputError("give one of rating, add or remove")
    with _lock:
        record = as_now(read(home, chart), notes)
        if kinds == ["rating"]:
            rating = body["rating"]
            if rating is not None and (isinstance(rating, bool) or rating not in RATINGS):
                raise InputError("the rating is 1 to 5")
            record["rating"] = rating
        elif kinds == ["add"]:
            spot = body["add"]
            if not isinstance(spot, Mapping):
                raise InputError("a spot is a time and its reasons")
            if len(record["spots"]) >= SPOTS_MAX:
                raise InputError(f"this chart has {SPOTS_MAX} spots marked already")
            record["spots"] = sorted(record["spots"] + [{
                "id": secrets.token_hex(4), "at": parse_time(spot.get("at"), length),
                "reasons": _reasons(spot.get("reasons")), "note": _note(spot.get("note"))}],
                key=lambda x: (x.get("at", 0), x.get("id", "")))
        else:
            gone = body["remove"]
            kept = [x for x in record["spots"] if x.get("id") != gone]
            if not isinstance(gone, str) or len(kept) == len(record["spots"]):
                raise InputError("no such spot")
            record["spots"] = kept
        # a notes.chart that cannot be read now keeps the sha of the chart rated: None would give its rating and
        # spots to the next chart in the folder (the gate review's F1)
        record.update(version=1, notes_sha=notes if notes is not None else record["notes_sha"],
                      updated=round(now(), 3))
        _write(home, record)
        return record


def public(record: Mapping[str, Any], length: float | None) -> dict:
    """GET and POST /api/jobs/<id>/feedback's answer: the record's rating and spots (each with its time as m:ss), the
    song's length and the reasons' words, for the page; `earlier`, while this chart has neither, the newest earlier
    chart's rating and spot count (the box's line says he rated an earlier chart), else None."""
    spots = [{"id": x.get("id"), "at": x.get("at"), "time": mmss(x.get("at") or 0), "reasons": x.get("reasons") or [],
              "note": x.get("note")} for x in record.get("spots") or [] if isinstance(x, dict)]
    earlier = record.get("earlier") or []
    return {"chart": record.get("chart"), "rating": record.get("rating"), "spots": spots,
            "earlier": summary(earlier[0]) if earlier and not rated(record) else None,
            "length": None if length is None else round(length, 1),
            "reasons": [{"id": k, "words": v} for k, v in REASONS.items()], "note_max": NOTE_MAX}


def summary(record: Mapping[str, Any]) -> dict:
    """What "Your charts" shows of a record: its rating and how many spots."""
    return {"rating": record.get("rating"), "spots": len(record.get("spots") or [])}


def all_records(home: Path) -> list[dict]:
    """Every record in <home>/state/feedback (those that read as one), by chart id."""
    out = []
    try:
        files = sorted(folder(home).glob("*.json"))
    except OSError:
        return []
    for f in files:
        try:
            record = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if _valid(record) and f == path_for(home, record["chart"]):
            out.append(_whole(record, record["chart"]))
    return sorted(out, key=lambda r: r["chart"])


def rated(record: Mapping[str, Any]) -> bool:
    return record.get("rating") is not None or bool(record.get("spots"))


def notes_id(folder_path: Path) -> str | None:
    """A chart's notes.chart identity: the first 16 hex of its SHA-256 (no word of it), None when it cannot be read."""
    try:
        return hashlib.sha256((Path(folder_path) / "notes.chart").read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def guitar_notes(folder: Path) -> tuple[dict | None, str | None]:
    """The chart's Expert guitar as numbers, read as Clone Hero plays it (importers.read_chart with the folder's
    song.ini settings), for the spots in feedback.json: ({"resolution", "tempos": [{"tick", "bpm", "s"}], "notes":
    [{"s", "tick", "frets", "open", "kind", "sustain"}]}, None), or (None, why). Seconds from the chart's tick 0 (its
    Offset and the ini's delay, both 0 in songcharter's charts): song.ogg's, the lead-in in it (assemble puts every
    input second t at t + pad_seconds on the map), the clock of a spot's `at`. No text of the chart: not its
    [Events] (the lyrics, the sections), not its names."""
    from .. import importers
    from ..timed import OPEN
    path = Path(folder) / "notes.chart"
    try:
        raw = importers._parse_chart(importers._decode(path.read_bytes()))   # the resolution and the tempo map
        ini = Path(folder) / "song.ini"
        mods = importers.read_ini_modifiers(ini) if ini.is_file() else importers.ChartModifiers()
        part = importers.read_chart(path, modifiers=mods).parts.get(("guitar", "expert"))
    except Exception as e:  # noqa: BLE001  a chart that does not read: its spots go without notes, said why
        return None, f"its notes.chart could not be read as a chart ({type(e).__name__})"
    if part is None or not part.notes:
        return None, "the chart has no Expert guitar part"
    clock = importers._Clock(raw.resolution, raw.tempos)
    offset = mods.delay_ms / 1000 if mods.delay_ms else raw.offset

    def tick(seconds: float) -> int:   # _Clock.ms turned round: a note's tick from its time
        ms = (seconds - offset) * 1000
        i = max(bisect.bisect_right(clock.ms_at, ms) - 1, 0)
        return round(clock.ticks[i] + (ms - clock.ms_at[i]) * clock.bpms[i] * clock.resolution / 60000)

    notes = []
    for n in part.notes:
        t = tick(n.time)
        notes.append({"s": round(n.time, 3), "tick": t, "frets": [f for f in n.frets if f != OPEN],
                      "open": OPEN in n.frets, "kind": "tap" if n.tap else "hopo" if n.hopo else "strum",
                      "sustain": 0 if n.end is None else tick(n.end) - t})
    tempos = [{"tick": t, "bpm": bpm, "s": round(clock.ms(t) / 1000 + offset, 3)} for t, bpm in raw.tempos]
    return {"resolution": raw.resolution, "tempos": tempos, "notes": notes}, None


def around(guitar: Mapping[str, Any], at: float, left: list[int]) -> dict:
    """A spot's `around` in feedback.json: the notes from AROUND_S before `at` to AROUND_S after, the nearest
    AROUND_NOTES of them and no more than left[0] (the file's budget, taken from it), with the chart's resolution and
    the tempo markers there (the one in force at the start first); how many were left out, and why."""
    lo, hi = max(0.0, at - AROUND_S), at + AROUND_S
    near = [n for n in guitar["notes"] if lo <= n["s"] <= hi]
    room = min(AROUND_NOTES, left[0])
    kept = sorted(sorted(near, key=lambda n: abs(n["s"] - at))[:room], key=lambda n: n["s"])
    left[0] -= len(kept)
    tempos = guitar["tempos"]
    first = max((i for i, t in enumerate(tempos) if t["s"] <= lo), default=0)
    out = {"from_s": lo, "to_s": hi, "resolution": guitar["resolution"],
           "tempos": [t for i, t in enumerate(tempos) if i == first or lo < t["s"] <= hi], "notes": kept,
           "left_out": len(near) - len(kept)}
    if out["left_out"]:
        out["why"] = (f"at most {AROUND_NOTES} notes a spot: the nearest kept" if room == AROUND_NOTES else
                      f"at most {AROUND_TOTAL} notes in this file, reached")
    return out


def for_diagnostics(home: Path, find: Callable[[Path, str], Path | None]) -> dict:
    """feedback.json in the diagnostics zip: every chart's record that holds a rating or a spot, with the chart as it
    is now (`now`: whether its folder is still in the library, its notes.chart identity, the gate's verdict, the
    song's length and its report.json's `pipeline`: the seeds, takes, devices, fallbacks and engines, so a spot can be
    reproduced), and no path: the chart is named by its library id. `find` is jobs.find_chart. A spot's note is his
    own words, as he wrote them. The record as it stands for the chart there now (as_now): a rating given to an
    earlier chart in its folder is in `earlier`, with that chart's notes_sha. Each spot of the chart rated (its
    notes_sha the one there now) has `around`: the guitar's notes about it (guitar_notes, around; the gate advisor's
    3), or why none."""
    charts, left = [], [AROUND_TOTAL]
    for record in all_records(home):
        if not rated(record) and not record["earlier"]:
            continue
        where = find(Path(home), record["chart"])
        now: dict[str, Any] = {"there": where is not None}
        if where is not None:
            try:
                report = json.loads((where / "report.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                report = None
            report = report if isinstance(report, dict) else {}
            gate = report.get("gate") if isinstance(report.get("gate"), dict) else {}
            now.update(notes_sha=notes_id(where), ok=gate.get("ok"), length=song_length(report),
                       pipeline=report.get("pipeline"))
            record = as_now(record, now["notes_sha"])
        guitar, why = (None, "the chart's folder is not there any more") if where is None else (
            (None, "these spots were marked on another notes.chart than the one there now")
            if record["notes_sha"] != now["notes_sha"] else (None, None))
        spots = []
        for spot in record["spots"]:
            if guitar is None and why is None:   # read once a chart, for its first spot
                guitar, why = guitar_notes(where)
            spots.append({**spot, "around": {"why": why} if guitar is None else around(guitar, spot["at"], left)})
        charts.append({k: record.get(k) for k in ("chart", "rating", "notes_sha", "updated", "earlier")}
                      | {"spots": spots, "now": now})
    return {"about": "Each chart's rating (1 to 5) and the spots marked on it, with the chart's record (its "
                     "report.json's pipeline: seeds, takes, devices, fallbacks, engines). A spot's `at` is seconds "
                     "of the song as Clone Hero plays it (with the lead-in); its note is the player's own words. "
                     "`earlier`: the ratings and spots given to an earlier chart made into the same folder (charted "
                     "again with other options), each with that chart's notes_sha, the newest first. A spot's "
                     f"`around`: the chart's Expert guitar notes from {AROUND_S} s before it to {AROUND_S} s after, "
                     "as numbers only (s: seconds on the clock of `at`; tick; frets 0 to 4, green to orange; open; "
                     "kind: strum, hopo or tap; sustain in ticks), with the chart's resolution and its tempo "
                     "markers there (the one in force at the start first); never a word of the chart. At most "
                     f"{AROUND_NOTES} notes a spot (the nearest) and {AROUND_TOTAL} in this file: `left_out` and "
                     "`why` say so; `why` alone when there are none. An `earlier` chart's spots have no `around`: "
                     "that chart is not there now.",
            "reasons": REASONS, "charts": charts}


def song_length(report: Mapping[str, Any]) -> float | None:
    """The song's seconds as Clone Hero plays it, from a chart's report.json: the decode's length and the lead-in
    (report.json's audio.duration and lead_in.pad_seconds); None when it does not say."""
    audio = report.get("audio") if isinstance(report.get("audio"), dict) else {}
    lead = report.get("lead_in") if isinstance(report.get("lead_in"), dict) else {}
    duration, pad = audio.get("duration"), lead.get("pad_seconds", 0.0)
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
        return None
    pad = pad if isinstance(pad, (int, float)) and not isinstance(pad, bool) and pad >= 0 else 0.0
    return round(float(duration) + float(pad), 3)
