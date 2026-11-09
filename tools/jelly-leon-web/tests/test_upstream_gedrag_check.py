"""Tests voor upstream_gedrag_check.py: register van upstream-gedrag, webdeel (B03-019 a, bouwplan §10.11)."""

from __future__ import annotations

from pathlib import Path

import pytest
import upstream_gedrag_check
from conftest import REPO_ROOT, write

HEADER = """# Register

| ID | Haak / gedrag | Bestand | Anker | Gebruikt door | Test |
|---|---|---|---|---|---|
"""
ROW_1 = "| UG-WEB-1 | detailpagina | `src/item.js` | `function reloadFromItem\\(item\\)` | B03-009 | anker |\n"
ROW_2 = "| UG-WEB-2 | standaardlayout | `src/apphost.js` | `function getDefaultLayout\\(\\) \\{\\s*return 'modern';` | smoke | anker |\n"


def make_repo(tmp_path: Path, register: str, files: dict[str, str] | None = None) -> Path:
    repo = tmp_path / "repo"
    write(repo, "tools/jelly-leon-web/fork_paths.txt", "docs/platform-v2/\ntools/jelly-leon-web/\nsrc/jelly-leon/\n")
    write(repo, upstream_gedrag_check.REGISTER_REL, register)
    defaults = {
        "src/item.js": "function reloadFromItem(item) {\n}\n",
        "src/apphost.js": "function getDefaultLayout() {\n    return 'modern';\n}\n",
    }
    for rel, text in {**defaults, **(files or {})}.items():
        write(repo, rel, text)
    return repo


def errors_for(repo: Path) -> list[str]:
    return upstream_gedrag_check.check(repo)[1]


def test_real_register_of_this_repo_is_complete_and_all_anchors_exist():
    entries, errors = upstream_gedrag_check.check(REPO_ROOT)
    assert errors == []
    assert len(entries) >= 19
    paths = {entry.path for entry in entries}
    # De geplande webhaken uit PATCHES.md en het gedrag van de smoketest staan er allemaal in.
    for needed in ("src/apps/legacy/controllers/itemDetails/index.js", "src/components/homesections/homesections.js",
                   "src/components/apphost.js", "src/components/playback/skipsegment.ts",
                   "src/apps/modern/components/AppToolbar/menus/SyncPlayMenu.tsx", "src/components/layoutManager.js"):
        assert needed in paths
    assert upstream_gedrag_check.main(["--repo", str(REPO_ROOT)]) == 0


def test_valid_register_passes_with_multiline_anchor(tmp_path):
    assert errors_for(make_repo(tmp_path, HEADER + ROW_1 + ROW_2)) == []


@pytest.mark.parametrize(
    "files, melding",
    [
        ({"src/item.js": "function reloadFromItem(item, user) {\n}\n"}, "anker niet gevonden"),   # signatuur anders
        ({"src/apphost.js": "function getDefaultLayout() {\n    return 'tv';\n}\n"}, "anker niet gevonden"),
    ],
)
def test_changed_upstream_behaviour_blocks(tmp_path, files, melding):
    errors = errors_for(make_repo(tmp_path, HEADER + ROW_1 + ROW_2, files))
    assert len(errors) == 1 and melding in errors[0]


def test_moved_file_blocks(tmp_path):
    repo = make_repo(tmp_path, HEADER + ROW_1)
    (repo / "src/item.js").unlink()
    assert any("bestaat niet (meer)" in e for e in errors_for(repo))


def test_register_rules(tmp_path):
    dubbel = HEADER + ROW_1 + ROW_1
    assert any("dubbele ID's" in e for e in errors_for(make_repo(tmp_path / "a", dubbel)))
    gat = HEADER + ROW_1 + ROW_2.replace("UG-WEB-2", "UG-WEB-4")
    assert any("niet doorlopend" in e for e in errors_for(make_repo(tmp_path / "b", gat)))
    pipe = HEADER + "| UG-WEB-1 | x | `src/item.js` | `a|b` | y | anker |\n"
    assert any("kolommen" in e for e in errors_for(make_repo(tmp_path / "c", pipe)))
    eigen = HEADER + "| UG-WEB-1 | x | `src/jelly-leon/hooks.js` | `x` | y | anker |\n"
    assert any("fork-eigen pad" in e for e in errors_for(make_repo(tmp_path / "d", eigen)))
    regex = HEADER + "| UG-WEB-1 | x | `src/item.js` | `function (` | y | anker |\n"
    assert any("geen geldige regex" in e for e in errors_for(make_repo(tmp_path / "e", regex)))
    leeg = HEADER
    assert any("geen enkele UG-WEB-regel" in e for e in errors_for(make_repo(tmp_path / "f", leeg)))
    zonder_test = HEADER + "| UG-WEB-1 | x | `src/item.js` | `function` | y |  |\n"
    assert any("verplicht" in e for e in errors_for(make_repo(tmp_path / "g", zonder_test)))


def test_reference_without_register_entry_fails(tmp_path):
    repo = make_repo(tmp_path, HEADER + ROW_1, {"docs/platform-v2/PATCHES.md": "Haak steunt op UG-WEB-1 en UG-WEB-7.\n"})
    errors = errors_for(repo)
    assert len(errors) == 1 and "UG-WEB-7" in errors[0] and "PATCHES.md:1" in errors[0]


def test_missing_register_is_a_violation_not_ok(tmp_path, capsys):
    repo = make_repo(tmp_path, HEADER + ROW_1)
    (repo / upstream_gedrag_check.REGISTER_REL).unlink()
    assert upstream_gedrag_check.main(["--repo", str(repo)]) == 1
    assert "ontbreekt" in capsys.readouterr().err
