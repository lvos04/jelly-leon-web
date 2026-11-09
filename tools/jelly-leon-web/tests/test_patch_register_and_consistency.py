"""Tests voor patch_register_check.py en check_fork_consistency.py (ADR-0002, ADR-0003, ADR-0005, contract §11)."""

from __future__ import annotations

import json
from pathlib import Path

import check_fork_consistency
import patch_register_check
import pytest
from conftest import EMPTY_PATCHES, REPO_ROOT, commit_all, git, package_json, write


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


def test_evidence_validatie_exact_volgens_section_11_contract_1_2(repos):
    """A4: alleen waarden uit de vaste lijst, gescheiden door '; '; toelichting hoort in 'opmerking'."""
    fork: Path = repos["fork"]
    good = [
        dict(EVIDENCE_OK, id="B03-001", validatie="Sim-getest; NIET GEVALIDEERD (hardware)"),
        dict(EVIDENCE_OK, id="B03-013", validatie="Unit-getest; Sim-getest; NIET GEVALIDEERD (echte NAS)"),
        dict(EVIDENCE_OK, id="EX48", validatie="Sim-geslaagd"),
        dict(EVIDENCE_OK, id="EX49", validatie="Sim-mislukt; NIET GEVALIDEERD (echte NAS)"),
        dict(EVIDENCE_OK, id="D15", status="Open", validatie="NIET GEVALIDEERD (hardware)"),
    ]
    write(fork, "docs/platform-v2/EVIDENCE.json", json.dumps(good))
    assert check_fork_consistency.check_evidence(fork) == []

    bad = {
        "B03-002": "Sim-getest (headless Chromium)",      # vrije tekst achter een geldige waarde
        "B03-003": "NIET GEVALIDEERD",                     # zonder reden uit de lijst
        "B03-004": "Sim-getest;NIET GEVALIDEERD (hardware)",  # verkeerd scheidingsteken
        "B03-005": "Sim-getest; Sim-getest",               # dubbel
        "B03-006": "Sim-geslaagd",                         # alleen voor de testmatrix (EX..)
        "B03-007": "",                                     # leeg
        "B03-008": "Sim-getest; ",                         # lege tweede waarde
    }
    write(fork, "docs/platform-v2/EVIDENCE.json",
          json.dumps([dict(EVIDENCE_OK, id=key, validatie=value) for key, value in bad.items()]))
    errors = check_fork_consistency.check_evidence(fork)
    for key in bad:
        assert any(f"[{key}]" in e and "validatie" in e for e in errors), key
    assert any("[B03-002]: validatie 'Sim-getest (headless Chromium)' is geen toegestane waarde" in e for e in errors)
    assert any("[B03-005]" in e and "dubbel" in e for e in errors)
    assert any("[B03-007]: validatie ontbreekt" in e for e in errors)


def test_evidence_alleen_velden_uit_section_11_en_bewijs_verplicht(repos):
    fork: Path = repos["fork"]
    write(fork, "docs/platform-v2/EVIDENCE.json",
          json.dumps([dict(EVIDENCE_OK, toelichting="hoort in opmerking"), dict(EVIDENCE_OK, id="B03-002", bewijs=" ")]))
    joined = "\n".join(check_fork_consistency.check_evidence(fork))
    assert "velden toelichting horen niet bij §11" in joined
    assert "[B03-002]: bewijs is leeg" in joined


def test_evidence_genoemde_commits_bestaan_echt(repos):
    """Eerlijkheid: een commit in 'bewijs' die niet bestaat, faalt; digests, run-ID's en <repo>@<sha> tellen niet."""
    fork: Path = repos["fork"]
    head = git(fork, "rev-parse", "--short=9", "HEAD")
    full = git(fork, "rev-parse", "HEAD")
    ok = (f"commits {head}, {full}; image jellyfin:10.11.11@sha256:aefb67e6a7ff; integriteit sha512-5rjszPzcabcdef1; "
          "GitHub Actions run 42610233474; serverdeel jelly-leon@d4bc20d6a; https://example.invalid/x/abcdef12345")
    write(fork, "docs/platform-v2/EVIDENCE.json", json.dumps([dict(EVIDENCE_OK, bewijs=ok)]))
    assert check_fork_consistency.check_evidence(fork) == []

    write(fork, "docs/platform-v2/EVIDENCE.json", json.dumps([dict(EVIDENCE_OK, bewijs=f"commits {head}, deadbeef42")]))
    errors = check_fork_consistency.check_evidence(fork)
    assert errors == [
        "docs/platform-v2/EVIDENCE.json[B03-001]: commit deadbeef42 uit 'bewijs' bestaat niet in deze repo "
        "(andere repo? schrijf <repo>@deadbeef42)"
    ]


