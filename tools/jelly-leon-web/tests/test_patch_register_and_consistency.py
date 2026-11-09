"""Tests voor patch_register_check.py en check_fork_consistency.py (ADR-0002, ADR-0003, ADR-0005, contract §11)."""

from __future__ import annotations

import json
from pathlib import Path

import check_fork_consistency
import patch_register_check
from conftest import EMPTY_PATCHES, commit_all, git, package_json, write


def test_registered_core_patch_is_accepted(repos):
    errors, info = patch_register_check.check(repos["fork"], None, "HEAD")
    assert errors == []
    assert any("core-patch JLW-0001: M src/controllers/itemDetails.js" in line for line in info)


def test_unregistered_change_fails(repos):
    fork: Path = repos["fork"]
    write(fork, "src/strings/nl.json", '{"Search": "Zoek"}\n')
    commit_all(fork, "stille wijziging")
    errors, _ = patch_register_check.check(fork, None, "HEAD")
    assert any("src/strings/nl.json: niet-geregistreerde core-patch" in e for e in errors)
    assert patch_register_check.main(["--repo", str(fork)]) == 1


def test_fork_owned_paths_are_not_patches(repos):
    fork: Path = repos["fork"]
    write(fork, "src/jelly-leon/scenes.js", "export const s = 1;\n")
    write(fork, "docs/platform-v2/NIEUW.md", "# nieuw\n")
    commit_all(fork, "fork-eigen code")
    errors, _ = patch_register_check.check(fork, None, "HEAD")
    assert errors == []


def test_stale_register_entry_fails(repos):
    fork: Path = repos["fork"]
    git(fork, "checkout", repos["base"], "--", "src/controllers/itemDetails.js")
    commit_all(fork, "patch teruggedraaid")
    errors, _ = patch_register_check.check(fork, None, "HEAD")
    assert any("wijkt niet (meer) af" in e for e in errors)


def test_license_and_contributors_may_never_change(repos):
    fork: Path = repos["fork"]
    write(fork, "LICENSE", "MIT\n")
    (fork / "CONTRIBUTORS.md").unlink()
    commit_all(fork, "fout")
    errors, _ = patch_register_check.check(fork, None, "HEAD")
    assert any(e.startswith("LICENSE: mag nooit afwijken") for e in errors)
    assert any(e.startswith("CONTRIBUTORS.md: mag nooit afwijken") for e in errors)


def test_register_requires_fields_and_identity_note_for_package_json(repos):
    fork: Path = repos["fork"]
    register = (fork / "docs/platform-v2/PATCHES.md").read_text(encoding="utf-8")
    register = register.replace("`src/controllers/itemDetails.js`", "`src/controllers/itemDetails.js`, `package.json`")
    register = register.replace("| Upstream-PR-kans | middel |\n", "")
    write(fork, "docs/platform-v2/PATCHES.md", register)
    write(fork, "package.json", json.dumps({"name": "jellyfin-web", "version": "1.0.0", "x": 1}) + "\n")
    commit_all(fork, "afhankelijkheid toegevoegd")
    errors, _ = patch_register_check.check(fork, None, "HEAD")
    assert any("verplicht veld 'Upstream-PR-kans'" in e for e in errors)
    assert any("veld 'Technische identiteit'" in e for e in errors)


def test_missing_base_commit_is_environment_error(repos, capsys):
    fork: Path = repos["fork"]
    rc = patch_register_check.main(["--repo", str(fork), "--base", "0" * 40])
    assert rc == 3
    assert "fetch-depth: 0" in capsys.readouterr().err


def test_empty_register_with_clean_fork_is_ok(repos):
    fork: Path = repos["fork"]
    git(fork, "checkout", repos["base"], "--", "src/controllers/itemDetails.js")
    write(fork, "docs/platform-v2/PATCHES.md", EMPTY_PATCHES)
    commit_all(fork, "geen patches")
    errors, info = patch_register_check.check(fork, None, "HEAD")
    assert errors == []
    assert "0 in geregistreerde core-patches, 0 patches in register" in info[-1]


