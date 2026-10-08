"""Contrat de chaque adapter musical : JSON fournisseur (fixtures réelles) -> Track du domaine."""
import dataclasses

import pytest
from fakes import FakeHttp, load_fixture

from reveil_musical.domain.errors import ProviderUnavailable
from reveil_musical.domain.models import Track
from reveil_musical.infrastructure.music.itunes import ITunesMusicProvider
from reveil_musical.infrastructure.music.musicbrainz import MusicBrainzMusicProvider

UA = "ReveilMusical/0.1 (contact@example.com)"


def itunes(http):
    return ITunesMusicProvider(http, "https://itunes.test")


def musicbrainz(http):
    return MusicBrainzMusicProvider(http, "https://mb.test", UA)


def test_itunes_maps_its_json_to_a_domain_track():
    http = FakeHttp(load_fixture("itunes_search.json"))

    track = itunes(http).find_track("Here Comes the Sun")

    assert track == Track(title="Here Comes the Sun", artist="The Beatles", source="itunes")
    assert http.calls[0]["url"] == "https://itunes.test/search"
    assert http.calls[0]["params"] == {"term": "Here Comes the Sun", "media": "music", "limit": 5}


def test_musicbrainz_maps_title_and_artist_credit():
    track = musicbrainz(FakeHttp(load_fixture("musicbrainz_recording.json"))).find_track("Here Comes the Sun")

    assert track == Track(title="Here Comes the Sun", artist="Richie Havens", source="musicbrainz")


def test_musicbrainz_always_sends_an_identifiable_user_agent():
    http = FakeHttp(load_fixture("musicbrainz_recording.json"))

    musicbrainz(http).find_track("x")

    assert http.calls[0]["headers"] == {"User-Agent": UA}
    assert http.calls[0]["params"] == {"query": "x", "fmt": "json"}


@pytest.mark.parametrize("make", [itunes, musicbrainz])
def test_unexpected_json_shape_is_reported_as_provider_unavailable(make):
    with pytest.raises(ProviderUnavailable):
        make(FakeHttp({"results": [{"oops": 1}], "recordings": [{"oops": 1}]})).find_track("x")


@pytest.mark.parametrize(
    "make, payload",
    [
        (itunes, {"results": [{"trackName": None, "artistName": "A"}]}),
        (musicbrainz, {"recordings": [{"title": "", "artist-credit": [{"name": "A"}]}]}),
    ],
)
def test_meaningless_fields_are_reported_as_provider_unavailable(make, payload):
    with pytest.raises(ProviderUnavailable):
        make(FakeHttp(payload)).find_track("x")


def test_no_provider_specific_field_leaks_into_the_domain():
    track = itunes(FakeHttp(load_fixture("itunes_search.json"))).find_track("x")

    assert isinstance(track, Track)
    assert {f.name for f in dataclasses.fields(Track)} == {"title", "artist", "source"}
    assert "trackViewUrl" not in repr(track) and "apple.com" not in repr(track)
