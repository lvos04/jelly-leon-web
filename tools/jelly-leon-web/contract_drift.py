#!/usr/bin/env python3
"""Drifttest van de gekopieerde platformcontracten (contract 1.3, kop en C1.3-ALG-01 / C1.3-JLW-01).

`docs/platform-v2/PLATFORM_CONTRACTEN.md` (`contracts 1.3`) en `docs/platform-v2/CONTRACT_1.3_CONFORMITEIT.md` zijn
byte-gelijke kopieën uit `lvos04/ai-server-manager` (bron van waarheid) op een vastgezette bron-commit; de 1.2-lijst
`docs/platform-v2/CONTRACT_1.2_CONFORMITEIT.md` blijft als historie staan (C1.3-ALG-01) en is op dezelfde bron-commit
vastgezet, zodat ook die kopie niet stil kan afwijken. Deze repo wijzigt ze nooit zelf; een nieuwe contractstand
overnemen is een stap van de orkestratie (byte-gelijk kopiëren + bron-commit en sha256 hieronder bijwerken). Zelfde
opzet als `tools/jelly-leon/contract_drift.py` in de serverfork `lvos04/jelly-leon`.

Controles:
  1. altijd (offline): elke kopie bestaat en heeft precies de vastgezette sha256 (niemand heeft hier iets aangepast);
     de contractkopie draagt de versiekop `contracts 1.3`;
  2. `--bron-map <checkout van ai-server-manager>`: de kopie is byte-gelijk aan `git show <bron-commit>:<pad>`;
     wijkt de werkboom van die checkout daarvan af, dan alleen een waarschuwing "bron gewijzigd" (kopie bijwerken);
  3. `--online`: idem via raw.githubusercontent.com op de volledige bron-commit (publieke repo, geen token) en —
     alleen als waarschuwing — op de bronbranch (`--bronbranch`). Netwerkfouten: 4 pogingen (wacht 2/4/8 s).

Alleen standaardbibliotheek. Exitcodes: 0 = gelijk (eventueel met waarschuwing), 1 = drift/afwijking,
3 = gebruiks- of omgevingsfout (bv. bron niet bereikbaar). Een omgevingsfout wordt nooit als "in orde" gemeld.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jlw_common import DEFAULT_REPO_ROOT  # noqa: E402

BRON_REPO = "lvos04/ai-server-manager"
#: Commit van ai-server-manager waaruit de kopieën komen: contracts 1.3 met de review-correcties RV1–RV13 (ADR-0028
#: daar); de laatste commit die een van de drie bestanden wijzigde ("Contract 1.3: MediaGuard-overstap … (RV13)").
BRON_COMMIT = "02b119cb84be9a307a88532f6692ea8a4bcb12f1"
BRON_BRANCH = "ccr-c133d7a0-kuz1cv"
#: Pad (gelijk in bron en kopie) → sha256 van de bron op BRON_COMMIT.
KOPIEEN: dict[str, str] = {
    "docs/platform-v2/PLATFORM_CONTRACTEN.md": "15b30cf17f91b606451ef9c41f02327076ef76ce655ee94e40e3538106962310",
    "docs/platform-v2/CONTRACT_1.3_CONFORMITEIT.md": "f0a2352ddb27088ae668013501c62a1eaaf879efe742a2d4422ffe8d33b43466",
    # Historie (C1.3-ALG-01: "mag als historie blijven staan"); byte-gelijk aan dezelfde bron-commit.
    "docs/platform-v2/CONTRACT_1.2_CONFORMITEIT.md": "634941340afd2d9a55846076ab468ea4aacddb32dd8be6a7b92dd113661d39a4",
}
CONTRACT_REL = "docs/platform-v2/PLATFORM_CONTRACTEN.md"
#: Conformiteitslijst van de versie die deze repo volgt (verplicht naast het contract, C1.3-ALG-01).
CONFORMITEIT_REL = "docs/platform-v2/CONTRACT_1.3_CONFORMITEIT.md"
#: Kop die in de contractkopie moet staan (de versie die deze repo volgt).
VERSIEKOP = b"Versie: `contracts 1.3`"
#: Kop van de conformiteitslijst die bij die versie hoort.
CONFORMITEITSKOP = b"# Conformiteit met contract 1.3"
RAW_URL = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"

Reader = Callable[[str], bytes | None]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_pins(repo: Path, pins: dict[str, str] | None = None) -> list[str]:
    """Offline: elke kopie bestaat, heeft precies de vastgezette sha256 en (contract) de juiste versiekop."""
    errors: list[str] = []
    for rel, expected in (pins or KOPIEEN).items():
        path = repo / rel
        if not path.is_file():
            errors.append(f"{rel} ontbreekt (byte-gelijke kopie uit {BRON_REPO} is verplicht, C1.3-ALG-01)")
            continue
        data = path.read_bytes()
        found = sha256(data)
        if found != expected:
            errors.append(
                f"{rel}: sha256 {found[:16]}… ≠ vastgezet {expected[:16]}… — de kopie is gewijzigd; niet hier "
                f"aanpassen maar byte-gelijk opnieuw kopiëren uit {BRON_REPO}@{BRON_COMMIT[:9]} (of, bij een nieuwe "
                "contractversie, bron-commit en sha256 in contract_drift.py bijwerken)"
            )
        if rel == CONTRACT_REL and VERSIEKOP not in data:
            errors.append(f"{rel}: versiekop {VERSIEKOP.decode()} ontbreekt")
        if rel == CONFORMITEIT_REL and not data.startswith(CONFORMITEITSKOP):
            errors.append(f"{rel}: begint niet met de kop '{CONFORMITEITSKOP.decode()}'")
    for rel in (CONTRACT_REL, CONFORMITEIT_REL):
        if rel not in (pins or KOPIEEN):
            errors.append(f"{rel} staat niet in de pinlijst van de drifttest (contract 1.3 C1.3-ALG-01)")
    return errors


def compare_with_source(
    repo: Path, at_commit: Reader, current: Reader | None, pins: dict[str, str] | None = None
) -> tuple[list[str], list[str]]:
    """Kopie ↔ bron op de bron-commit (fout bij verschil) en ↔ huidige bron (alleen een waarschuwing)."""
    errors: list[str] = []
    warnings: list[str] = []
    for rel in pins or KOPIEEN:
        path = repo / rel
        copy = path.read_bytes() if path.is_file() else None
        source = at_commit(rel)
        if source is None:
            errors.append(f"{rel}: niet gevonden in {BRON_REPO} op {BRON_COMMIT[:9]}")
        elif copy != source:
            errors.append(f"{rel}: kopie is niet byte-gelijk aan {BRON_REPO}@{BRON_COMMIT[:9]}")
        if current is not None and source is not None:
            latest = current(rel)
            if latest is None:
                warnings.append(f"{rel}: staat niet (meer) in de huidige bron — contractstand nagaan")
            elif latest != source:
                warnings.append(
                    f"{rel}: de bron is na {BRON_COMMIT[:9]} gewijzigd — nieuwe contractstand overnemen "
                    "(orkestratie: byte-gelijk kopiëren, bron-commit en sha256 in contract_drift.py bijwerken)"
                )
    return errors, warnings


def git_reader(source_repo: Path, ref: str) -> Reader:
    def read(rel: str) -> bytes | None:
        proc = subprocess.run(["git", "-C", str(source_repo), "show", f"{ref}:{rel}"], capture_output=True, check=False)
        return proc.stdout if proc.returncode == 0 else None

    return read


def worktree_reader(source_repo: Path) -> Reader:
    def read(rel: str) -> bytes | None:
        path = source_repo / rel
        return path.read_bytes() if path.is_file() else None

    return read


def http_reader(ref: str, attempts: int = 4, sleep: Callable[[float], None] | None = None) -> Reader:
    """Leest een bestand van de publieke bron; 404 → None; andere fouten na `attempts` pogingen → OSError."""

    def read(rel: str) -> bytes | None:
        url = RAW_URL.format(repo=BRON_REPO, ref=ref, path=rel)
        delay = 2.0
        last = ""
        for attempt in range(1, attempts + 1):
            try:
                with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 (vaste https-URL)
                    return resp.read()
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return None
                last = f"HTTP {exc.code}"
            except (urllib.error.URLError, TimeoutError) as exc:
                last = str(exc)
            if attempt < attempts:
                (sleep or time.sleep)(delay)
                delay *= 2
        raise OSError(f"{url} niet bereikbaar na {attempts} pogingen ({last})")

    return read


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drifttest van de platformcontract-kopieën (contract 1.3).")
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO_ROOT)
    bron = parser.add_mutually_exclusive_group()
    bron.add_argument("--bron-map", type=Path, help="lokale checkout van ai-server-manager (vergelijk met git show)")
    bron.add_argument("--online", action="store_true", help="vergelijk met de publieke bron op GitHub")
    parser.add_argument("--bronbranch", default=BRON_BRANCH, help="branch van de bron voor de driftwaarschuwing")
    parser.add_argument("--github", action="store_true", help="waarschuwingen als ::warning:: voor GitHub Actions")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()

    errors = check_pins(repo)
    warnings: list[str] = []
    try:
        if args.bron_map:
            if not (args.bron_map / ".git").exists():
                print(f"FOUT: {args.bron_map} is geen git-checkout van {BRON_REPO}", file=sys.stderr)
                return 3
            more, warnings = compare_with_source(
                repo, git_reader(args.bron_map, BRON_COMMIT), worktree_reader(args.bron_map)
            )
            errors += more
        elif args.online:
            more, warnings = compare_with_source(repo, http_reader(BRON_COMMIT), http_reader(args.bronbranch))
            errors += more
    except OSError as exc:
        print(f"FOUT: {exc}", file=sys.stderr)
        return 3

    for line in warnings:
        print(f"::warning::{line}" if args.github else f"WAARSCHUWING: {line}", file=sys.stderr)
    if errors:
        print(f"CONTRACTKOPIE NIET IN ORDE ({len(errors)} problemen):", file=sys.stderr)
        for line in errors:
            print(f"  - {line}", file=sys.stderr)
        return 1
    mode = "online tegen GitHub" if args.online else ("tegen de lokale bron" if args.bron_map else "offline, sha256-pin")
    print(f"Contractkopieën in orde ({mode}): {len(KOPIEEN)} bestanden byte-gelijk aan {BRON_REPO}@{BRON_COMMIT[:9]}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
