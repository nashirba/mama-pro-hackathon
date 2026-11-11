import pytest

from config.settings import allowed_hosts_from_env, database_from_env


@pytest.mark.parametrize("url", ["postgresql://u:p@h/db", "postgres://u:p@h/db", "postgis://u:p@h/db"])
def test_database_scheme_forced_to_postgis(url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", url)
    assert database_from_env(None)["ENGINE"] == "django.contrib.gis.db.backends.postgis"


def test_pooler_host_disables_server_side_cursors(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@ep-cool-123-pooler.eu-central-1.aws.neon.tech/db")
    assert database_from_env(None)["DISABLE_SERVER_SIDE_CURSORS"] is True


def test_direct_host_keeps_server_side_cursors(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@ep-cool-123.eu-central-1.aws.neon.tech/db")
    assert "DISABLE_SERVER_SIDE_CURSORS" not in database_from_env(None)


def test_render_hostname_added_to_allowed_hosts(monkeypatch):
    monkeypatch.setenv("ALLOWED_HOSTS", "example.kz")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "kamqor-demo.onrender.com")
    assert allowed_hosts_from_env() == ["example.kz", "kamqor-demo.onrender.com"]


def test_allowed_hosts_without_render_hostname(monkeypatch):
    monkeypatch.setenv("ALLOWED_HOSTS", "example.kz")
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)
    assert allowed_hosts_from_env() == ["example.kz"]
