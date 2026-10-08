import logging

import pytest
from fakes import FakeHttp, load_fixture

from reveil_musical.__main__ import main
from reveil_musical.container import create_container


@pytest.fixture
def offline():
    container = create_container({})
    container.http.override(FakeHttp(error="offline"))
    return container


def test_cli_entry_point_prints_the_result(offline, capsys):
    assert main(["u3", "VENDREDI", "NUAGEUX"], offline) == 0
    assert "PUSH" in capsys.readouterr().out


def test_cli_rejects_an_unknown_weather():
    with pytest.raises(SystemExit):
        main(["u1", "LUNDI", "GRELE"])


def test_unknown_user_gives_a_clear_message_and_exit_code_2(offline, caplog):
    assert main(["ghost", "LUNDI", "SOLEIL"], offline) == 2
    assert "ghost" in caplog.text


def test_user_service_outage_is_logged_as_critical_and_exit_code_1(offline, caplog):
    class DownUsers:
        def get(self, user_id):
            raise TimeoutError("service utilisateurs injoignable")

    offline.users.override(DownUsers())

    assert main(["u1", "LUNDI", "SOLEIL"], offline) == 1
    critical = [r for r in caplog.records if r.levelno == logging.CRITICAL]
    assert critical and "u1" in critical[0].getMessage()


def test_day_and_weather_are_case_insensitive(offline):
    assert main(["u1", "lundi", "Soleil"], offline) == 0


def test_without_arguments_the_cli_explains_its_usage():
    with pytest.raises(SystemExit):
        main([])


def write_batch(tmp_path, *lines):
    path = tmp_path / "reveils.csv"
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def test_batch_shares_the_cache_so_the_quota_is_really_respected(tmp_path, capsys):
    container = create_container({})
    http = FakeHttp(load_fixture("itunes_search.json"))
    container.http.override(http)
    batch = write_batch(tmp_path, "# user,jour,meteo", "u3,LUNDI,SOLEIL", "u3,MARDI,PLUIE", "", "u3,MERCREDI,NEIGE")

    assert main(["--batch", batch], container) == 0

    assert capsys.readouterr().out.count("Réveil envoyé") == 3
    assert len(http.calls) == 1  # même morceau : un seul appel réseau pour toute la tournée


def test_a_bad_line_does_not_prevent_the_other_wake_ups(offline, tmp_path, capsys, caplog):
    batch = write_batch(tmp_path, "u1,LUNDI,SOLEIL", "u1,FERIE,SOLEIL", "u2,MARDI,PLUIE")

    assert main(["--batch", batch], offline) == 1

    assert capsys.readouterr().out.count("Réveil envoyé") == 2
    assert "ligne 2" in caplog.text


@pytest.mark.parametrize(
    "variable, value", [("REVEIL_HTTP_TIMEOUT", "abc"), ("REVEIL_MUSIC_PROVIDERS", "spotify"), ("REVEIL_MUSIC_PROVIDERS", "")]
)
def test_invalid_configuration_stops_cleanly_with_exit_code_1(monkeypatch, caplog, variable, value):
    monkeypatch.setenv(variable, value)

    assert main(["u1", "LUNDI", "SOLEIL"]) == 1
    assert "configuration invalide" in caplog.text and variable in caplog.text


def test_missing_batch_file_is_reported_cleanly(offline, caplog):
    assert main(["--batch", "/nulle/part/reveils.csv"], offline) == 1
    assert "/nulle/part/reveils.csv" in caplog.text


def test_an_empty_batch_is_an_error_not_a_silent_success(offline, tmp_path, caplog):
    assert main(["--batch", write_batch(tmp_path, "# user,jour,meteo", "")], offline) == 1
    assert "aucun réveil" in caplog.text


def test_batch_with_only_an_unknown_user_exits_with_2(offline, tmp_path):
    assert main(["--batch", write_batch(tmp_path, "u1,LUNDI,SOLEIL", "ghost,LUNDI,SOLEIL")], offline) == 2


def test_batch_exit_code_reports_the_most_serious_problem(offline, tmp_path):
    # une ligne invalide (1 : réveil non livré) est plus grave qu'un utilisateur inconnu (2)
    batch = write_batch(tmp_path, "u1,LUNDI", "ghost,LUNDI,SOLEIL")
    assert main(["--batch", batch], offline) == 1
