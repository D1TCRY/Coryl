"""Structured file serialization helpers for Coryl."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date, datetime, time
from math import isfinite
from pathlib import Path
from typing import Any, Literal

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

import yaml

from .exceptions import UnsupportedFormatError

StructuredFormat = Literal["json", "toml", "yaml"]

_STRUCTURED_SUFFIXES: dict[str, StructuredFormat] = {
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
}
_TOML_BARE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def structured_format_for_path(path: str | Path) -> StructuredFormat | None:
    return _STRUCTURED_SUFFIXES.get(Path(path).suffix.lower())


def supports_structured_data(path: str | Path) -> bool:
    return structured_format_for_path(path) is not None


def load_from_path(path: str | Path, text: str) -> Any:
    format_name = structured_format_for_path(path)
    if format_name is None:
        raise UnsupportedFormatError(
            f"Unsupported structured format for '{Path(path)}'. "
            "Supported formats are: .json, .toml, .yaml, .yml."
        )
    return loads(text, format_name)


def dump_to_path(path: str | Path, content: Any) -> str:
    format_name = structured_format_for_path(path)
    if format_name is None:
        raise UnsupportedFormatError(
            f"Unsupported structured format for '{Path(path)}'. "
            "Supported formats are: .json, .toml, .yaml, .yml."
        )
    return dumps(content, format_name)


def loads(text: str, format_name: StructuredFormat) -> Any:
    if not text.strip():
        return {}

    if format_name == "json":
        return json.loads(text)
    if format_name == "toml":
        return tomllib.loads(text)
    if format_name == "yaml":
        result = yaml.safe_load(text)
        return {} if result is None else result

    raise UnsupportedFormatError(f"Unsupported structured format: {format_name!r}.")


def dumps(content: Any, format_name: StructuredFormat) -> str:
    if format_name == "json":
        return json.dumps(content, indent=4, ensure_ascii=False) + "\n"
    if format_name == "toml":
        return dumps_toml(content)
    if format_name == "yaml":
        return yaml.safe_dump(
            content,
            allow_unicode=True,
            sort_keys=False,
        )

    raise UnsupportedFormatError(f"Unsupported structured format: {format_name!r}.")


def dumps_toml(content: Any) -> str:
    if not isinstance(content, Mapping):
        raise TypeError("TOML documents must be mappings at the top level.")

    lines = _render_toml_table(content, ())
    return "\n".join(lines).rstrip() + "\n"


def _render_toml_table(table: Mapping[str, Any], prefix: tuple[str, ...]) -> list[str]:
    lines: list[str] = []
    if prefix:
        dotted_key = ".".join(_format_toml_key(part) for part in prefix)
        lines.append(f"[{dotted_key}]")

    scalar_items: list[tuple[str, Any]] = []
    child_tables: list[tuple[str, Mapping[str, Any]]] = []
    array_tables: list[tuple[str, list[Mapping[str, Any]]]] = []

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


def _render_toml_body(table: Mapping[str, Any], prefix: tuple[str, ...]) -> list[str]:
    lines: list[str] = []
    scalar_items: list[tuple[str, Any]] = []
    child_tables: list[tuple[str, Mapping[str, Any]]] = []
    array_tables: list[tuple[str, list[Mapping[str, Any]]]] = []

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


def _format_toml_value(value: Any) -> str:
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
        raise TypeError("Nested mappings must be emitted as TOML tables, not inline values.")
    if isinstance(value, list):
        if any(isinstance(item, Mapping) for item in value):
            raise TypeError("Lists of mappings must be emitted as TOML array tables.")
        inner = ", ".join(_format_toml_value(item) for item in value)
        return f"[{inner}]"

    raise TypeError(f"Unsupported TOML value type: {type(value).__name__}.")


def _is_array_of_tables(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, Mapping) for item in value)