def test_evidence_van_deze_repo_volgt_section_11():
    """De echte docs/platform-v2/EVIDENCE.json (zelfde controle als de CI-stap check_fork_consistency.py)."""
    assert check_fork_consistency.check_evidence(REPO_ROOT) == []
    items = json.loads((REPO_ROOT / "docs/platform-v2/EVIDENCE.json").read_text(encoding="utf-8"))
    assert items and all(item["status"] not in {"Gereed", "Geslaagd"} for item in items)


def test_evidence_must_be_list(repos):
    fork: Path = repos["fork"]
    write(fork, "docs/platform-v2/EVIDENCE.json", json.dumps(EVIDENCE_OK))
    assert check_fork_consistency.check_evidence(fork) == ["docs/platform-v2/EVIDENCE.json: verwacht een JSON-lijst (contract §11)"]


def test_evidence_ontbrekend_of_leeg_is_nooit_in_orde(repos, capsys):
    """Fail-closed: zonder bewijsbestand (of met een lege lijst) meldt de CI-stap nooit "in orde"."""
    fork: Path = repos["fork"]
    assert check_fork_consistency.main(["--repo", str(fork)]) == 0
    capsys.readouterr()
    (fork / "docs/platform-v2/EVIDENCE.json").unlink()
    assert check_fork_consistency.check_evidence(fork) == [
        "docs/platform-v2/EVIDENCE.json ontbreekt (contract §11: elke repo houdt EVIDENCE.json bij)"
    ]
    assert check_fork_consistency.main(["--repo", str(fork)]) == 1
    captured = capsys.readouterr()
    assert "in orde" not in captured.out
    assert "EVIDENCE.json ontbreekt" in captured.err
    write(fork, "docs/platform-v2/EVIDENCE.json", "[]\n")
    assert check_fork_consistency.check_evidence(fork) == [
        "docs/platform-v2/EVIDENCE.json: lege lijst — geen enkel bewijs vastgelegd (contract §11)"
    ]
    assert check_fork_consistency.main(["--repo", str(fork)]) == 1


def test_evidence_blokkade_staat_ook_in_validatie(repos):
    """Een NIET GEVALIDEERD-blokkade die niet in `validatie` staat, zou in de Excel als volledig Sim-getest lezen."""
    fork: Path = repos["fork"]
    good = dict(EVIDENCE_OK, validatie="Sim-getest; NIET GEVALIDEERD (echte NAS); NIET GEVALIDEERD (hardware)",
                blokkade="echte NAS: NIET GEVALIDEERD (echte NAS); echte tv's: NIET GEVALIDEERD (hardware)")
    write(fork, "docs/platform-v2/EVIDENCE.json", json.dumps([good]))
    assert check_fork_consistency.check_evidence(fork) == []
    bad = [
        dict(good, validatie="Sim-getest; NIET GEVALIDEERD (hardware)"),
        dict(good, id="B03-013", validatie="Sim-getest", blokkade="NIET GEVALIDEERD (echte NAS/hardware)"),
    ]
    write(fork, "docs/platform-v2/EVIDENCE.json", json.dumps(bad))
    errors = check_fork_consistency.check_evidence(fork)
    assert errors == [
        "docs/platform-v2/EVIDENCE.json[B03-001]: blokkade noemt 'NIET GEVALIDEERD (echte NAS)', maar validatie niet "
        "(zet het als lijstwaarde in 'validatie')",
        "docs/platform-v2/EVIDENCE.json[B03-013]: blokkade noemt 'NIET GEVALIDEERD (echte NAS/hardware)', maar "
        "validatie niet (zet het als lijstwaarde in 'validatie')",
    ]


@pytest.mark.parametrize("datum", ["2026-02-30", "2026-13-01", "9-11-2026", "", "2026-11-09T12:00:00Z"])
def test_evidence_bijgewerkt_is_een_echte_datum(repos, datum):
    fork: Path = repos["fork"]
    write(fork, "docs/platform-v2/EVIDENCE.json", json.dumps([dict(EVIDENCE_OK, bijgewerkt=datum)]))
    assert check_fork_consistency.check_evidence(fork) == [
        "docs/platform-v2/EVIDENCE.json[B03-001]: bijgewerkt moet een echte datum JJJJ-MM-DD zijn"
    ]


def test_package_json_helper_roundtrip():
    assert json.loads(package_json("9.9.9"))["version"] == "9.9.9"


# --------------------------------------------------------------------------------- zichtbare naam (JLW-0002)

BRAND_HTML = '<html>\n<meta name="application-name" content="Jellyfin">\n<title>Jellyfin</title>\n</html>\n'
BRAND_CONFIG = {"naam": "Jelly Leon", "upstream_naam": "Jellyfin", "patch": "JLW-0002", "bestanden": ["src/index.html"]}


