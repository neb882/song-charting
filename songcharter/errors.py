"""The errors a user can act on.

The command line exits 2 for these and for an OSError (a file that is missing or cannot be read or written, a
download that failed), printing their one-line message; any other exception is a bug in songcharter: exit 3, with
its traceback. A bare ValueError or RuntimeError, such as numpy's or torch's, is therefore a bug, not a bad input.

Each class is also the built-in its raise sites raised before (ValueError, RuntimeError), so callers that catch
those still catch them.
"""


class SongcharterError(Exception):
    """An error the user can act on; its message says what is wrong and, where there is one, the fix."""


class InputError(SongcharterError, ValueError):
    """A bad input, config or option: a file ffmpeg cannot read, a chart that does not parse, a value out of range,
    an output folder that holds foreign files, a song with nothing to chart."""


class ToolError(SongcharterError, RuntimeError):
    """A component that is missing or fails: ffmpeg, a model's weights, autochart's engine, allin1, song.ogg's
    sync."""
