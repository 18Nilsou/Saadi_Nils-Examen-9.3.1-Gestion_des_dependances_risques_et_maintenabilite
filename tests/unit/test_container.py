import pytest
from dependency_injector import providers
from fakes import FakeHttp, load_fixture

from reveil_musical.container import Container, create_container
from reveil_musical.domain.models import Channel, DayOfWeek, Weather


@pytest.fixture
def container():
    return create_container({})


def test_resolves_the_use_case_and_wakes_up_through_itunes(container):
    container.http.override(FakeHttp(load_fixture("itunes_search.json")))

    result = container.wake_up_use_case().execute("u1", DayOfWeek.LUNDI, Weather.SOLEIL)

    assert (result.track.source, result.channel, result.degraded) == ("itunes", Channel.EMAIL, False)


def test_network_down_ends_on_the_local_list(container):
    container.http.override(FakeHttp(error="network down"))

    result = container.wake_up_use_case().execute("u2", DayOfWeek.MARDI, Weather.NEIGE)

    assert (result.track.source, result.channel, result.degraded) == ("local", Channel.SMS, True)


def test_stateful_components_are_singletons_and_use_case_is_transient(container):
    assert container.itunes() is container.itunes()
    assert container.http() is container.http()
    assert container.wake_up_use_case() is not container.wake_up_use_case()


def test_no_captive_dependency_singletons_only_depend_on_singletons_or_config():
    allowed = (providers.Singleton, providers.Configuration, providers.ConfigurationOption, providers.Object)
    for singleton in Container().traverse(types=[providers.Singleton]):
        for dep in singleton.related:
            assert isinstance(dep, allowed), f"{singleton} capture {dep}"


def test_env_variables_override_defaults():
    c = create_container({"REVEIL_ITUNES_URL": "http://itunes.local", "REVEIL_HTTP_TIMEOUT": "1.5"})

    assert c.config.itunes_url() == "http://itunes.local"
    assert c.config.http_timeout() == 1.5


def urls_called(env, http):
    c = create_container(env)
    c.http.override(http)
    result = c.wake_up_use_case().execute("u1", DayOfWeek.LUNDI, Weather.SOLEIL)
    return [call["url"].split("/")[2] for call in http.calls], result


def test_provider_order_comes_from_configuration():
    hosts, result = urls_called({"REVEIL_MUSIC_PROVIDERS": "musicbrainz,itunes"}, FakeHttp(error="down"))

    assert hosts == ["musicbrainz.org", "itunes.apple.com"]
    assert result.track.source == "local"  # la liste locale reste toujours en dernier


def test_a_provider_can_be_removed_without_touching_the_code():
    hosts, _ = urls_called({"REVEIL_MUSIC_PROVIDERS": "musicbrainz"}, FakeHttp(error="down"))

    assert hosts == ["musicbrainz.org"]


def test_unknown_provider_name_fails_at_startup_not_at_wake_up_time():
    with pytest.raises(ValueError, match="spotify"):
        create_container({"REVEIL_MUSIC_PROVIDERS": "itunes,spotify"})
