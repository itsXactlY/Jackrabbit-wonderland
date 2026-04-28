#!/usr/bin/env python3
"""Sync Hermes Agent's local provider config from container/wonderland.env."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = ROOT / "container" / "wonderland.env"
DEFAULT_CONFIG = Path(os.environ.get("HERMES_CONFIG", Path.home() / ".hermes" / "config.yaml"))


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        elif "#" in value:
            value = value.split("#", 1)[0].strip()
        values[key.strip()] = value
    return values


def yaml_scalar(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:@+-]+", value):
        return value
    return "'" + value.replace("'", "''") + "'"


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def normalized_name(value: str) -> str:
    return value.strip().lower().replace(" ", "-")


def find_top_block(lines: list[str], key: str, *, allow_dash: bool) -> tuple[int, int] | None:
    pattern = re.compile(rf"^{re.escape(key)}:\s*(?:#.*)?$")
    start = next((i for i, line in enumerate(lines) if pattern.match(line.rstrip("\n"))), None)
    if start is None:
        return None

    end = len(lines)
    for i in range(start + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("#"):
            continue
        is_child = lines[i].startswith((" ", "\t")) or (allow_dash and lines[i].startswith("-"))
        if not is_child:
            end = i
            break
    return start, end


def update_mapping_block(
    lines: list[str],
    start: int,
    end: int,
    fields: dict[str, str],
    *,
    indent: str,
) -> tuple[list[str], int]:
    present: set[str] = set()
    insert_at = start + 1
    field_re = re.compile(rf"^{re.escape(indent)}([A-Za-z0-9_-]+):")

    for i in range(start + 1, end):
        match = field_re.match(lines[i])
        if not match:
            continue
        key = match.group(1)
        if key in fields:
            lines[i] = f"{indent}{key}: {yaml_scalar(fields[key])}\n"
            present.add(key)
            insert_at = i + 1

    additions = [
        f"{indent}{key}: {yaml_scalar(value)}\n"
        for key, value in fields.items()
        if key not in present
    ]
    if additions:
        lines[insert_at:insert_at] = additions
        end += len(additions)
    return lines, end


def ensure_model_block(lines: list[str], provider: str, model: str, base_url: str) -> list[str]:
    fields = {
        "provider": provider,
        "default": model,
        "base_url": base_url,
    }
    block = find_top_block(lines, "model", allow_dash=False)
    if block is None:
        prefix = [
            "model:\n",
            *[f"  {key}: {yaml_scalar(value)}\n" for key, value in fields.items()],
            "\n",
        ]
        return prefix + lines

    start, end = block
    lines, _ = update_mapping_block(lines, start, end, fields, indent="  ")
    return lines


def ensure_custom_provider(
    lines: list[str],
    provider: str,
    model: str,
    base_url: str,
    api_key: str,
) -> list[str]:
    fields = {
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
        "api_mode": "chat_completions",
    }
    entry = [f"- name: {yaml_scalar(provider)}\n"]
    entry.extend(f"  {key}: {yaml_scalar(value)}\n" for key, value in fields.items())

    block = find_top_block(lines, "custom_providers", allow_dash=True)
    if block is None:
        if lines and lines[-1].strip():
            lines.append("\n")
        lines.append("custom_providers:\n")
        lines.extend(entry)
        return lines

    start, end = block
    target = normalized_name(provider)
    entry_start: int | None = None
    name_re = re.compile(r"^-\s+name:\s*(.*?)\s*(?:#.*)?$")
    for i in range(start + 1, end):
        match = name_re.match(lines[i].rstrip("\n"))
        if match and normalized_name(unquote(match.group(1))) == target:
            entry_start = i
            break

    if entry_start is None:
        lines[end:end] = entry
        return lines

    entry_end = end
    for i in range(entry_start + 1, end):
        if lines[i].startswith("-"):
            entry_end = i
            break

    lines[entry_start] = f"- name: {yaml_scalar(provider)}\n"
    lines, _ = update_mapping_block(lines, entry_start, entry_end, fields, indent="  ")
    return lines


def sync_config(config_path: Path, env_path: Path, *, dry_run: bool) -> tuple[Path | None, dict[str, str]]:
    env = parse_env_file(env_path)
    provider = env.get("WONDERLAND_PROVIDER", "wonderland").strip() or "wonderland"
    base_url = (env.get("WONDERLAND_BASE_URL") or env.get("OPENAI_BASE_URL") or "").strip()
    model = (env.get("WONDERLAND_MODEL") or env.get("OPENAI_MODEL") or provider).strip()
    api_key = (env.get("WONDERLAND_API_KEY") or "local-wonderland").strip()

    if not base_url:
        raise SystemExit(f"{env_path} does not define WONDERLAND_BASE_URL or OPENAI_BASE_URL")
    if not model:
        raise SystemExit(f"{env_path} does not define WONDERLAND_MODEL or OPENAI_MODEL")

    if config_path.exists():
        lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    else:
        lines = []

    lines = ensure_model_block(lines, provider, model, base_url)
    lines = ensure_custom_provider(lines, provider, model, base_url, api_key)
    new_text = "".join(lines)
    if new_text and not new_text.endswith("\n"):
        new_text += "\n"

    backup_path: Path | None = None
    if not dry_run:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if config_path.exists():
            stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = config_path.with_name(f"{config_path.name}.backup.wonderland-{stamp}")
            shutil.copy2(config_path, backup_path)
        config_path.write_text(new_text, encoding="utf-8")

    return backup_path, {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Configure Hermes Agent to use the local Wonderland gateway."
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    backup, resolved = sync_config(args.config.expanduser(), args.env_file.expanduser(), dry_run=args.dry_run)
    mode = "would sync" if args.dry_run else "synced"
    print(f"Hermes config {mode}: {args.config.expanduser()}")
    if backup:
        print(f"Backup: {backup}")
    print(f"Provider: {resolved['provider']}")
    print(f"Model: {resolved['model']}")
    print(f"Base URL: {resolved['base_url']}")


if __name__ == "__main__":
    main()