def test_consistency_ok_and_identity_violation(repos, capsys):
    fork: Path = repos["fork"]
    assert check_fork_consistency.main(["--repo", str(fork)]) == 0
    assert "technische identiteit jellyfin-web 1.0.0" in capsys.readouterr().out
    write(fork, "package.json", json.dumps({"name": "jelly-leon-web", "version": "1.0.0-jl.1"}) + "\n")
    commit_all(fork, "identiteit gewijzigd")
    baseline = json.loads((fork / "tools/jelly-leon-web/baseline.json").read_text(encoding="utf-8"))
    errors = check_fork_consistency.check_identity(fork, baseline)
    assert any("name 'jelly-leon-web'" in e for e in errors)
    assert any("version '1.0.0-jl.1'" in e for e in errors)


def test_consistency_detects_bad_baseline(repos):
    fork: Path = repos["fork"]
    baseline = json.loads((fork / "tools/jelly-leon-web/baseline.json").read_text(encoding="utf-8"))
    baseline["fork_version"] = "1.0.1-jl.0"
    errors = check_fork_consistency.check_baseline(fork, baseline)
    assert any("hoort bij 1.0.1" in e for e in errors)
    baseline["fork_version"] = "1.0.0"
    errors = check_fork_consistency.check_baseline(fork, baseline)
    assert any("volgt niet <upstream>-jl.<N>" in e for e in errors)
    baseline = dict(baseline, fork_version="1.0.0-jl.0", upstream_commit=repos["v101"])
    git(fork, "fetch", "-q", "upstream", "refs/tags/v1.0.1:refs/tags/v1.0.1")
    errors = check_fork_consistency.check_baseline(fork, baseline)
    assert any("geen voorouder van HEAD" in e for e in errors)


EVIDENCE_OK = {
    "id": "B03-001",
    "status": "Bezig",
    "validatie": "Sim-getest",
    "bewijs": "commit abc",
    "blokkade": "echte clients",
    "opmerking": "",
    "repo": "jelly-leon-web",
    "bijgewerkt": "2026-11-09",
}


def test_evidence_rules(repos):
    fork: Path = repos["fork"]
    write(fork, "docs/platform-v2/EVIDENCE.json", json.dumps([EVIDENCE_OK]))
    assert check_fork_consistency.check_evidence(fork) == []
    bad = [
        dict(EVIDENCE_OK, status="Gereed"),
        dict(EVIDENCE_OK, id="EX48", status="Geslaagd", validatie="Sim-geslaagd"),
        dict(EVIDENCE_OK, id="B03-013", status="Geblokkeerd", blokkade=""),
        dict(EVIDENCE_OK, id="B3-1", validatie="werkt"),
        dict(EVIDENCE_OK, id="B03-002", repo="jelly-leon"),
    ]
    write(fork, "docs/platform-v2/EVIDENCE.json", json.dumps(bad))
    errors = check_fork_consistency.check_evidence(fork)
    joined = "\n".join(errors)
    assert "status 'Gereed' vraagt echte acceptatie" in joined
    assert "status 'Geslaagd' vraagt echte acceptatie" in joined
    assert "Geblokkeerd zonder blokkade-reden" in joined
    assert "id 'B3-1' is geen Excel-ID" in joined
    assert "validatie 'werkt'" in joined
    assert "repo moet 'jelly-leon-web' zijn" in joined


def test_evidence_must_be_list(repos):
    fork: Path = repos["fork"]
    write(fork, "docs/platform-v2/EVIDENCE.json", json.dumps(EVIDENCE_OK))
    assert check_fork_consistency.check_evidence(fork) == ["docs/platform-v2/EVIDENCE.json: verwacht een JSON-lijst (contract §11)"]


def test_package_json_helper_roundtrip():
    assert json.loads(package_json("9.9.9"))["version"] == "9.9.9"
