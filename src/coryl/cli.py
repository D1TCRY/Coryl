"""Diagnostics CLI for Coryl-managed projects."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from . import Coryl, CorylError, PackageAssetGroup


@dataclass(slots=True)
class CommandResult:
    """Structured CLI output that supports table and JSON rendering."""

    json_data: object
    headers: tuple[str, ...] | None = None
    rows: tuple[Mapping[str, object], ...] = ()
    text: str | None = None
    footer: str | None = None
    exit_code: int = 0


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the Coryl diagnostics CLI."""

    output_stream = stdout or sys.stdout
    error_stream = stderr or sys.stderr
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        result = args.handler(args)
    except (CorylError, FileNotFoundError, KeyError, TypeError, ValueError) as error:
        print(f"Error: {error}", file=error_stream)
        return 1

    _write_result(result, as_json=args.as_json, stream=output_stream)
    return result.exit_code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coryl",
        description="Diagnostics for Coryl-managed projects.",
    )
    root_subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--manifest",
        default="app.toml",
        help="Manifest path relative to --root.",
    )
    common.add_argument(
        "--root",
        default=".",
        help="Project root used to resolve managed resources.",
    )
    common.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output JSON instead of the default table view.",
    )

    resources_parser = root_subparsers.add_parser("resources", help="Inspect manifest resources.")
    resources_subparsers = resources_parser.add_subparsers(dest="resources_command", required=True)

    resources_list = resources_subparsers.add_parser(
        "list",
        parents=[common],
        help="List manifest resources.",
    )
    resources_list.set_defaults(handler=_handle_resources_list)

    resources_check = resources_subparsers.add_parser(
        "check",
        parents=[common],
        help="Report missing or unsafe resources.",
    )
    resources_check.set_defaults(handler=_handle_resources_check)

    config_parser = root_subparsers.add_parser("config", help="Inspect config resources.")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)

    config_show = config_subparsers.add_parser(
        "show",
        parents=[common],
        help="Show the contents of a config resource.",
    )
    config_show.add_argument("name", help="Config resource name.")
    config_show.set_defaults(handler=_handle_config_show)

    cache_parser = root_subparsers.add_parser("cache", help="Inspect cache resources.")
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command", required=True)

    cache_clear = cache_subparsers.add_parser(
        "clear",
        parents=[common],
        help="Clear a managed cache resource.",
    )
    cache_clear.add_argument("name", help="Cache resource name.")
    cache_clear.set_defaults(handler=_handle_cache_clear)

    assets_parser = root_subparsers.add_parser("assets", help="Inspect asset resources.")
    assets_subparsers = assets_parser.add_subparsers(dest="assets_command", required=True)

    assets_list = assets_subparsers.add_parser(
        "list",
        parents=[common],
        help="List files in an asset group.",
    )
    assets_list.add_argument("name", help="Asset resource name.")
    assets_list.set_defaults(handler=_handle_assets_list)

    return parser


def _load_app(manifest: str, root: str) -> Coryl:
    # Diagnostics should inspect the project rather than implicitly creating
    # missing resources from manifest defaults when possible.
    return Coryl(root=root, manifest_path=manifest, create_missing=False)


def _handle_resources_list(args: argparse.Namespace) -> CommandResult:
    app = _load_app(args.manifest, args.root)
    audit = app.audit_paths()
    resources = _audit_rows(audit)
    return CommandResult(
        json_data={
            "root": audit["root"],
            "resources": resources,
        },
        headers=("name", "role", "kind", "exists", "safe", "path"),
        rows=tuple(resources),
    )


def _handle_resources_check(args: argparse.Namespace) -> CommandResult:
    app = _load_app(args.manifest, args.root)
    audit = app.audit_paths()
    resources = _audit_rows(audit)
    problems = [
        resource
        for resource in resources
        if not resource["exists"] or not resource["safe"]
    ]
    for resource in resources:
        issues: list[str] = []
        if not resource["exists"]:
            issues.append("missing")
        if not resource["safe"]:
            issues.append("unsafe")
        resource["status"] = ", ".join(issues) if issues else "ok"

    ok = not problems
    return CommandResult(
        json_data={
            "root": audit["root"],
            "ok": ok,
            "resources": resources,
            "problems": problems,
        },
        headers=("name", "status", "role", "kind", "path"),
        rows=tuple(resources),
        footer="All resources are present and safe." if ok else None,
        exit_code=0 if ok else 1,
    )


