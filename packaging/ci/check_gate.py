#!/usr/bin/env python3
"""check_gate.py: did `songcharter chart` build a playable song folder that passed its own gate?

    python packaging/ci/check_gate.py SONG_FOLDER

It passes when:
- the folder holds notes.chart, song.ini, song.ogg and report.json;
- report.json's gate.ok is true;
- scan-chart ran on the folder (gate.scan_chart.ran), found it playable, and found 0 chart issues;
- guitar, bass and drums each have Expert onsets (report.json's tracks.<part>.expert.onsets above 0). The planning run
  of make_clip.py's 30-s clip had 23, 120 and 119.

A build the gate fails is written to SONG_FOLDER.failed instead (songcharter.assemble.FAILED_SUFFIX); its report is
then checked the same way, so the log says why. Exit 0: pass, with one summary line. Exit 1: each failure listed.
Exit 2: bad usage. Standard library only, so any Python runs it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FILES = ("notes.chart", "song.ini", "song.ogg", "report.json")
PARTS = ("guitar", "bass", "drums")
FAILED_SUFFIX = ".failed"   # songcharter.assemble.FAILED_SUFFIX


def check(folder: Path) -> tuple[list[str], dict]:
    """The failures of one song folder, and what the summary line shows."""
    failures = [f"no {name}" for name in FILES if not (folder / name).is_file()]
    if "no report.json" in failures:
        return failures, {}
    try:
        report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return failures + [f"report.json cannot be read: {e}"], {}
    if not isinstance(report, dict):
        return failures + ["report.json is not an object"], {}

    gate = report.get("gate") if isinstance(report.get("gate"), dict) else {}
    if gate.get("ok") is not True:
        failures.append(f"gate.ok is {gate.get('ok')!r}, with {gate.get('errors')!r} errors: "
                        + "; ".join(f"{i.get('kind')}: {i.get('message')}" for i in gate.get("issues") or []
                                    if isinstance(i, dict) and i.get("error"))[:2000])
    scan = gate.get("scan_chart") if isinstance(gate.get("scan_chart"), dict) else {}
    if scan.get("ran") is not True:
        failures.append(f"scan-chart did not run ({scan.get('reason', 'no gate.scan_chart')})")
    else:
        if scan.get("playable") is not True:
            failures.append(f"scan-chart: playable is {scan.get('playable')!r}")
        if scan.get("chart_issues") != 0:
            failures.append(f"scan-chart: {scan.get('chart_issues')!r} chart issues, not 0")

    tracks = report.get("tracks") if isinstance(report.get("tracks"), dict) else {}
    onsets = {}
    for part in PARTS:
        expert = (tracks.get(part) or {}).get("expert") if isinstance(tracks.get(part), dict) else None
        onsets[part] = n = expert.get("onsets") if isinstance(expert, dict) else None
        if not isinstance(n, int) or n <= 0:
            failures.append(f"{part}: no Expert onsets ({'no Expert track' if n is None else n})")
    return failures, {"scan": scan, "onsets": onsets}


def main(argv: list[str]) -> int:
    if argv in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0
    if len(argv) != 1:
        print("usage: check_gate.py SONG_FOLDER", file=sys.stderr)
        return 2
    folder = Path(argv[0])
    if not folder.is_dir():
        failed = folder.with_name(folder.name + FAILED_SUFFIX)
        if not failed.is_dir():
            print(f"check_gate: FAIL, no song folder at {folder} (nor {failed.name})")
            return 1
        failures, _ = check(failed)
        print(f"check_gate: FAIL, the build went to {failed}: the gate failed it", *(f"  {f}" for f in failures),
              sep="\n")
        return 1
    failures, seen = check(folder)
    if failures:
        print(f"check_gate: FAIL, {folder}:", *(f"  {f}" for f in failures), sep="\n")
        return 1
    counts = ", ".join(f"{part} {n}" for part, n in seen["onsets"].items())
    print(f"check_gate: ok, {folder}: gate ok, scan-chart {seen['scan'].get('version')} playable with 0 chart issues; "
          f"Expert onsets {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
