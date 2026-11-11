"""EVIDENCE.json volgens contract 1.3 §11 (C1.3-ALG-02, C1.3-JLW-02) — tools/jelly-leon-web/check_fork_consistency.py.

Nieuw in 1.3 ten opzichte van de 1.2-controle (test_patch_register_and_consistency.py):
- validatiewaarden `Intel-iGPU-getest (ontwikkelmachine)` en `Niet getest` (alleen bij status `Niet gestart`);
- een lege `validatie` is nooit toegestaan, ook niet als alleen spaties;
- elke `NIET GEVALIDEERD (…)` uit `blokkade` is een lijstwaarde en staat ook in `validatie`; een afwijkende
  schrijfwijze van zo'n reden ontloopt die vergelijking niet maar is zelf een fout;
- contractpunten (`C1.3-<code>`, `C1.2-<code>`) en reviews (`REVIEW-jelly-leon-web-<onderwerp>`) mogen een eigen regel
  hebben, met de statussen van het blad Werkpakketten.
De laatste test draait de controle op de echte EVIDENCE.json van deze repo (dezelfde controle als de CI-stap).
"""

from __future__ import annotations

import json
from pathlib import Path

import check_fork_consistency
import pytest
from conftest import REPO_ROOT, write

EVIDENCE = "docs/platform-v2/EVIDENCE.json"
BASIS = {
    "id": "B03-014",
    "status": "Bezig",
    "validatie": "Sim-getest",
    "bewijs": "tools/jelly-leon-web/tests/test_evidence_contract_1_3.py",
    "blokkade": "",
    "opmerking": "",
    "repo": "jelly-leon-web",
    "bijgewerkt": "2026-11-10",
}
CONFORMITEIT_13 = """# Conformiteit met contract 1.3 — test

## 0. Voor alle repos (ALG)

| ID | Wijziging | Contract | Bestanden | Moment |
|---|---|---|---|---|
| C1.3-ALG-01 | Kopie | kop | — | NU |
| C1.3-ALG-02 | EVIDENCE | §11 | — | NU |

## 9. jelly-leon (server-fork)

| ID | Wijziging | Contract | Bestanden | Moment |
|---|---|---|---|---|
| C1.3-JL-01 | Kopie | kop | — | NU |

## 10. jelly-leon-web (web-fork)

| ID | Wijziging | Contract | Bestanden | Moment |
|---|---|---|---|---|
| C1.3-JLW-01 | Kopie + drifttest-pin | kop | — | NU |
| C1.3-JLW-02 | EVIDENCE-consistentie | §11 | — | NU |

## 11. jelly-leon-clients

| C1.3-JLC-01 | Kopie | kop | — | NU |
"""
CONFORMITEIT_12 = """# Conformiteit met contract 1.2 — test

## 0. Voor alle repos

- **A1** Kopie van het contract.
- **A4** `EVIDENCE.json`.

## 9. jelly-leon (server-fork)

| # | Wijziging | Bestanden |
|---|---|---|
| J1 | Server | — |

## 10. jelly-leon-web (web-fork)

| # | Wijziging | Bestanden |
|---|---|---|
| JW1 | Upgradefase | — |
| JW3 | Opnieuw proberen | — |
"""


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    write(root, "docs/platform-v2/CONTRACT_1.3_CONFORMITEIT.md", CONFORMITEIT_13)
    write(root, "docs/platform-v2/CONTRACT_1.2_CONFORMITEIT.md", CONFORMITEIT_12)
    return root


def fouten(repo: Path, *entries: dict) -> list[str]:
    write(repo, EVIDENCE, json.dumps(list(entries), ensure_ascii=False) + "\n")
    return check_fork_consistency.check_evidence(repo)


# ------------------------------------------------------------------------------------- nieuwe waarden in 1.3


@pytest.mark.parametrize(
    "entry",
    [
        dict(BASIS, status="Niet gestart", validatie="Niet getest"),
        dict(BASIS, status="Niet gestart", validatie="Niet getest; NIET GEVALIDEERD (echte NAS)",
             blokkade="wacht op de NAS: NIET GEVALIDEERD (echte NAS)"),
        dict(BASIS, id="JLT-12", status="Niet gestart", validatie="Niet getest"),
        dict(BASIS, validatie="Intel-iGPU-getest (ontwikkelmachine); NIET GEVALIDEERD (hardware)"),
        dict(BASIS, validatie="Sim-getest; Intel-iGPU-getest (ontwikkelmachine); NIET GEVALIDEERD (hardware)"),
        dict(BASIS, status="Niet gestart", validatie="NIET GEVALIDEERD (echte NAS)"),
    ],
    ids=["niet-getest", "niet-getest-met-nas", "testrij-niet-gestart", "igpu", "igpu-en-sim", "niet-gestart-nas"],
)
def test_nieuwe_waarden_van_1_3_zijn_toegestaan(repo, entry):
    assert fouten(repo, entry) == []


