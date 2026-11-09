#!/usr/bin/env python3
"""Controleert het register van upstream-gedrag, webdeel (docs/platform-v2/UPSTREAM_GEDRAG.md; B03-019 a, §10.11).

Per regel `UG-WEB-<n>` moet het anker (Python-regex, `re.MULTILINE`) gevonden worden in het genoemde upstream-bestand
van de huidige boom. Zo blokkeert een upstream-sync die een haakpunt of gedrag laat verdwijnen of verhuizen, nog vóór
er een haak bestaat (EX48, JLT-67). Verder:

  * ID's uniek en doorlopend genummerd (UG-WEB-1, -2, …), elk veld gevuld;
  * het bestand ligt buiten de fork-eigen paden (het gaat om upstream-gedrag) en bestaat;
  * elke verwijzing `UG-WEB-<n>` in docs/, README.jelly-leon.md of tools/jelly-leon-web/ bestaat in het register
    ("een verwijzing UG-… zonder test laat de build falen", B03-019).

Exitcodes: 0 = in orde, 1 = overtreding, 3 = gebruiks-/omgevingsfout.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jlw_common import DEFAULT_REPO_ROOT, ToolError, is_fork_path, load_fork_paths  # noqa: E402

REGISTER_REL = "docs/platform-v2/UPSTREAM_GEDRAG.md"
ID_RE = re.compile(r"^UG-WEB-(\d+)$")
REF_RE = re.compile(r"\bUG-WEB-(\d+)\b")
CELL_CODE_RE = re.compile(r"^`([^`]+)`$")
SCAN_ROOTS = ("docs", "README.jelly-leon.md", "tools/jelly-leon-web", ".github/workflows/jelly-leon-web-ci.yml",
              ".github/workflows/upstream-sync.yml")
SCAN_SUFFIXES = {".md", ".py", ".yml", ".yaml", ".json", ".txt"}


@dataclass(frozen=True)
class Entry:
    entry_id: str
    number: int
    behaviour: str
    path: str
    anchor: str
    used_by: str
    test: str


def _split_row(line: str) -> list[str]:
    cells = line.strip()
    if not (cells.startswith("|") and cells.endswith("|")):
        return []
    return [cell.strip() for cell in cells[1:-1].split("|")]


def parse_register(text: str) -> tuple[list[Entry], list[str]]:
    entries: list[Entry] = []
    errors: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        cells = _split_row(line)
        if not cells or not ID_RE.match(cells[0]):
            continue
        where = f"{REGISTER_REL}:{number}"
        if len(cells) != 6:
            errors.append(f"{where}: {cells[0]} heeft {len(cells)} kolommen, verwacht 6 (een '|' in de regex? gebruik \\x7c)")
            continue
        entry_id, behaviour, path_cell, anchor_cell, used_by, test = cells
        path_match, anchor_match = CELL_CODE_RE.match(path_cell), CELL_CODE_RE.match(anchor_cell)
        if not path_match or not anchor_match:
            errors.append(f"{where}: {entry_id}: bestand en anker staan elk tussen backticks")
            continue
        if not all((behaviour, used_by, test)):
            errors.append(f"{where}: {entry_id}: gedrag, 'gebruikt door' en test zijn verplicht")
            continue
        entries.append(Entry(entry_id, int(ID_RE.match(entry_id).group(1)), behaviour, path_match.group(1),
                             anchor_match.group(1), used_by, test))
    return entries, errors


def check_entries(repo: Path, entries: list[Entry], fork_paths: list[str]) -> list[str]:
    errors: list[str] = []
    numbers = [entry.number for entry in entries]
    if not entries:
        errors.append(f"{REGISTER_REL}: geen enkele UG-WEB-regel (register leeg of onleesbaar)")
    duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
    if duplicates:
        errors.append(f"{REGISTER_REL}: dubbele ID's: {', '.join(f'UG-WEB-{n}' for n in duplicates)}")
    expected = list(range(1, len(set(numbers)) + 1))
    if sorted(set(numbers)) != expected:
        errors.append(f"{REGISTER_REL}: nummering niet doorlopend vanaf 1 ({sorted(set(numbers))})")
    for entry in entries:
        if is_fork_path(entry.path, fork_paths):
            errors.append(f"{entry.entry_id}: {entry.path} is een fork-eigen pad; het register gaat over upstream-gedrag")
            continue
        try:
            pattern = re.compile(entry.anchor, re.MULTILINE)
        except re.error as exc:
            errors.append(f"{entry.entry_id}: anker is geen geldige regex: {exc}")
            continue
        target = repo / entry.path
        if not target.is_file():
            errors.append(f"{entry.entry_id}: {entry.path} bestaat niet (meer) — haakpunt verhuisd? Gedrag opnieuw beoordelen")
            continue
        if not pattern.search(target.read_text(encoding="utf-8", errors="replace")):
            errors.append(
                f"{entry.entry_id}: anker niet gevonden in {entry.path} ({entry.behaviour}) — upstream-gedrag gewijzigd; "
                "eerst opnieuw beoordelen, dan pas de haak/het anker aanpassen"
            )
    return errors


def iter_scan_files(repo: Path):
    for root in SCAN_ROOTS:
        path = repo / root
        if path.is_file():
            yield path
        elif path.is_dir():
            for item in sorted(path.rglob("*")):
                if item.is_file() and item.suffix in SCAN_SUFFIXES and "__pycache__" not in item.parts:
                    yield item


def check_references(repo: Path, entries: list[Entry]) -> list[str]:
    known = {entry.number for entry in entries}
    errors: list[str] = []
    for path in iter_scan_files(repo):
        rel = path.relative_to(repo).as_posix()
        if rel == REGISTER_REL or rel.startswith("tools/jelly-leon-web/tests/"):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            for match in REF_RE.finditer(line):
                if int(match.group(1)) not in known:
                    errors.append(f"{rel}:{number}: verwijst naar UG-WEB-{match.group(1)}, dat niet in {REGISTER_REL} staat")
    return errors


def check(repo: Path) -> tuple[list[Entry], list[str]]:
    register = repo / REGISTER_REL
    if not register.is_file():
        raise ToolError(f"{REGISTER_REL} ontbreekt (B03-019: het register bestaat, leeg mag niet stil)", exit_code=1)
    entries, errors = parse_register(register.read_text(encoding="utf-8"))
    errors += check_entries(repo, entries, load_fork_paths(repo))
    errors += check_references(repo, entries)
    return entries, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Controleer het register van upstream-gedrag (webdeel).")
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--overzicht", action="store_true", help="druk per regel ID, bestand en uitkomst af")
    args = parser.parse_args(argv)
    try:
        entries, errors = check(args.repo.resolve())
    except ToolError as exc:
        print(f"FOUT: {exc}", file=sys.stderr)
        return exc.exit_code
    if args.overzicht:
        failed = {line.split(":", 1)[0] for line in errors}
        for entry in entries:
            print(f"{'FOUT' if entry.entry_id in failed else 'OK  '} {entry.entry_id:<10} {entry.path}")
    if errors:
        print(f"UPSTREAM-GEDRAG NIET IN ORDE ({len(errors)} problemen):", file=sys.stderr)
        for line in errors:
            print(f"  - {line}", file=sys.stderr)
        return 1
    print(f"Upstream-gedrag (webdeel) in orde: {len(entries)} ankers gevonden, alle UG-WEB-verwijzingen bekend.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
