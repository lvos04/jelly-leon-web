"""Testopzet: een nep-upstream (webclient) en een fork in tijdelijke git-repositories (simulator, geen netwerk)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
REPO_ROOT = TOOLS.parent.parent
sys.path.insert(0, str(TOOLS))

GPL_HEAD = "GNU GENERAL PUBLIC LICENSE\n                       Version 2, June 1991\n"


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    configure(path)
    return path


def configure(path: Path) -> None:
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.invalid")
    git(path, "config", "commit.gpgsign", "false")
    git(path, "config", "tag.gpgsign", "false")


def package_json(version: str) -> str:
    return json.dumps({"name": "jellyfin-web", "version": version, "license": "GPL-2.0-or-later"}, indent=2) + "\n"


def package_lock(version: str) -> str:
    data = {"name": "jellyfin-web", "version": version, "lockfileVersion": 3,
            "packages": {"": {"name": "jellyfin-web", "version": version}}}
    return json.dumps(data, indent=2) + "\n"


PATCHES = """# Patchregister

## JLW-0001 — Haak voor de MediaGuard-knop op de detailpagina

| Veld | Waarde |
|---|---|
| Status | actief |
| Doel | Eén regel die de fork-eigen extensie aanroept |
| Bestanden | `src/controllers/itemDetails.js` |
| Waarom geen plugin/configuratie | De detailpagina heeft geen uitbreidingspunt |
| Upstream-PR-kans | middel |
| Test | tests/test_patch_register.py |
"""

EMPTY_PATCHES = """# Patchregister

Geen core-patches.
"""

FORK_PATHS = """# fork-eigen
README.jelly-leon.md
docs/platform-v2/
tools/jelly-leon-web/
src/jelly-leon/
"""


@pytest.fixture()
def repos(tmp_path: Path) -> dict:
    """Upstream (tags v1.0.0, v1.0.1, v1.1, v1.2-rc1) en een fork op basis van v1.0.0 met één core-patch."""
    upstream = init_repo(tmp_path / "upstream")
    write(upstream, "LICENSE", GPL_HEAD)
    write(upstream, "CONTRIBUTORS.md", "- upstream-auteur\n")
    write(upstream, "package.json", package_json("1.0.0"))
    write(upstream, "package-lock.json", package_lock("1.0.0"))
    write(upstream, "src/controllers/itemDetails.js", "export function render() {\n    return 'details';\n}\n")
    write(upstream, "src/strings/nl.json", '{"Search": "Zoeken"}\n')
    base_commit = commit_all(upstream, "upstream 1.0.0")
    git(upstream, "tag", "-a", "v1.0.0", "-m", "1.0.0")

    fork = tmp_path / "fork"
    subprocess.run(["git", "clone", "-q", str(upstream), str(fork)], check=True)
    configure(fork)
    git(fork, "remote", "rename", "origin", "upstream")
    git(fork, "tag", "upstream-v1.0.0", base_commit)
    baseline = {
        "schema_version": "1",
        "upstream_tag": "v1.0.0",
        "upstream_version": "1.0.0",
        "upstream_commit": base_commit,
        "local_upstream_tag": "upstream-v1.0.0",
        "fork_version": "1.0.0-jl.0",
        "package_name": "jellyfin-web",
    }
    write(fork, "tools/jelly-leon-web/baseline.json", json.dumps(baseline, indent=2) + "\n")
    write(fork, "tools/jelly-leon-web/fork_paths.txt", FORK_PATHS)
    write(fork, "docs/platform-v2/PATCHES.md", PATCHES)
    write(fork, "README.jelly-leon.md", "# fork\n")
    write(fork, "src/jelly-leon/mediaguard.js", "export const knop = 'Vraag aan';\n")
    # Geregistreerde core-patch JLW-0001: één regel haak in de detailpagina.
    write(
        fork,
        "src/controllers/itemDetails.js",
        "import { knop } from '../jelly-leon/mediaguard';\n"
        "export function render() {\n    return 'details' + knop;\n}\n",
    )
    commit_all(fork, "fork-opzet")

    # Upstream gaat verder: 1.0.1 (compatibel), 1.1 (raakt de gepatchte regel → conflict), 1.2-rc1 (geen release).
    write(upstream, "package.json", package_json("1.0.1"))
    write(upstream, "package-lock.json", package_lock("1.0.1"))
    write(upstream, "src/strings/nl.json", '{"Search": "Zoeken", "Play": "Afspelen"}\n')
    v101 = commit_all(upstream, "upstream 1.0.1")
    git(upstream, "tag", "-a", "v1.0.1", "-m", "1.0.1")
    write(upstream, "package.json", package_json("1.1.0"))
    write(upstream, "package-lock.json", package_lock("1.1.0"))
    write(upstream, "src/controllers/itemDetails.js", "export function render() {\n    return 'details v2';\n}\n")
    v11 = commit_all(upstream, "upstream 1.1")
    git(upstream, "tag", "-a", "v1.1", "-m", "1.1")
    write(upstream, "src/strings/nl.json", '{"Search": "Zoeken", "Rc": "rc"}\n')
    commit_all(upstream, "upstream 1.2-rc1")
    git(upstream, "tag", "-a", "v1.2-rc1", "-m", "rc")
    return {"upstream": upstream, "fork": fork, "base": base_commit, "v101": v101, "v11": v11}
