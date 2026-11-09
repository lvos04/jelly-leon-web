"""Drifttest van de platformcontract-kopieën (contract 1.2, A1) — tools/jelly-leon-web/contract_drift.py.

De eerste test is de echte drifttest op deze repo (draait in CI in de job forkregels); de rest bewijst met een nep-bron
(tijdelijke git-repo, nep-HTTP) dat elke vorm van drift of een onbereikbare bron als fout wordt gemeld en nooit als
"in orde".
"""

from __future__ import annotations

import hashlib
import io
import urllib.error
from pathlib import Path

import contract_drift
import pytest
from conftest import REPO_ROOT, commit_all, init_repo, write

CONTRACT = "docs/platform-v2/PLATFORM_CONTRACTEN.md"
CONFORMITEIT = "docs/platform-v2/CONTRACT_1.2_CONFORMITEIT.md"
SIBLING_SOURCE = REPO_ROOT.parent / "ai-server-manager"


def pins_for(texts: dict[str, bytes]) -> dict[str, str]:
    return {rel: hashlib.sha256(data).hexdigest() for rel, data in texts.items()}


@pytest.fixture()
def kopie(tmp_path: Path) -> tuple[Path, dict[str, bytes]]:
    texts = {
        CONTRACT: "# Platformcontracten\n\nVersie: `contracts 1.2` · test\n".encode(),
        CONFORMITEIT: "# Conformiteit 1.2\n".encode(),
    }
    repo = tmp_path / "kopie"
    for rel, data in texts.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_bytes(data)
    return repo, texts


def test_echte_kopieen_zijn_byte_gelijk_aan_de_vastgezette_bron():
    """De drifttest zelf: beide kopieën in deze repo hebben exact de sha256 van de bron-commit."""
    assert contract_drift.check_pins(REPO_ROOT) == []
    assert set(contract_drift.KOPIEEN) == {CONTRACT, CONFORMITEIT}
    assert contract_drift.VERSIEKOP in (REPO_ROOT / CONTRACT).read_bytes()
    assert len(contract_drift.BRON_COMMIT) == 40


@pytest.mark.skipif(not (SIBLING_SOURCE / ".git").exists(), reason="geen lokale checkout van ai-server-manager")
def test_echte_kopieen_tegen_lokale_bron_op_de_bron_commit():
    """Alleen lokaal (naastgelegen checkout): kopie == git show <bron-commit>:<pad>."""
    errors, _warnings = contract_drift.compare_with_source(
        REPO_ROOT, contract_drift.git_reader(SIBLING_SOURCE, contract_drift.BRON_COMMIT), None
    )
    assert errors == []


def test_gewijzigde_kopie_faalt(kopie):
    repo, texts = kopie
    pins = pins_for(texts)
    assert contract_drift.check_pins(repo, pins) == []
    (repo / CONFORMITEIT).write_bytes(texts[CONFORMITEIT] + b"lokale aanpassing\n")
    errors = contract_drift.check_pins(repo, pins)
    assert len(errors) == 1 and "kopie is gewijzigd" in errors[0] and CONFORMITEIT in errors[0]


def test_alleen_regeleinden_anders_faalt_ook(kopie):
    repo, texts = kopie
    pins = pins_for(texts)
    (repo / CONTRACT).write_bytes(texts[CONTRACT].replace(b"\n", b"\r\n"))
    assert any("kopie is gewijzigd" in e for e in contract_drift.check_pins(repo, pins))


def test_ontbrekende_kopie_faalt(kopie):
    repo, texts = kopie
    (repo / CONTRACT).unlink()
    errors = contract_drift.check_pins(repo, pins_for(texts))
    assert errors and "ontbreekt" in errors[0] and "A1" in errors[0]


def test_ontbrekende_versiekop_faalt(kopie):
    repo, texts = kopie
    oud = texts[CONTRACT].replace(b"contracts 1.2", b"contracts 1.1")
    (repo / CONTRACT).write_bytes(oud)
    errors = contract_drift.check_pins(repo, pins_for({CONTRACT: oud, CONFORMITEIT: texts[CONFORMITEIT]}))
    assert errors == ["docs/platform-v2/PLATFORM_CONTRACTEN.md: versiekop Versie: `contracts 1.2` ontbreekt"]


