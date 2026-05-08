from __future__ import annotations

from types import SimpleNamespace

import pytest

import coryl.resources as coryl_resources

from coryl import Coryl, CorylOptionalDependencyError, CorylValidationError


class _FakeValidationError(Exception):
    pass


class _FakeBaseModel:
    @classmethod
    def model_validate(cls, data: object) -> object:
        raise NotImplementedError


class _FakeSettingsModel(_FakeBaseModel):
    def __init__(self, host: str, port: int, debug: bool = False) -> None:
        self.host = host
        self.port = port
        self.debug = debug

    @classmethod
    def model_validate(cls, data: object) -> "_FakeSettingsModel":
        if not isinstance(data, dict):
            raise _FakeValidationError("Input should be a mapping.")

        host = data.get("host")
        port = data.get("port")
        debug = data.get("debug", False)

        if not isinstance(host, str):
            raise _FakeValidationError("host must be a string.")
        if not isinstance(port, int):
            raise _FakeValidationError("port must be an integer.")
        if not isinstance(debug, bool):
            raise _FakeValidationError("debug must be a boolean.")

        return cls(host, port, debug)

    def model_dump(self, *, mode: str = "json") -> dict[str, object]:
        if mode != "json":
            raise AssertionError(f"Unexpected dump mode: {mode!r}")
        return {"host": self.host, "port": self.port, "debug": self.debug}


@pytest.fixture
def fake_pydantic_module() -> SimpleNamespace:
    return SimpleNamespace(
        BaseModel=_FakeBaseModel,
        ValidationError=_FakeValidationError,
        SettingsModel=_FakeSettingsModel,
    )


def _patch_optional_import(monkeypatch: pytest.MonkeyPatch, *, module_name: str, module: object) -> None:
    original_import_module = coryl_resources.import_module

    def fake_import(name: str, package: str | None = None) -> object:
        if name == module_name:
            return module
        return original_import_module(name, package)

    monkeypatch.setattr(coryl_resources, "import_module", fake_import)


def test_typed_config_load_typed_supports_explicit_model_and_registered_schema(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    fake_pydantic_module: SimpleNamespace,
) -> None:
    _patch_optional_import(monkeypatch, module_name="pydantic", module=fake_pydantic_module)

    app = Coryl(tmp_path)
    explicit = app.configs.add("explicit", "config/explicit.toml")
    registered = app.configs.add(
        "registered",
        "config/registered.toml",
        schema=fake_pydantic_module.SettingsModel,
    )

    payload = {"host": "localhost", "port": 5432, "debug": True}
    explicit.save(payload)
    registered.save(payload)

    explicit_loaded = explicit.load_typed(fake_pydantic_module.SettingsModel)
    registered_loaded = registered.load_typed()

    assert isinstance(explicit_loaded, fake_pydantic_module.SettingsModel)
    assert isinstance(registered_loaded, fake_pydantic_module.SettingsModel)
    assert explicit_loaded.port == 5432
    assert registered_loaded.debug is True


def test_typed_config_save_typed_round_trips_model_instances(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    fake_pydantic_module: SimpleNamespace,
) -> None:
    _patch_optional_import(monkeypatch, module_name="pydantic", module=fake_pydantic_module)

    app = Coryl(tmp_path)
    settings = app.configs.add("settings", "config/settings.toml")

    instance = fake_pydantic_module.SettingsModel("localhost", 5432, True)
    settings.save_typed(instance)

    assert settings.load() == {"host": "localhost", "port": 5432, "debug": True}


def test_typed_config_validation_failures_raise_coryl_validation_error(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    fake_pydantic_module: SimpleNamespace,
) -> None:
    _patch_optional_import(monkeypatch, module_name="pydantic", module=fake_pydantic_module)

    app = Coryl(tmp_path)
    settings = app.configs.add("settings", "config/settings.toml")
    settings.save({"host": "localhost", "port": "not-an-int"})

    with pytest.raises(CorylValidationError, match="Configuration validation failed"):
        settings.load_typed(fake_pydantic_module.SettingsModel)


def test_typed_config_helpers_raise_clear_optional_dependency_errors_when_missing(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    fake_pydantic_module: SimpleNamespace,
) -> None:
    original_import_module = coryl_resources.import_module

    def missing_pydantic(name: str, package: str | None = None) -> object:
        if name == "pydantic":
            raise ModuleNotFoundError("No module named 'pydantic'")
        return original_import_module(name, package)

    monkeypatch.setattr(coryl_resources, "import_module", missing_pydantic)

    app = Coryl(tmp_path)
    settings = app.configs.add(
        "settings",
        "config/settings.toml",
        schema=fake_pydantic_module.SettingsModel,
    )
    settings.save({"host": "localhost", "port": 5432})
    instance = fake_pydantic_module.SettingsModel("localhost", 5432, True)

    with pytest.raises(CorylOptionalDependencyError, match=r"pip install coryl\[pydantic\]"):
        settings.load_typed()

    with pytest.raises(CorylOptionalDependencyError, match=r"pip install coryl\[pydantic\]"):
        settings.save_typed(instance)