def brand_fork(tmp_path: Path, fork_html: str, config: object = BRAND_CONFIG) -> tuple[Path, dict]:
    """Mini-upstream met src/index.html en een fork met de gegeven versie en baseline-configuratie."""
    from conftest import init_repo

    repo = init_repo(tmp_path / "merk")
    write(repo, "src/index.html", BRAND_HTML)
    base = commit_all(repo, "upstream")
    write(repo, "src/index.html", fork_html)  # de controle leest de werkboom, net als package.json
    baseline = {"upstream_commit": base}
    if config is not None:
        baseline["zichtbare_naam"] = config
    return repo, baseline


def test_zichtbare_naam_pure_vervanging_is_in_orde(tmp_path):
    repo, baseline = brand_fork(tmp_path, BRAND_HTML.replace("Jellyfin", "Jelly Leon"))
    assert check_fork_consistency.check_visible_name(repo, baseline) == []


@pytest.mark.parametrize(
    "fork_html, melding",
    [
        (BRAND_HTML, "ontbreekt (JLW-0002 niet toegepast)"),                                 # patch kwijt
        (BRAND_HTML.replace("<title>Jellyfin", "<title>Jelly Leon Server"), "geen pure naamwijziging"),
        (BRAND_HTML.replace("</html>", "<script src=x></script>\n</html>"), "niets toevoegen of weghalen"),
        (BRAND_HTML.replace("Jellyfin", "Jelly Leon").replace("ltr", "rtl").replace(
            "<html>", '<html lang="nl">'), "geen pure naamwijziging"),                        # meegesmokkelde wijziging
    ],
)
def test_zichtbare_naam_alleen_de_naam_en_niets_anders(tmp_path, fork_html, melding):
    repo, baseline = brand_fork(tmp_path, fork_html)
    errors = check_fork_consistency.check_visible_name(repo, baseline)
    assert errors and any(melding in e for e in errors), errors


def test_zichtbare_naam_onvolledige_configuratie_faalt(tmp_path):
    repo, baseline = brand_fork(tmp_path, BRAND_HTML, config={"naam": "Jelly Leon", "bestanden": []})
    assert any("vraagt naam, upstream_naam" in e for e in check_fork_consistency.check_visible_name(repo, baseline))
    repo, baseline = brand_fork(tmp_path / "b", BRAND_HTML, config=None)
    assert check_fork_consistency.check_visible_name(repo, baseline) == []


def test_zichtbare_naam_van_deze_repo_is_vastgelegd_en_in_orde():
    """De echte fork legt de merkwijziging vast in baseline.json en wijkt alleen in de naam af (JLW-0002)."""
    baseline = json.loads((REPO_ROOT / "tools/jelly-leon-web/baseline.json").read_text(encoding="utf-8"))
    config = baseline["zichtbare_naam"]
    assert config["naam"] == "Jelly Leon" and config["upstream_naam"] == "Jellyfin" and config["patch"] == "JLW-0002"
    assert set(config["bestanden"]) == {"src/index.html", "src/manifest.json", "src/scripts/libraryMenu.js"}
    assert check_fork_consistency.check_visible_name(REPO_ROOT, baseline) == []
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert (package["name"], package["version"]) == ("jellyfin-web", baseline["upstream_version"])
    apphost = (REPO_ROOT / "src/components/apphost.js").read_text(encoding="utf-8")
    assert "const appName = 'Jellyfin Web';" in apphost  # clientnaam richting server blijft "Jellyfin Web"


def test_evidence_jlt_testrijen_volgen_testmatrixregels(repos):
    fork: Path = repos["fork"]
    entry = {"id": "JLT-60", "status": "Bezig", "validatie": "Sim-geslaagd; NIET GEVALIDEERD (echte NAS)",
             "bewijs": "tests", "blokkade": "", "opmerking": "", "repo": "jelly-leon-web", "bijgewerkt": "2026-11-09"}
    write(fork, "docs/platform-v2/EVIDENCE.json", json.dumps([entry]) + "\n")
    assert check_fork_consistency.check_evidence(fork) == []
    for bad in ({"status": "Geslaagd"}, {"id": "JLT-6"}, {"status": "Gereed"}):
        write(fork, "docs/platform-v2/EVIDENCE.json", json.dumps([dict(entry, **bad)]) + "\n")
        assert check_fork_consistency.check_evidence(fork), bad
    # Sim-geslaagd mag alleen bij testrijen, niet bij een werkpakket.
    write(fork, "docs/platform-v2/EVIDENCE.json", json.dumps([dict(entry, id="B03-014")]) + "\n")
    assert any("Sim-geslaagd" in e for e in check_fork_consistency.check_evidence(fork))