def test_vergelijking_met_bron_in_git(tmp_path, kopie):
    repo, texts = kopie
    bron = init_repo(tmp_path / "bron")
    for rel, data in texts.items():
        write(bron, rel, data.decode())
    commit = commit_all(bron, "contract 1.2")
    errors, warnings = contract_drift.compare_with_source(
        repo, contract_drift.git_reader(bron, commit), contract_drift.worktree_reader(bron), pins_for(texts)
    )
    assert errors == [] and warnings == []

    # De bron gaat daarna verder: alleen een waarschuwing (overnemen is een stap van de orkestratie).
    write(bron, CONTRACT, texts[CONTRACT].decode() + "nieuwe regel\n")
    errors, warnings = contract_drift.compare_with_source(
        repo, contract_drift.git_reader(bron, commit), contract_drift.worktree_reader(bron), pins_for(texts)
    )
    assert errors == [] and len(warnings) == 1 and "na " in warnings[0] and CONTRACT in warnings[0]

    # De kopie wijkt af van de bron-commit: fout.
    (repo / CONFORMITEIT).write_bytes(b"iets anders\n")
    errors, _ = contract_drift.compare_with_source(repo, contract_drift.git_reader(bron, commit), None, pins_for(texts))
    assert errors == [f"{CONFORMITEIT}: kopie is niet byte-gelijk aan lvos04/ai-server-manager@{contract_drift.BRON_COMMIT[:9]}"]


def test_bestand_ontbreekt_in_de_bron(tmp_path, kopie):
    repo, texts = kopie
    bron = init_repo(tmp_path / "bron")
    write(bron, CONTRACT, texts[CONTRACT].decode())
    commit = commit_all(bron, "alleen het contract")
    errors, _ = contract_drift.compare_with_source(repo, contract_drift.git_reader(bron, commit), None, pins_for(texts))
    assert any(CONFORMITEIT in e and "niet gevonden" in e for e in errors)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def test_http_reader_herhaalt_en_meldt_onbereikbaar(monkeypatch):
    calls: list[str] = []
    waits: list[float] = []

    def urlopen(url, timeout):
        calls.append(url)
        raise urllib.error.URLError("verbinding geweigerd")

    monkeypatch.setattr(contract_drift.urllib.request, "urlopen", urlopen)
    read = contract_drift.http_reader("abc123", attempts=4, sleep=waits.append)
    with pytest.raises(OSError, match="niet bereikbaar na 4 pogingen"):
        read(CONTRACT)
    assert len(calls) == 4 and waits == [2.0, 4.0, 8.0]
    assert calls[0] == f"https://raw.githubusercontent.com/lvos04/ai-server-manager/abc123/{CONTRACT}"


def test_http_reader_404_is_niet_gevonden_en_200_geeft_inhoud(monkeypatch):
    def urlopen(url, timeout):
        if url.endswith(CONFORMITEIT):
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        return FakeResponse(b"inhoud")

    monkeypatch.setattr(contract_drift.urllib.request, "urlopen", urlopen)
    read = contract_drift.http_reader("abc123", sleep=lambda _s: None)
    assert read(CONTRACT) == b"inhoud"
    assert read(CONFORMITEIT) is None


def test_main_online_onbereikbaar_is_omgevingsfout_nooit_in_orde(monkeypatch, capsys):
    def urlopen(url, timeout):
        raise urllib.error.HTTPError(url, 503, "Service Unavailable", None, None)

    monkeypatch.setattr(contract_drift.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(contract_drift.time, "sleep", lambda _s: None)
    assert contract_drift.main(["--repo", str(REPO_ROOT), "--online"]) == 3
    out = capsys.readouterr()
    assert "HTTP 503" in out.err and "in orde" not in out.out


def test_main_bron_map_zonder_git_is_gebruiksfout(tmp_path, capsys):
    assert contract_drift.main(["--repo", str(REPO_ROOT), "--bron-map", str(tmp_path)]) == 3
    assert "geen git-checkout" in capsys.readouterr().err


def test_main_offline_en_drift_exitcodes(tmp_path, kopie, monkeypatch, capsys):
    repo, texts = kopie
    monkeypatch.setattr(contract_drift, "KOPIEEN", pins_for(texts))
    assert contract_drift.main(["--repo", str(repo)]) == 0
    assert "Contractkopieën in orde (offline, sha256-pin)" in capsys.readouterr().out
    (repo / CONTRACT).write_bytes(texts[CONTRACT] + b"x")
    assert contract_drift.main(["--repo", str(repo)]) == 1
    assert "CONTRACTKOPIE NIET IN ORDE (1 problemen)" in capsys.readouterr().err


def test_main_waarschuwing_als_github_annotatie(tmp_path, kopie, monkeypatch, capsys):
    repo, texts = kopie
    monkeypatch.setattr(contract_drift, "KOPIEEN", pins_for(texts))
    nieuw = {CONTRACT: texts[CONTRACT] + b"later\n", CONFORMITEIT: texts[CONFORMITEIT]}

    def http_reader(ref, attempts=4, sleep=None):
        bron = texts if ref == contract_drift.BRON_COMMIT else nieuw
        return lambda rel: bron.get(rel)

    monkeypatch.setattr(contract_drift, "http_reader", http_reader)
    assert contract_drift.main(["--repo", str(repo), "--online", "--github"]) == 0
    captured = capsys.readouterr()
    assert captured.err.startswith("::warning::") and CONTRACT in captured.err
    assert "online tegen GitHub" in captured.out