@pytest.mark.parametrize("status", ["Bezig", "Geblokkeerd", "N.v.t."])
def test_niet_getest_alleen_bij_niet_gestart(repo, status):
    entry = dict(BASIS, status=status, validatie="Niet getest", blokkade="reden" if status == "Geblokkeerd" else "")
    assert fouten(repo, entry) == [
        f"{EVIDENCE}[B03-014]: validatie 'Niet getest' mag alleen bij status 'Niet gestart' (contract §11, 1.3), "
        f"niet bij '{status}'"
    ]


def test_niet_getest_naast_een_testuitkomst_is_tegenstrijdig(repo):
    errors = fouten(repo, dict(BASIS, status="Niet gestart", validatie="Niet getest; Sim-getest"))
    assert errors == [
        f"{EVIDENCE}[B03-014]: validatie 'Niet getest; Sim-getest' zegt tegelijk 'Niet getest' en Sim-getest "
        "(tegenstrijdig; kies één)"
    ]
    errors = fouten(repo, dict(BASIS, id="JLT-12", status="Niet gestart", validatie="Niet getest; Sim-geslaagd"))
    assert len(errors) == 1 and "tegelijk 'Niet getest' en Sim-geslaagd" in errors[0]


@pytest.mark.parametrize("validatie", ["Sim-getest", "Unit-getest; NIET GEVALIDEERD (echte NAS)"])
def test_niet_gestart_met_testuitkomst_is_tegenstrijdig(repo, validatie):
    errors = fouten(repo, dict(BASIS, status="Niet gestart", validatie=validatie))
    assert len(errors) == 1 and "status 'Niet gestart' met testuitkomst" in errors[0], errors


def test_igpu_zonder_hardwarevoorbehoud_faalt(repo):
    """Het bewijs op de ontwikkelmachine zegt niets over de GPU's van de NAS (§11: die blijven NIET GEVALIDEERD)."""
    errors = fouten(repo, dict(BASIS, validatie="Intel-iGPU-getest (ontwikkelmachine)"))
    assert errors == [
        f"{EVIDENCE}[B03-014]: 'Intel-iGPU-getest (ontwikkelmachine)' zegt niets over de GPU's van de NAS; zet er "
        "'NIET GEVALIDEERD (hardware)' naast (contract §11, 1.3)"
    ]


@pytest.mark.parametrize(
    "validatie",
    ["Intel-iGPU-getest", "Intel-iGPU-getest (NAS)", "niet getest", "Niet getest (nog)", "Niet-getest"],
)
def test_varianten_van_de_nieuwe_waarden_zijn_vrije_tekst(repo, validatie):
    errors = fouten(repo, dict(BASIS, status="Niet gestart", validatie=validatie))
    assert any(f"validatie '{validatie}' is geen toegestane waarde" in e for e in errors), errors


@pytest.mark.parametrize("validatie", ["", " ", "   "])
def test_lege_validatie_nooit_toegestaan(repo, validatie):
    errors = fouten(repo, dict(BASIS, validatie=validatie))
    assert errors and all("validatie" in e for e in errors), errors


# ------------------------------------------------------------------------------- blokkade ↔ validatie (1.3)


def test_elke_niet_gevalideerd_uit_blokkade_staat_in_validatie(repo):
    goed = dict(BASIS, validatie="Sim-getest; NIET GEVALIDEERD (account); NIET GEVALIDEERD (Mac/Xcode)",
                blokkade="GitHub-geheim: NIET GEVALIDEERD (account); Swiftfin: NIET GEVALIDEERD (Mac/Xcode)")
    assert fouten(repo, goed) == []
    fout = dict(goed, validatie="Sim-getest; NIET GEVALIDEERD (account)")
    assert fouten(repo, fout) == [
        f"{EVIDENCE}[B03-014]: blokkade noemt 'NIET GEVALIDEERD (Mac/Xcode)', maar validatie niet (zet het als "
        "lijstwaarde in 'validatie')"
    ]