def _handle_config_show(args: argparse.Namespace) -> CommandResult:
    app = _load_app(args.manifest, args.root)
    resource = app.config_resource(args.name)
    config_data = _json_ready(resource.load())

    if isinstance(config_data, dict):
        rows = tuple(
            {"key": key, "value": _format_cell(value)}
            for key, value in config_data.items()
        )
        return CommandResult(
            json_data={
                "name": resource.name,
                "path": resource.display_path,
                "config": config_data,
            },
            headers=("key", "value"),
            rows=rows,
        )

    return CommandResult(
        json_data={
            "name": resource.name,
            "path": resource.display_path,
            "config": config_data,
        },
        text=_pretty_json(config_data),
    )


def _handle_cache_clear(args: argparse.Namespace) -> CommandResult:
    app = _load_app(args.manifest, args.root)
    cache = app.cache_resource(args.name)
    existed = cache.exists()
    cache.clear()
    payload = {
        "name": cache.name,
        "path": cache.display_path,
        "cleared": True,
        "previously_exists": existed,
    }
    return CommandResult(
        json_data=payload,
        headers=("name", "cleared", "previously_exists", "path"),
        rows=(payload,),
    )


def _handle_assets_list(args: argparse.Namespace) -> CommandResult:
    app = _load_app(args.manifest, args.root)
    assets = app.asset_group(args.name)
    if not assets.exists():
        raise FileNotFoundError(assets.display_path)

    if isinstance(assets, PackageAssetGroup):
        files = sorted(assets.files("**/*"), key=lambda item: item.display_path)
        rows = tuple(
            {
                "relative_path": item.relative_path.as_posix(),
                "path": item.display_path,
            }
            for item in files
        )
    else:
        files = sorted(assets.files("**/*"), key=lambda item: str(item))
        rows = tuple(
            {
                "relative_path": Path(item).relative_to(assets.path).as_posix(),
                "path": str(item),
            }
            for item in files
        )

    return CommandResult(
        json_data={
            "name": assets.name,
            "path": assets.display_path,
            "files": list(rows),
        },
        headers=("relative_path", "path"),
        rows=rows,
    )


def _audit_rows(audit: Mapping[str, object]) -> list[dict[str, object]]:
    resources = audit.get("resources", {})
    if not isinstance(resources, Mapping):
        raise TypeError("audit_paths() returned an invalid 'resources' mapping.")

    rows: list[dict[str, object]] = []
    for name in sorted(resources):
        details = resources[name]
        if not isinstance(name, str) or not isinstance(details, Mapping):
            raise TypeError("audit_paths() returned an invalid resource entry.")
        rows.append(
            {
                "name": name,
                "role": details.get("role"),
                "kind": details.get("kind"),
                "exists": bool(details.get("exists")),
                "safe": bool(details.get("safe")),
                "path": details.get("path"),
            }
        )
    return rows


def _write_result(result: CommandResult, *, as_json: bool, stream: TextIO) -> None:
    if as_json:
        stream.write(_pretty_json(_json_ready(result.json_data)))
        stream.write("\n")
        return

    if result.headers is not None:
        _write_table(result.headers, result.rows, stream=stream)
    elif result.text is not None:
        stream.write(result.text)
        stream.write("\n")

    if result.footer:
        stream.write(result.footer)
        stream.write("\n")


def _write_table(
    headers: Sequence[str],
    rows: Sequence[Mapping[str, object]],
    *,
    stream: TextIO,
) -> None:
    rendered_rows = [
        {header: _format_cell(row.get(header, "")) for header in headers}
        for row in rows
    ]
    widths = {
        header: max(
            len(header),
            *(len(row[header]) for row in rendered_rows),
        )
        for header in headers
    }

    stream.write("  ".join(header.ljust(widths[header]) for header in headers))
    stream.write("\n")
    stream.write("  ".join("-" * widths[header] for header in headers))
    stream.write("\n")
    for row in rendered_rows:
        stream.write("  ".join(row[header].ljust(widths[header]) for header in headers))
        stream.write("\n")


def _format_cell(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return json.dumps(_json_ready(dict(value)), ensure_ascii=True, sort_keys=True)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return json.dumps(_json_ready(list(value)), ensure_ascii=True)
    return str(value)


def _pretty_json(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True)


def _json_ready(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _json_ready(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_ready(item) for item in value]
    return str(value)


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
