"""The friend's word on each chart (M8-14, DESIGN.md 4.5): how it played, 1 to 5, and the spots he marks, kept with
the chart and sent back in the diagnostics zip.

    record = feedback.read(home, chart_id)                    # {"chart", "rating", "spots", ...}; an empty one first
    record = feedback.change(home, chart_id, body, length=245.3, notes=sha)   # an InputError for a bad body
    feedback.for_diagnostics(home, find)                      # every chart's, with its report.json's `pipeline`

  * **Where:** <home>/state/feedback/<24 hex>.json, the hex the SHA-256 of the chart's library id (jobs.LIBRARY_ID:
    `<16 hex>:<name>[:v<N>]`, which the record holds), so no name of a song is made into a file's name. Not in the
    song folder, which Install copies into Clone Hero. Written whole, through a temporary file; a re-chart never
    writes it (a new version is a new chart, with its own), and nothing deletes it: a chart deleted in Windows keeps
    its record, which the diagnostics still send.
  * **What:** `rating` (1 to 5, or None: optional, and changeable, and taken back with None); `spots`, at most
    SPOTS_MAX, each {"id" (8 hex), "at" (whole seconds of the song as Clone Hero plays it), "reasons" (one or more of
    REASONS, in their order), "note" (his own words, at most NOTE_MAX characters, kept as he wrote them; None
    without)}; `notes_sha` (the first 16 hex of the SHA-256 of the chart's notes.chart when he last changed the record:
    which chart he rated, should the folder be charted again with the same seed); `updated` (the time).
  * **The checks** (`change`): a body is {"rating": 1-5 or null}, {"add": {"at": "m:ss", "reasons": [...], "note":
    "..."}} or {"remove": <a spot's id>}; `at` within the song (`length`, the song.ogg's seconds: the song and the
    lead-in, which Clone Hero's clock counts); anything else is an InputError in plain words.
"""
from __future__ import annotations

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
TIME = re.compile(r"^\s*(\d{1,3}):([0-5][0-9])\s*$")   # m:ss
MAX_AT = 999 * 60 + 59            # the latest time m:ss can write: a number past it is no time either
_lock = threading.Lock()          # one change at a time (the server's request threads)


def folder(home: Path) -> Path:
    return Path(home).joinpath(*FOLDER)


def path_for(home: Path, chart: str) -> Path:
    """The record's file: <home>/state/feedback/<the first 24 hex of the SHA-256 of the chart's id>.json."""
    return folder(home) / (hashlib.sha256(chart.encode("utf-8")).hexdigest()[:24] + ".json")


def empty(chart: str) -> dict:
    return {"version": 1, "chart": chart, "rating": None, "spots": [], "notes_sha": None, "updated": None}


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
    """A record as read: the empty record's keys, then its own, its damaged spots left out."""
    return {**empty(chart), **record, "spots": [x for x in record["spots"] if _spot_ok(x)]}


def read(home: Path, chart: str) -> dict:
    """The chart's record, or an empty one (none yet, or a file that does not read as one: never an error); a spot
    that does not read as one is left out, the others kept (F5)."""
    try:
        record = json.loads(path_for(home, chart).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty(chart)
    return _whole(record, chart) if _valid(record, chart) else empty(chart)


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
    change."""
    if not isinstance(body, Mapping):
        raise InputError("the request body is a JSON object")
    kinds = [k for k in ("rating", "add", "remove") if k in body]
    if len(kinds) != 1:
        raise InputError("give one of rating, add or remove")
    with _lock:
        record = read(home, chart)
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
        record.update(version=1, notes_sha=notes, updated=round(now(), 3))
        _write(home, record)
        return record


def public(record: Mapping[str, Any], length: float | None) -> dict:
    """GET and POST /api/jobs/<id>/feedback's answer: the record's rating and spots (each with its time as m:ss), the
    song's length and the reasons' words, for the page."""
    spots = [{"id": x.get("id"), "at": x.get("at"), "time": mmss(x.get("at") or 0), "reasons": x.get("reasons") or [],
              "note": x.get("note")} for x in record.get("spots") or [] if isinstance(x, dict)]
    return {"chart": record.get("chart"), "rating": record.get("rating"), "spots": spots,
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


def for_diagnostics(home: Path, find: Callable[[Path, str], Path | None]) -> dict:
    """feedback.json in the diagnostics zip: every chart's record that holds a rating or a spot, with the chart as it
    is now (`now`: whether its folder is still in the library, its notes.chart identity, the gate's verdict, the
    song's length and its report.json's `pipeline`: the seeds, takes, devices, fallbacks and engines, so a spot can be
    reproduced), and no path: the chart is named by its library id. `find` is jobs.find_chart. A spot's note is his
    own words, as he wrote them."""
    charts = []
    for record in all_records(home):
        if not rated(record):
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
        charts.append({k: record.get(k) for k in ("chart", "rating", "spots", "notes_sha", "updated")} | {"now": now})
    return {"about": "Each chart's rating (1 to 5) and the spots marked on it, with the chart's record (its "
                     "report.json's pipeline: seeds, takes, devices, fallbacks, engines). A spot's `at` is seconds "
                     "of the song as Clone Hero plays it (with the lead-in); its note is the player's own words.",
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
