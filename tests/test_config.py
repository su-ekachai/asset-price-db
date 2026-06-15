import pytest

from src.config import AppConfig, load_config
from src.exceptions import ConfigurationError


def test_load_config(tmp_path):
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text("""
database:
  host: testhost
  ilp_port: 9001
  pg_port: 8813
  user: testuser
  password: testpassword
download:
  rate_limit_pause: 1.0
    """)
    config = load_config(str(config_file))
    assert isinstance(config, AppConfig)
    assert config.database.host == "testhost"
    assert config.database.ilp_port == 9001
    assert config.download.rate_limit_pause == 1.0


def test_load_config_missing_file():
    config = load_config("non_existent_config.yaml")
    assert config.database.host == "localhost"


def test_env_vars_override_defaults(monkeypatch):
    monkeypatch.setenv("QUESTDB_HOST", "envhost")
    monkeypatch.setenv("QUESTDB_USER", "envuser")
    monkeypatch.setenv("QUESTDB_PASSWORD", "envpass")
    monkeypatch.setenv("QUESTDB_ILP_PORT", "9999")
    monkeypatch.setenv("QUESTDB_PG_PORT", "7777")

    config = load_config("non_existent_config.yaml")
    assert config.database.host == "envhost"
    assert config.database.user == "envuser"
    assert config.database.password == "envpass"
    assert config.database.ilp_port == 9999
    assert config.database.pg_port == 7777


def test_env_vars_override_yaml(tmp_path, monkeypatch):
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text("""
database:
  host: yamlhost
  user: yamluser
  password: yamlpass
    """)
    monkeypatch.setenv("QUESTDB_HOST", "envhost")
    monkeypatch.setenv("QUESTDB_PASSWORD", "envpass")

    config = load_config(str(config_file))
    assert config.database.host == "envhost"
    assert config.database.user == "yamluser"
    assert config.database.password == "envpass"


def test_env_port_not_an_integer(monkeypatch):
    monkeypatch.setenv("QUESTDB_PG_PORT", "eighty-eight-twelve")
    with pytest.raises(ConfigurationError, match="QUESTDB_PG_PORT must be an integer"):
        load_config("non_existent_config.yaml")


def test_env_port_out_of_range(monkeypatch):
    monkeypatch.setenv("QUESTDB_ILP_PORT", "70000")
    with pytest.raises(ConfigurationError, match="between 1 and 65535"):
        load_config("non_existent_config.yaml")
