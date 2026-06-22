from typing import Any, cast

from pytest import MonkeyPatch

from server.config import Settings


def clear_agentclef_env(monkeypatch: MonkeyPatch) -> None:
    for field_name in Settings.model_fields:
        monkeypatch.delenv(f"AGENTCLEF_{field_name.upper()}", raising=False)


def make_settings(monkeypatch: MonkeyPatch, **overrides: object) -> Settings:
    clear_agentclef_env(monkeypatch)
    return make_settings_from_env(**overrides)


def make_settings_from_env(**overrides: object) -> Settings:
    settings_cls = cast(Any, Settings)
    return settings_cls(_env_file=None, **overrides)