@pytest.mark.parametrize("reden", ["NIET GEVALIDEERD (echte tv)", "NIET GEVALIDEERD (echte NAS, hardware)"])
def test_blokkade_met_onbekende_reden_faalt(repo, reden):
    errors = fouten(repo, dict(BASIS, blokkade=f"x: {reden}"))
    assert len(errors) == 1 and f"'{reden}', dat is geen waarde uit de vaste lijst" in errors[0], errors


@pytest.mark.parametrize(
    "blokkade",
    [
        "echte NAS: niet gevalideerd (echte NAS)",
        "echte NAS: Niet gevalideerd (echte NAS)",
        "echte NAS: NIET GEVALIDEERD(echte NAS)",
        "echte NAS: NIET GEVALIDEERD  (echte NAS)",
        "echte NAS: NIET GEVALIDEERD\n(echte NAS)",
        "echte NAS: NIET GEVALIDEERD (echte NAS",
        "NIET GEVALIDEERD op de echte NAS",
        "NIETGEVALIDEERD (echte NAS)",
    ],
    ids=["kleine-letters", "alleen-beginhoofdletter", "zonder-spatie", "dubbele-spatie", "regeleinde",
         "haakje-niet-gesloten", "zonder-haakjes", "aaneen"],
)
@pytest.mark.parametrize("validatie", ["Sim-getest", "Sim-getest; NIET GEVALIDEERD (echte NAS)"])
def test_afwijkende_schrijfwijze_in_blokkade_ontloopt_de_controle_niet(repo, blokkade, validatie):
    """Tegenproef van de review: een bijna-goede reden werd niet herkend en dus nooit met `validatie` vergeleken.

    Ook met de juiste waarde in `validatie` blijft het een fout: de blokkade zelf moet de vaste schrijfwijze dragen.
    """
    errors = fouten(repo, dict(BASIS, validatie=validatie, blokkade=blokkade))
    assert len(errors) == 1 and "anders dan de vaste lijst van §11" in errors[0], errors
    assert "NIET GEVALIDEERD (echte NAS) | NIET GEVALIDEERD (hardware)" in errors[0]


def test_afwijkende_schrijfwijze_naast_een_juiste_reden_wordt_apart_gemeld(repo):
    entry = dict(
        BASIS,
        validatie="Sim-getest",
        blokkade="tv's: NIET GEVALIDEERD (hardware); NAS: niet gevalideerd (echte NAS); NIET GEVALIDEERD(account)",
    )
    errors = fouten(repo, entry)
    assert len(errors) == 3, errors
    assert "blokkade noemt 'NIET GEVALIDEERD (hardware)', maar validatie niet" in errors[0]
    assert "blokkade schrijft 'niet gevalideerd (echte NAS)' anders" in errors[1]
    assert "blokkade schrijft 'NIET GEVALIDEERD(account)' anders" in errors[2]


@pytest.mark.parametrize(
    "blokkade",
    [
        "upstream-sync.yml is nog niet gevalideerd op GitHub",
        "Niet gevalideerd op echte apparaten; dat hoort bij jelly-leon-clients",
        "wacht op de NAS: NIET GEVALIDEERD (echte NAS); verder niet gevalideerd op een tweede NAS",
    ],
    ids=["lopende-tekst", "zin-met-beginhoofdletter", "naast-exacte-reden"],
)
def test_lopende_tekst_in_blokkade_is_geen_lijstwaarde(repo, blokkade):
    """Gewone tekst (kleine letters, geen haakje) is geen poging tot een lijstwaarde en blijft toegestaan."""
    assert fouten(repo, dict(BASIS, validatie="Sim-getest; NIET GEVALIDEERD (echte NAS)", blokkade=blokkade)) == []


# -------------------------------------------------------------------------------- contractpunten en reviews


@pytest.mark.parametrize(
    "entry_id",
    ["C1.3-JLW-01", "C1.3-JLW-02", "C1.3-ALG-01", "C1.2-JW1", "C1.2-A4", "REVIEW-jelly-leon-web-contract-1.3"],
)
def test_contractpunten_en_reviews_van_deze_repo_mogen(repo, entry_id):
    assert fouten(repo, dict(BASIS, id=entry_id, validatie="Unit-getest")) == []


