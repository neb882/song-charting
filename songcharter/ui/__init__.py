"""songcharter's local page (M4-04, DESIGN.md 4.5): a standard-library server on 127.0.0.1 (server.py), one chart at
a time as a child process group (jobs.py, proc.py), and a vanilla-JS page with no CDN and no build step (static/).

What the UI keeps is in $SONGCHARTER_HOME (`home`: the launcher sets it, ~/.local/share/songcharter by default):

    uploads/<16 hex>/<name><ext>, upload.json   a dropped song file (16 hex of its SHA-256), with its tags
    library/<16 hex>/<artist - title>/          the song folder a job builds (its .failed beside it)
    logs/ui-<yyyyMMdd>.log, logs/job-<yyyyMMdd-HHmmss>.log
    doctor.json                                 the install's doctor report: the page's header
    exports/<name>.zip                          a zip the Done screen saved (M4-06)
    replaced/<stamp>/<artist - title>/          an older chart of ours that an install replaced (M4-06)
    ui.json                                     the page's settings: the Songs folder chosen (M4-06)
    state/update.json                           the update check's last answer, kept a day (updates.py, M5-07)
"""
from __future__ import annotations

import os
from pathlib import Path


def home() -> Path:
    """$SONGCHARTER_HOME, else ~/.local/share/songcharter (the install's layout, M4-03)."""
    value = os.environ.get("SONGCHARTER_HOME")
    return Path(value).expanduser() if value else Path.home() / ".local" / "share" / "songcharter"
