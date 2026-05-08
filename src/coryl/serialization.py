"""Structured file serialization helpers for Coryl."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date, datetime, time
from functools import lru_cache
from importlib import import_module
from math import isfinite
from pathlib import Path, PurePath
from typing import Any, Literal

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

from .exceptions import CorylOptionalDependencyError, UnsupportedFormatError

StructuredFormat = Literal["json", "toml", "yaml"]

_STRUCTURED_SUFFIXES: dict[str, StructuredFormat] = {
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
}
_TOML_BARE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def structured_format_for_path(path: str | PurePath) -> StructuredFormat | None:
    return _STRUCTURED_SUFFIXES.get(Path(path).suffix.lower())


def supports_structured_data(path: str | PurePath) -> bool:
    return structured_format_for_path(path) is not None


def load_from_path(
    path: str | PurePath,
    text: str,
    *,
    unique_keys: bool = False,
) -> object:
    format_name = structured_format_for_path(path)
    if format_name is None:
        raise UnsupportedFormatError(
            f"Unsupported structured format for '{Path(path)}'. "
            "Supported formats are: .json, .toml, .yaml, .yml."
        )
    return loads(text, format_name, unique_keys=unique_keys)


def dump_to_path(path: str | PurePath, content: object) -> str:
    format_name = structured_format_for_path(path)
    if format_name is None:
        raise UnsupportedFormatError(
            f"Unsupported structured format for '{Path(path)}'. "
            "Supported formats are: .json, .toml, .yaml, .yml."
        )
    return dumps(content, format_name)


def loads(
    text: str,
    format_name: StructuredFormat,
    *,
    unique_keys: bool = False,
) -> object:
    if not text.strip():
        return {}

    if format_name == "json":
        if unique_keys:
            return json.loads(text, object_pairs_hook=_json_unique_object_pairs_hook)
        return json.loads(text)
    if format_name == "toml":
        return tomllib.loads(text)
    if format_name == "yaml":
        yaml, unique_loader = _load_yaml_support()
        if unique_keys:
            result = yaml.load(text, Loader=unique_loader)
        else:
            result = yaml.safe_load(text)
        return {} if result is None else result

    raise UnsupportedFormatError(f"Unsupported structured format: {format_name!r}.")


def dumps(content: object, format_name: StructuredFormat) -> str:
    if format_name == "json":
        return json.dumps(content, indent=4, ensure_ascii=False) + "\n"
    if format_name == "toml":
        return dumps_toml(content)
    if format_name == "yaml":
        yaml, _ = _load_yaml_support()
        return yaml.safe_dump(
            content,
            allow_unicode=True,
            sort_keys=False,
        )

    raise UnsupportedFormatError(f"Unsupported structured format: {format_name!r}.")


def dumps_toml(content: object) -> str:
    if not isinstance(content, Mapping):
        raise TypeError("TOML documents must be mappings at the top level.")

    lines = _render_toml_table(content, ())
    return "\n".join(lines).rstrip() + "\n"


def _render_toml_table(
    table: Mapping[str, object], prefix: tuple[str, ...]
) -> list[str]:
    lines: list[str] = []
    if prefix:
        dotted_key = ".".join(_format_toml_key(part) for part in prefix)
        lines.append(f"[{dotted_key}]")

    scalar_items: list[tuple[str, object]] = []
    child_tables: list[tuple[str, Mapping[str, object]]] = []
    array_tables: list[tuple[str, list[Mapping[str, object]]]] = []

    for raw_key, value in table.items():
        key = str(raw_key)
        if isinstance(value, Mapping):
            child_tables.append((key, value))
        elif _is_array_of_tables(value):
            array_tables.append((key, value))
        else:
            scalar_items.append((key, value))

    for key, value in scalar_items:
        lines.append(f"{_format_toml_key(key)} = {_format_toml_value(value)}")

    for key, child in child_tables:
        if lines:
            lines.append("")
        lines.extend(_render_toml_table(child, (*prefix, key)))

    for key, items in array_tables:
        for item in items:
            if lines:
                lines.append("")
            dotted_key = ".".join(_format_toml_key(part) for part in (*prefix, key))
            lines.append(f"[[{dotted_key}]]")
            lines.extend(_render_toml_body(item, (*prefix, key)))

    return lines


def _render_toml_body(
    table: Mapping[str, object], prefix: tuple[str, ...]
) -> list[str]:
    lines: list[str] = []
    scalar_items: list[tuple[str, object]] = []
    child_tables: list[tuple[str, Mapping[str, object]]] = []
    array_tables: list[tuple[str, list[Mapping[str, object]]]] = []

    for raw_key, value in table.items():
        key = str(raw_key)
        if isinstance(value, Mapping):
            child_tables.append((key, value))
        elif _is_array_of_tables(value):
            array_tables.append((key, value))
        else:
            scalar_items.append((key, value))

    for key, value in scalar_items:
        lines.append(f"{_format_toml_key(key)} = {_format_toml_value(value)}")

    for key, child in child_tables:
        if lines:
            lines.append("")
        lines.extend(_render_toml_table(child, (*prefix, key)))

    for key, items in array_tables:
        for item in items:
            if lines:
                lines.append("")
            dotted_key = ".".join(_format_toml_key(part) for part in (*prefix, key))
            lines.append(f"[[{dotted_key}]]")
            lines.extend(_render_toml_body(item, (*prefix, key)))

    return lines


def _format_toml_key(key: str) -> str:
    if _TOML_BARE_KEY_PATTERN.match(key):
        return key
    return json.dumps(key, ensure_ascii=False)


def _format_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not isfinite(value):
            raise TypeError("TOML does not support NaN or Infinity values.")
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if value is None:
        raise TypeError("TOML does not support null values.")
    if isinstance(value, Mapping):
        raise TypeError(
            "Nested mappings must be emitted as TOML tables, not inline values."
        )
    if isinstance(value, list):
        if any(isinstance(item, Mapping) for item in value):
            raise TypeError("Lists of mappings must be emitted as TOML array tables.")
        inner = ", ".join(_format_toml_value(item) for item in value)
        return f"[{inner}]"

    raise TypeError(f"Unsupported TOML value type: {type(value).__name__}.")


def _is_array_of_tables(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, Mapping) for item in value)
    )


def _json_unique_object_pairs_hook(
    pairs: list[tuple[object, object]],
) -> dict[object, object]:
    return _mapping_from_unique_pairs(pairs, source="JSON object")


def _mapping_from_unique_pairs(
    pairs: list[tuple[object, object]],
    *,
    source: str,
) -> dict[object, object]:
    mapping: dict[object, object] = {}
    for key, value in pairs:
        if key in mapping:
            raise ValueError(f"Duplicate key {key!r} found in {source}.")
        mapping[key] = value
    return mapping


@lru_cache(maxsize=1)
def _load_yaml_module() -> Any:
    try:
        return import_module("yaml")
    except ModuleNotFoundError as error:
        raise CorylOptionalDependencyError(
            "YAML support requires the optional 'PyYAML' dependency. "
            "Install it with 'pip install coryl[yaml]'."
        ) from error


@lru_cache(maxsize=1)
def _load_yaml_support() -> tuple[Any, type[Any]]:
    yaml = _load_yaml_module()

    class UniqueKeySafeLoader(yaml.SafeLoader):
        pass

    def construct_unique_yaml_mapping(
        loader: Any,
        node: Any,
        deep: bool = False,
    ) -> dict[object, object]:
        loader.flatten_mapping(node)
        pairs: list[tuple[object, object]] = []
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            value = loader.construct_object(value_node, deep=deep)
            pairs.append((key, value))
        return _mapping_from_unique_pairs(pairs, source="YAML mapping")

    UniqueKeySafeLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_unique_yaml_mapping,
    )
    return yaml, UniqueKeySafeLoader
