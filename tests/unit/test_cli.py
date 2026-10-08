import logging

import pytest
from fakes import FakeHttp

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
