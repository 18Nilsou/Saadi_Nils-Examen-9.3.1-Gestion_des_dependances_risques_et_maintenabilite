"""Bout en bout contre les VRAIES API (réseau requis). Exclus par défaut ;
lancer avec : pytest -m e2e --no-cov"""
import subprocess
import sys

import pytest

from reveil_musical.container import DEFAULTS
from reveil_musical.domain.models import Track
from reveil_musical.infrastructure.http import JsonHttpClient
from reveil_musical.infrastructure.music.itunes import ITunesMusicProvider
from reveil_musical.infrastructure.music.musicbrainz import MusicBrainzMusicProvider

pytestmark = pytest.mark.e2e

HTTP = JsonHttpClient(timeout=10)


def test_itunes_still_matches_our_adapter():
    track = ITunesMusicProvider(HTTP, DEFAULTS["itunes_url"]).find_track("Here Comes the Sun")

    assert isinstance(track, Track) and track.artist == "The Beatles"


def test_musicbrainz_accepts_our_user_agent_and_still_matches_our_adapter():
    provider = MusicBrainzMusicProvider(HTTP, DEFAULTS["musicbrainz_url"], DEFAULTS["musicbrainz_user_agent"])

    track = provider.find_track("Here Comes the Sun")

    assert isinstance(track, Track) and "here comes the sun" in track.title.lower()


def test_full_wake_up_from_the_command_line():
    run = subprocess.run(
        [sys.executable, "-m", "reveil_musical", "u1", "LUNDI", "SOLEIL"],
        capture_output=True, text=True, timeout=60,
    )

    assert run.returncode == 0, run.stderr
    assert "Réveil envoyé via EMAIL" in run.stdout and "source=itunes" in run.stdout
