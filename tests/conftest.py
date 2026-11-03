"""Shared test setup."""
import pytest


@pytest.fixture(autouse=True, scope="session")
def private_cache(tmp_path_factory):
    """$SONGCHARTER_CACHE for the whole session, so a pipeline run's default work folder (songcharter.cache) goes to
    a temporary folder and never to the real per-user cache (%LOCALAPPDATA%\\songcharter, ~/.cache/songcharter). A
    test that looks into the cache sets one of its own."""
    with pytest.MonkeyPatch.context() as mp:
        path = tmp_path_factory.mktemp("user-cache")
        mp.setenv("SONGCHARTER_CACHE", str(path))
        yield path