@pytest.mark.parametrize(
    "entry_id, melding",
    [
        ("C1.3-JLW-09", "staat niet in docs/platform-v2/CONTRACT_1.3_CONFORMITEIT.md"),   # bestaat niet
        ("C1.3-JL-01", "staat niet in docs/platform-v2/CONTRACT_1.3_CONFORMITEIT.md"),    # punt van de serverfork
        ("C1.3-JLC-01", "staat niet in docs/platform-v2/CONTRACT_1.3_CONFORMITEIT.md"),   # punt van de clients
        ("C1.2-J1", "staat niet in docs/platform-v2/CONTRACT_1.2_CONFORMITEIT.md"),        # 1.2-punt van de server
        ("C1.2-JW2", "staat niet in docs/platform-v2/CONTRACT_1.2_CONFORMITEIT.md"),       # niet in de (test)lijst
        ("C1.3-JLW-1", "volgt niet C1.3-<REPO>-<nn>"),
        ("C1.3-jlw-01", "volgt niet C1.3-<REPO>-<nn>"),
        ("C1.4-JLW-01", "volgt niet C1.3-<REPO>-<nn>"),
        ("C1.2-H", "volgt niet C1.3-<REPO>-<nn>"),
        ("REVIEW-jelly-leon-contract", "volgt niet REVIEW-jelly-leon-web-<onderwerp>"),
        ("REVIEW-jelly-leon-web-", "volgt niet REVIEW-jelly-leon-web-<onderwerp>"),
        ("REVIEW-jelly-leon-web-Contract", "volgt niet REVIEW-jelly-leon-web-<onderwerp>"),
    ],
)
def test_onbekende_of_vreemde_contractpunten_falen(repo, entry_id, melding):
    errors = fouten(repo, dict(BASIS, id=entry_id, validatie="Unit-getest"))
    assert len(errors) == 1 and melding in errors[0], errors


def test_contractpunt_zonder_gekopieerde_lijst_is_nooit_in_orde(repo):
    (repo / "docs/platform-v2/CONTRACT_1.3_CONFORMITEIT.md").unlink()
    errors = fouten(repo, dict(BASIS, id="C1.3-JLW-01", validatie="Unit-getest"))
    assert errors == [
        f"{EVIDENCE}[C1.3-JLW-01]: docs/platform-v2/CONTRACT_1.3_CONFORMITEIT.md ontbreekt; contractpunt 'C1.3-JLW-01' "
        "is niet te controleren (fail-closed)"
    ]


@pytest.mark.parametrize("status", ["Gereed", "Geslaagd", "Open", "Mislukt"])
def test_contractpunten_volgen_het_blad_werkpakketten(repo, status):
    errors = fouten(repo, dict(BASIS, id="C1.3-JLW-02", status=status, validatie="Unit-getest"))
    assert any("status" in e for e in errors), errors


def test_contractpunt_krijgt_geen_testmatrixwaarde(repo):
    errors = fouten(repo, dict(BASIS, id="C1.3-JLW-01", validatie="Sim-geslaagd"))
    assert any("validatie 'Sim-geslaagd' is geen toegestane waarde" in e for e in errors), errors


def test_dubbel_contractpunt_faalt(repo):
    entry = dict(BASIS, id="C1.3-JLW-01", validatie="Unit-getest")
    assert any("dubbel id" in e for e in fouten(repo, entry, entry))


# ------------------------------------------------------------------------------------- de echte stand


def test_echte_conformiteitslijsten_kennen_de_punten_van_deze_repo():
    punten_13 = check_fork_consistency.conformiteit_punten(REPO_ROOT, check_fork_consistency.CONFORMITEIT_13_REL)
    punten_12 = check_fork_consistency.conformiteit_punten(REPO_ROOT, check_fork_consistency.CONFORMITEIT_12_REL)
    assert punten_13 is not None and {"C1.3-JLW-01", "C1.3-JLW-02", "C1.3-ALG-01", "C1.3-ALG-02"} <= punten_13
    assert not any(p.startswith(("C1.3-JL-", "C1.3-JLC-", "C1.3-ASM-")) for p in punten_13)
    assert punten_12 is not None and {"A1", "A4", "JW1", "JW2", "JW3"} <= punten_12


def test_echte_evidence_volgt_1_3_en_heeft_de_contractpunten():
    assert check_fork_consistency.check_evidence(REPO_ROOT) == []
    items = {item["id"]: item for item in json.loads((REPO_ROOT / EVIDENCE).read_text(encoding="utf-8"))}
    for punt in ("C1.3-JLW-01", "C1.3-JLW-02"):
        assert punt in items, punt
        assert items[punt]["status"] in {"Bezig", "Geblokkeerd"}  # nooit Gereed in deze bouwomgeving
    for item in items.values():
        assert item["validatie"].strip()
