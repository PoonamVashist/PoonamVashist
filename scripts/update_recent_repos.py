#!/usr/bin/env python3
"""Refresh the recent public repositories section in the profile README."""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "profile.json"
DEFAULT_README = ROOT / "README.md"
START_MARKER = "<!-- RECENT-REPOS:START -->"
END_MARKER = "<!-- RECENT-REPOS:END -->"


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def validate_config(config: dict[str, Any]) -> None:
    if not isinstance(config.get("username"), str) or not config["username"].strip():
        raise ValueError("profile.json must contain a non-empty 'username'.")
    if not isinstance(config.get("limit"), int) or config["limit"] < 1:
        raise ValueError("profile.json 'limit' must be a positive integer.")
    if config.get("sort") not in {"created", "updated", "pushed", "full_name"}:
        raise ValueError("profile.json 'sort' is not supported by the GitHub API.")
    if config.get("direction") not in {"asc", "desc"}:
        raise ValueError("profile.json 'direction' must be 'asc' or 'desc'.")
    if not isinstance(config.get("repository_overrides", {}), dict):
        raise ValueError("profile.json 'repository_overrides' must be an object.")


def fetch_repositories(config: dict[str, Any]) -> list[dict[str, Any]]:
    username = config["username"]
    query = urlencode(
        {
            "type": "owner",
            "sort": config["sort"],
            "direction": config["direction"],
            "per_page": 100,
        }
    )
    url = f"https://api.github.com/users/{quote(username)}/repos?{query}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{username}-profile-readme-updater",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise RuntimeError(
            f"GitHub API returned HTTP {error.code} while loading repositories."
        ) from error
    except URLError as error:
        raise RuntimeError(f"Could not reach the GitHub API: {error.reason}") from error

    if not isinstance(payload, list):
        raise RuntimeError("GitHub API returned an unexpected response.")
    return payload


def filter_repositories(
    repositories: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    excluded = {name.casefold() for name in config.get("exclude", [])}
    selected: list[dict[str, Any]] = []

    for repository in repositories:
        name = str(repository.get("name", ""))
        description = repository.get("description")
        if not name or name.casefold() in excluded:
            continue
        if repository.get("private", False):
            continue
        if repository.get("fork", False) or repository.get("archived", False):
            continue
        if config.get("require_description", False) and not description:
            continue
        selected.append(repository)
        if len(selected) == config["limit"]:
            break

    return selected


def format_date(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return "recently"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return "recently"


def render_repository(
    repository: dict[str, Any], override: dict[str, Any] | None = None
) -> str:
    override = override or {}
    name = html.escape(str(repository.get("name", "Repository")))
    url = html.escape(str(repository.get("html_url", "#")), quote=True)
    description = html.escape(
        str(
            override.get("summary")
            or repository.get("description")
            or "Public repository by Poonam Vashist."
        )
    )
    stack = override.get("stack")
    if not isinstance(stack, list) or not stack:
        stack = [repository.get("language") or "Multiple technologies"]
    stack_markup = " · ".join(
        f"<code>{html.escape(str(technology))}</code>" for technology in stack
    )
    updated = format_date(repository.get("pushed_at") or repository.get("updated_at"))

    return "\n".join(
        [
            '<td width="50%" valign="top">',
            f'<strong><a href="{url}">{name}</a></strong>',
            "<br><br>",
            description,
            "<br><br>",
            f"<sub>{stack_markup} · Updated {updated}</sub>",
            "</td>",
        ]
    )


def render_recent_repositories(
    repositories: list[dict[str, Any]],
    overrides: dict[str, Any] | None = None,
) -> str:
    if not repositories:
        return "_New public work will appear here automatically._"

    overrides = overrides or {}
    rows: list[str] = []
    for index in range(0, len(repositories), 2):
        cells = [
            render_repository(repo, overrides.get(str(repo.get("name", "")), {}))
            for repo in repositories[index : index + 2]
        ]
        rows.extend(["<tr>", *cells, "</tr>"])

    return "\n".join(["<table>", *rows, "</table>"])


def updated_readme(current: str, rendered: str) -> str:
    if current.count(START_MARKER) != 1 or current.count(END_MARKER) != 1:
        raise ValueError("README.md must contain exactly one recent-repositories marker pair.")

    before, remainder = current.split(START_MARKER, 1)
    _, after = remainder.split(END_MARKER, 1)
    return f"{before}{START_MARKER}\n{rendered}\n{END_MARKER}{after}"


def update_readme(path: Path, rendered: str, *, check: bool = False) -> bool:
    current = path.read_text(encoding="utf-8")
    refreshed = updated_readme(current, rendered)
    changed = current != refreshed

    if changed and not check:
        path.write_text(refreshed, encoding="utf-8")
    return changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--readme", type=Path, default=DEFAULT_README)
    parser.add_argument(
        "--repos-file",
        type=Path,
        help="Read repository data from a local JSON file instead of the GitHub API.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with status 1 if README.md would change; do not write it.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_json(args.config)
        if not isinstance(config, dict):
            raise ValueError("profile.json must contain a JSON object.")
        validate_config(config)
        repositories = (
            load_json(args.repos_file) if args.repos_file else fetch_repositories(config)
        )
        if not isinstance(repositories, list):
            raise ValueError("Repository data must contain a JSON array.")

        selected = filter_repositories(repositories, config)
        rendered = render_recent_repositories(
            selected, config.get("repository_overrides", {})
        )
        changed = update_readme(args.readme, rendered, check=args.check)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.check and changed:
        print("README.md is not up to date.")
        return 1
    if changed:
        print("Updated README.md with recent public work.")
    else:
        print("README.md is already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
