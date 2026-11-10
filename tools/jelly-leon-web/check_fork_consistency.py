#!/usr/bin/env python3
"""Bewaakt de versie- en identiteitsregels van de webclient-fork (ADR-0003, ADR-0005) en EVIDENCE.json (§11).

Controles:
  * baseline.json: forkversie = <upstream_version>-jl.<N>, tag en versie kloppen, upstream-commit zit in de historie;
  * technische identiteit: package.json/package-lock.json heten "jellyfin-web" met de upstream-versie
    (stock clients, plugins en de server zien de webclient als Jellyfin Web; alleen de zichtbare naam mag later
    "Jelly Leon" worden);
  * lokale tag upstream-<tag> (als die bestaat) wijst naar dezelfde upstream-commit;
  * zichtbare naam (JLW-0002, ADR-0003/ADR-0011): in de merkbestanden is de enige afwijking van upstream dat
    "Jellyfin" "Jelly Leon" werd, regel voor regel; elders mag die vervanging niet stilletjes gebeuren
    (de merkwijziging blijft de enige, de technische identiteit blijft "Jellyfin");
  * toolchain (ADR-0011): baseline.json → toolchain (Node/npm exact, Node-image en serverimage op @sha256) is de enige
    bron; de eigen workflows (node-version, build-container, JLW_SERVER_IMAGE) en de smoketest gebruiken exact die
    waarden, en Node/npm voldoen aan `engines` in package.json (12.x: node >= 24, npm >= 11);
  * docs/platform-v2/EVIDENCE.json volgt contract §11 (1.3; C1.3-ALG-02 en C1.3-JLW-02): precies de velden uit §11,
    geldige statussen, nooit "Gereed"/"Geslaagd" in deze bouwomgeving, `validatie` nooit leeg en alleen waarden uit
    de vaste lijst (meerdere gescheiden door "; ", toelichting hoort in `opmerking`), repo = jelly-leon-web, en elke
    commit die in `bewijs` genoemd wordt bestaat echt in deze repo (commits van andere repos schrijf je als
    `<repo>@<sha>`). Fail-closed: een ontbrekend of leeg EVIDENCE.json is een overtreding (§11: elke repo houdt het
    bij), nooit "in orde". Elke `NIET GEVALIDEERD (…)` die in `blokkade` staat, is een waarde uit de vaste lijst en
    staat ook in `validatie` (geen stille blokkade); `bijgewerkt` is een echte kalenderdatum.
    Nieuw in 1.3: `Niet getest` alleen bij status `Niet gestart` (en nooit naast een testuitkomst; omgekeerd draagt
    een rij `Niet gestart` geen testuitkomst); `Intel-iGPU-getest (ontwikkelmachine)` alleen samen met
    `NIET GEVALIDEERD (hardware)` (de GPU's van de NAS blijven niet gevalideerd); naast Excel-ID's mogen contractpunten
    (`C1.3-<code>` uit CONTRACT_1.3_CONFORMITEIT.md, `C1.2-<code>` uit de 1.2-lijst; alleen punten voor alle repos of
    voor deze repo, en alleen als ze echt in de gekopieerde lijst staan) en reviews
    (`REVIEW-jelly-leon-web-<onderwerp>`) een eigen regel hebben, met de statussen van het blad Werkpakketten.

Exitcodes: 0 = in orde, 1 = overtreding, 3 = gebruiks-/omgevingsfout.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jlw_common import (  # noqa: E402
    BASELINE_REL,
    DEFAULT_REPO_ROOT,
    EVIDENCE_REL,
    FORK_VERSION_RE,
    ToolError,
    Version,
    load_baseline,
    load_json,
    parse_stable_tag,
    read_package_json,
    run_git,
)

REPO_NAME = "jelly-leon-web"
EVIDENCE_FIELDS = ("id", "status", "validatie", "bewijs", "blokkade", "opmerking", "repo", "bijgewerkt")
# Excel-statuslijsten (contract §11). "Gereed" en "Geslaagd" vragen echte acceptatie op de NAS en worden in deze
# bouwomgeving nooit gezet; "Ingevuld"/"Getest" horen bij besluiten (D01–D18) die de gebruiker invult.
STATUS_WERKPAKKET = {"Niet gestart", "Bezig", "Gereed", "Geblokkeerd", "N.v.t."}
STATUS_TEST = {"Niet gestart", "Bezig", "Geslaagd", "Mislukt", "Geblokkeerd", "N.v.t."}
STATUS_BESLUIT = {"Open", "Ingevuld", "Getest", "Geblokkeerd", "N.v.t."}
FORBIDDEN_STATUSES = {"Gereed", "Geslaagd", "Getest", "Ingevuld"}
# §11 (1.3): vaste lijst; meerdere waarden gescheiden door "; ". De testmatrix (EX.., JLT-..) zet het
# simulatorresultaat in `validatie` ("Sim-geslaagd"/"Sim-mislukt").
INTEL_IGPU = "Intel-iGPU-getest (ontwikkelmachine)"
NIET_GETEST = "Niet getest"
NIET_GEVALIDEERD_HARDWARE = "NIET GEVALIDEERD (hardware)"
VALIDATIE_WAARDEN = (
    "Sim-getest",
    "Unit-getest",
    INTEL_IGPU,
    "NIET GEVALIDEERD (echte NAS)",
    NIET_GEVALIDEERD_HARDWARE,
    "NIET GEVALIDEERD (account)",
    "NIET GEVALIDEERD (Mac/Xcode)",
    NIET_GETEST,
)
VALIDATIE_TESTMATRIX = ("Sim-geslaagd", "Sim-mislukt")
#: Waarden die zeggen dat er iets getest is; die passen niet bij `Niet getest` of bij status `Niet gestart`.
TESTUITKOMSTEN = ("Sim-getest", "Unit-getest", INTEL_IGPU) + VALIDATIE_TESTMATRIX
STATUS_NIET_GESTART = "Niet gestart"
VALIDATIE_SEP = "; "
# Hexadecimale commit-verwijzing in `bewijs`; niet na ":" "-" "@" "/" (digests als sha256:…, sha512-…, <repo>@<sha>,
# URL-paden) en niet alleen cijfers (run-ID's van GitHub Actions).
COMMIT_REF_RE = re.compile(r"(?<![0-9A-Za-z:@/\-])([0-9a-f]{7,40})(?![0-9A-Za-z])")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# "NIET GEVALIDEERD (…)" in vrije tekst (blokkade): moet ook als lijstwaarde in `validatie` staan.
NIET_GEVALIDEERD_RE = re.compile(r"NIET GEVALIDEERD \([^)]*\)")
ID_RE = re.compile(r"^(B\d{2}-\d{3}|I\d{2}-\d{2}-\d{2}|A\d{2}(-\d+)?|APP-\d{2}|EX\d{2}|JLT-\d{2}|D\d{2})$")
# Contractpunten en reviews (§11, 1.3; K9): eigen regels naast de Excel-ID's, statussen van het blad Werkpakketten.
CONTRACTPUNT_13_RE = re.compile(r"^C1\.3-([A-Z]+)-(\d{2})$")
CONTRACTPUNT_12_RE = re.compile(r"^C1\.2-([A-Z]+\d+)$")
REVIEW_RE = re.compile(rf"^REVIEW-{re.escape(REPO_NAME)}-[a-z0-9][a-z0-9.-]*$")
CONFORMITEIT_13_REL = "docs/platform-v2/CONTRACT_1.3_CONFORMITEIT.md"
CONFORMITEIT_12_REL = "docs/platform-v2/CONTRACT_1.2_CONFORMITEIT.md"
# Hoofdstukken van de conformiteitslijsten die over deze repo gaan: "voor alle repos" en "jelly-leon-web".
EIGEN_HOOFDSTUK_RE = re.compile(r"^## (0\.|10\. jelly-leon-web\b)")
# Testrijen: EX01–EX50 (testmatrix) en sinds B03 2.0 JLT-01…74 (update_excel.py routeert JLT-… naar de Testmatrix).
TEST_ID_RE = re.compile(r"^(EX\d{2}|JLT-\d{2})$")

# Zichtbare naam (JLW-0002): staat in baseline.json onder "zichtbare_naam" (naam, upstream_naam, bestanden), zodat
# een upstream-sync de instelling meeneemt. Alleen die bestanden, alleen die vervanging (ADR-0003, ADR-0011).
VISIBLE_NAME_KEY = "zichtbare_naam"

TOOLCHAIN_KEY = "toolchain"
EXACT_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
ENGINE_RE = re.compile(r"^>=\s*(\d+(?:\.\d+){0,2})$")
OWN_WORKFLOWS = (".github/workflows/jelly-leon-web-ci.yml", ".github/workflows/upstream-sync.yml")
CI_WORKFLOW = ".github/workflows/jelly-leon-web-ci.yml"
SMOKE_TEST = "tools/jelly-leon-web/e2e/web_smoke.py"
NODE_VERSION_RE = re.compile(r"^\s*node-version:\s*['\"]?([^'\"\s#]+)", re.MULTILINE)
SERVER_ENV_RE = re.compile(r"^\s*JLW_SERVER_IMAGE:\s*(\S+)", re.MULTILINE)
CONTAINER_IMAGE_RE = re.compile(r"^\s*image:\s*(\S+)", re.MULTILINE)
SMOKE_DEFAULT_RE = re.compile(r'DEFAULT_IMAGE = \(\s*"([^"]+)"\s*\)')


def check_baseline(repo: Path, baseline: dict) -> list[str]:
    errors: list[str] = []
    tag_version = parse_stable_tag(baseline["upstream_tag"])
    if tag_version is None:
        errors.append(f"{BASELINE_REL}: upstream_tag '{baseline['upstream_tag']}' is geen stabiele tag")
    elif str(tag_version) != str(Version.parse(baseline["upstream_version"])):
        errors.append(f"{BASELINE_REL}: upstream_tag {baseline['upstream_tag']} ≠ upstream_version {baseline['upstream_version']}")
    match = FORK_VERSION_RE.match(baseline["fork_version"])
    if not match:
        errors.append(f"{BASELINE_REL}: fork_version '{baseline['fork_version']}' volgt niet <upstream>-jl.<N>")
    elif match.group(1) != baseline["upstream_version"]:
        errors.append(
            f"{BASELINE_REL}: fork_version {baseline['fork_version']} hoort bij {match.group(1)}, "
            f"maar de basis is {baseline['upstream_version']}"
        )
    commit = baseline["upstream_commit"]
    if run_git(repo, "cat-file", "-e", f"{commit}^{{commit}}", check=False).returncode != 0:
        errors.append(f"upstream-commit {commit} ontbreekt in de historie (checkout met fetch-depth: 0?)")
    elif run_git(repo, "merge-base", "--is-ancestor", commit, "HEAD", check=False).returncode != 0:
        errors.append(f"upstream-commit {commit} is geen voorouder van HEAD: de fork bevat de basis niet")
    local_tag = baseline.get("local_upstream_tag")
    if local_tag:
        proc = run_git(repo, "rev-parse", "--verify", "--quiet", f"refs/tags/{local_tag}^{{commit}}", check=False)
        if proc.returncode == 0 and proc.stdout.strip() != commit:
            errors.append(f"lokale tag {local_tag} wijst naar {proc.stdout.strip()[:12]}, baseline naar {commit[:12]}")
    return errors


def check_identity(repo: Path, baseline: dict) -> list[str]:
    errors: list[str] = []
    expected_name = baseline.get("package_name", "jellyfin-web")
    expected_version = baseline["upstream_version"]
    package = read_package_json(repo)
    if package.get("name") != expected_name:
        errors.append(f"package.json: name '{package.get('name')}' ≠ '{expected_name}' (technische identiteit, ADR-0003)")
    if package.get("version") != expected_version:
        errors.append(
            f"package.json: version '{package.get('version')}' ≠ upstream {expected_version} "
            "(de webclient meldt de upstream-versie; de forkversie staat in baseline.json, ADR-0005)"
        )
    lock_path = repo / "package-lock.json"
    if lock_path.is_file():
        lock = load_json(repo, "package-lock.json")
        if isinstance(lock, dict):
            root = (lock.get("packages") or {}).get("", {})
            for label, value in (("name", lock.get("name")), ("version", lock.get("version")),
                                 ("packages[''].version", root.get("version"))):
                wanted = expected_name if label == "name" else expected_version
                if value is not None and value != wanted:
                    errors.append(f"package-lock.json: {label} '{value}' ≠ '{wanted}'")
    return errors


def check_visible_name(repo: Path, baseline: dict) -> list[str]:
    """JLW-0002: per merkbestand is elke afwijkende regel exact de upstream-regel met "Jellyfin" → "Jelly Leon"."""
    config = baseline.get(VISIBLE_NAME_KEY)
    if config is None:
        return []  # nog geen merkwijziging vastgelegd (P0); in deze repo bewaakt test_real_repo… dat hij er is
    if not isinstance(config, dict) or not all(
        isinstance(config.get(key), str) and config.get(key) for key in ("naam", "upstream_naam")
    ) or not isinstance(config.get("bestanden"), list) or not config["bestanden"]:
        return [f"{BASELINE_REL}: '{VISIBLE_NAME_KEY}' vraagt naam, upstream_naam en een niet-lege lijst bestanden"]
    VISIBLE_NAME, UPSTREAM_VISIBLE_NAME = config["naam"], config["upstream_naam"]  # noqa: N806
    errors: list[str] = []
    base = baseline["upstream_commit"]
    for rel in config["bestanden"]:
        proc = run_git(repo, "show", f"{base}:{rel}", check=False)
        path = repo / rel
        if proc.returncode != 0 or not path.is_file():
            errors.append(f"{rel}: merkbestand ontbreekt upstream ({base[:12]}) of in de fork (JLW-0002 herbeoordelen)")
            continue
        upstream_lines = proc.stdout.splitlines()
        fork_lines = path.read_text(encoding="utf-8").splitlines()
        if len(upstream_lines) != len(fork_lines):
            errors.append(f"{rel}: {len(fork_lines)} regels, upstream {len(upstream_lines)}; de merkpatch wijzigt alleen "
                          "bestaande regels (zichtbare naam), niets toevoegen of weghalen")
            continue
        changed = 0
        for number, (old, new) in enumerate(zip(upstream_lines, fork_lines), start=1):
            if old == new:
                continue
            changed += 1
            if UPSTREAM_VISIBLE_NAME not in old or new != old.replace(UPSTREAM_VISIBLE_NAME, VISIBLE_NAME):
                errors.append(f"{rel}:{number}: afwijking is geen pure naamwijziging "
                              f"'{UPSTREAM_VISIBLE_NAME}' → '{VISIBLE_NAME}' (enige merkwijziging, ADR-0003)")
        if changed == 0:
            errors.append(f"{rel}: zichtbare naam '{VISIBLE_NAME}' ontbreekt (JLW-0002 niet toegepast)")
    return errors


def _version_tuple(text: str) -> tuple[int, int, int]:
    parts = [int(p) for p in text.split(".")]
    return tuple((parts + [0, 0, 0])[:3])  # type: ignore[return-value]


def check_toolchain(repo: Path, baseline: dict) -> list[str]:
    """Eén bron voor Node/npm en de images (ADR-0011): gelijk in workflows en smoketest, voldoet aan engines."""
    toolchain = baseline.get(TOOLCHAIN_KEY)
    if toolchain is None:
        return []  # nog geen toolchain vastgelegd; in deze repo eist test_real_repo… dat hij er is
    if not isinstance(toolchain, dict):
        return [f"{BASELINE_REL}: '{TOOLCHAIN_KEY}' moet een object zijn"]
    errors: list[str] = []
    node, npm = str(toolchain.get("node", "")), str(toolchain.get("npm", ""))
    node_image, server_image = str(toolchain.get("node_image", "")), str(toolchain.get("server_image", ""))
    for label, value in (("node", node), ("npm", npm)):
        if not EXACT_VERSION_RE.match(value):
            errors.append(f"{BASELINE_REL}: toolchain.{label} '{value}' is geen exacte versie x.y.z")
    for label, value in (("node_image", node_image), ("server_image", server_image)):
        if "@sha256:" not in value or ":latest" in value:
            errors.append(f"{BASELINE_REL}: toolchain.{label} '{value}' niet op @sha256-digest vastgezet (of latest)")
    if node and f":{node}-" not in node_image:
        errors.append(f"{BASELINE_REL}: toolchain.node_image hoort bij Node {node} (tag '{node}-…'), niet '{node_image}'")
    if errors:
        return errors

    engines = read_package_json(repo).get("engines") or {}
    for label, have in (("node", node), ("npm", npm)):
        wanted = engines.get(label)
        if wanted is None:
            continue
        match = ENGINE_RE.match(str(wanted).strip())
        if not match:
            errors.append(f"package.json: engines.{label} '{wanted}' heeft een onbekende vorm; toolchain handmatig beoordelen")
        elif _version_tuple(have) < _version_tuple(match.group(1)):
            errors.append(
                f"toolchain.{label} {have} voldoet niet aan engines.{label} '{wanted}' (upstream vraagt een nieuwere "
                "toolchain: bewust besluit + images op digest bijwerken, ADR-0011)"
            )

    for rel in OWN_WORKFLOWS:
        path = repo / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for found in NODE_VERSION_RE.findall(text):
            if found != node:
                errors.append(f"{rel}: node-version {found} ≠ toolchain.node {node} ({BASELINE_REL})")
        for found in CONTAINER_IMAGE_RE.findall(text):
            if "node:" in found and found != node_image:
                errors.append(f"{rel}: build-container {found} ≠ toolchain.node_image ({BASELINE_REL})")
    ci = repo / CI_WORKFLOW
    if ci.is_file():
        found = SERVER_ENV_RE.findall(ci.read_text(encoding="utf-8"))
        if found != [server_image]:
            errors.append(f"{CI_WORKFLOW}: JLW_SERVER_IMAGE {found or 'ontbreekt'} ≠ toolchain.server_image ({BASELINE_REL})")
    smoke = repo / SMOKE_TEST
    if smoke.is_file():
        found = SMOKE_DEFAULT_RE.findall(smoke.read_text(encoding="utf-8"))
        if found != [server_image]:
            errors.append(f"{SMOKE_TEST}: DEFAULT_IMAGE {found or 'ontbreekt'} ≠ toolchain.server_image ({BASELINE_REL})")
    return errors


def check_evidence(repo: Path) -> list[str]:
    path = repo / EVIDENCE_REL
    if not path.is_file():
        # Fail-closed: zonder bewijsbestand valt er niets te controleren, dus nooit "in orde" (contract §11).
        return [f"{EVIDENCE_REL} ontbreekt (contract §11: elke repo houdt EVIDENCE.json bij)"]
    data = load_json(repo, EVIDENCE_REL)
    if not isinstance(data, list):
        return [f"{EVIDENCE_REL}: verwacht een JSON-lijst (contract §11)"]
    if not data:
        return [f"{EVIDENCE_REL}: lege lijst — geen enkel bewijs vastgelegd (contract §11)"]
    errors: list[str] = []
    seen: set[str] = set()
    punten: dict[str, set[str] | None] = {}  # cache van de gekopieerde conformiteitslijsten
    for index, entry in enumerate(data):
        where = f"{EVIDENCE_REL}[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{where}: geen object")
            continue
        for key in EVIDENCE_FIELDS:
            if key not in entry or not isinstance(entry[key], str):
                errors.append(f"{where}: veld '{key}' ontbreekt of is geen tekst")
        extra = sorted(set(entry) - set(EVIDENCE_FIELDS))
        if extra:
            errors.append(f"{where}: velden {', '.join(extra)} horen niet bij §11")
        entry_id = str(entry.get("id", ""))
        where = f"{EVIDENCE_REL}[{entry_id or index}]"
        if is_contract_or_review_id(entry_id):
            errors.extend(check_contract_point(repo, where, entry_id, punten))
        elif not ID_RE.match(entry_id):
            errors.append(
                f"{where}: id '{entry_id}' is geen Excel-ID (B03-001, I24-24-01, EX48, JLT-60, D15, …), geen "
                f"contractpunt (C1.3-JLW-01, C1.2-JW1) en geen review (REVIEW-{REPO_NAME}-<onderwerp>)"
            )
        if entry_id in seen:
            errors.append(f"{where}: dubbel id")
        seen.add(entry_id)
        status = entry.get("status", "")
        allowed = STATUS_TEST if TEST_ID_RE.match(entry_id) else (
            STATUS_BESLUIT if entry_id.startswith("D") else STATUS_WERKPAKKET
        )
        if status not in allowed:
            errors.append(f"{where}: status '{status}' niet toegestaan (kies uit {', '.join(sorted(allowed))})")
        if status in FORBIDDEN_STATUSES:
            errors.append(f"{where}: status '{status}' vraagt echte acceptatie op de NAS en wordt hier nooit gezet")
        errors.extend(check_validatie(where, entry_id, entry.get("validatie", "")))
        errors.extend(check_validatie_bij_status(where, status, entry.get("validatie", "")))
        errors.extend(check_blokkade_in_validatie(where, entry.get("validatie", ""), entry.get("blokkade", "")))
        if status == "Geblokkeerd" and not entry.get("blokkade"):
            errors.append(f"{where}: status Geblokkeerd zonder blokkade-reden")
        if entry.get("repo") != REPO_NAME:
            errors.append(f"{where}: repo moet '{REPO_NAME}' zijn")
        if not is_calendar_date(entry.get("bijgewerkt", "")):
            errors.append(f"{where}: bijgewerkt moet een echte datum JJJJ-MM-DD zijn")
        if not str(entry.get("bewijs", "")).strip():
            errors.append(f"{where}: bewijs is leeg")
        errors.extend(check_commit_refs(repo, where, str(entry.get("bewijs", ""))))
    return errors


def check_validatie(where: str, entry_id: str, validatie: object) -> list[str]:
    """§11: alleen waarden uit de vaste lijst, gescheiden door "; ", geen dubbele, geen vrije tekst."""
    if not isinstance(validatie, str) or not validatie:
        return [f"{where}: validatie ontbreekt (contract §11)"]
    allowed = VALIDATIE_WAARDEN + (VALIDATIE_TESTMATRIX if TEST_ID_RE.match(entry_id) else ())
    parts = validatie.split(VALIDATIE_SEP)
    errors = [
        f"{where}: validatie '{part}' is geen toegestane waarde (contract §11; kies uit {' | '.join(allowed)}; "
        "meerdere met '; ', toelichting in 'opmerking')"
        for part in parts
        if part not in allowed
    ]
    if len(set(parts)) != len(parts):
        errors.append(f"{where}: validatie '{validatie}' bevat een waarde dubbel")
    if set(VALIDATIE_TESTMATRIX) <= set(parts):
        errors.append(f"{where}: validatie '{validatie}' is tegelijk Sim-geslaagd en Sim-mislukt (kies één uitkomst; "
                      "een rij die maar deels is uitgevoerd krijgt Sim-getest, toelichting in 'opmerking')")
    return errors


def check_validatie_bij_status(where: str, status: object, validatie: object) -> list[str]:
    """§11 (1.3): `Niet getest` alleen bij `Niet gestart`; geen tegenstrijdigheid; iGPU is geen NAS-bewijs."""
    if not isinstance(validatie, str) or not validatie:
        return []  # al gemeld door check_validatie
    parts = validatie.split(VALIDATIE_SEP)
    tested = [part for part in parts if part in TESTUITKOMSTEN]
    errors: list[str] = []
    if NIET_GETEST in parts and status != STATUS_NIET_GESTART:
        errors.append(f"{where}: validatie '{NIET_GETEST}' mag alleen bij status '{STATUS_NIET_GESTART}' "
                      f"(contract §11, 1.3), niet bij '{status}'")
    if NIET_GETEST in parts and tested:
        errors.append(f"{where}: validatie '{validatie}' zegt tegelijk '{NIET_GETEST}' en {', '.join(tested)} "
                      "(tegenstrijdig; kies één)")
    elif status == STATUS_NIET_GESTART and tested:
        errors.append(f"{where}: status '{STATUS_NIET_GESTART}' met testuitkomst {', '.join(tested)} is tegenstrijdig "
                      "(is er getest, dan is de status 'Bezig' of 'Geblokkeerd')")
    if INTEL_IGPU in parts and NIET_GEVALIDEERD_HARDWARE not in parts:
        errors.append(f"{where}: '{INTEL_IGPU}' zegt niets over de GPU's van de NAS; zet er "
                      f"'{NIET_GEVALIDEERD_HARDWARE}' naast (contract §11, 1.3)")
    return errors


def check_blokkade_in_validatie(where: str, validatie: object, blokkade: object) -> list[str]:
    """Een `NIET GEVALIDEERD (…)` in de blokkade is een lijstwaarde en staat ook in `validatie` (§11, 1.3)."""
    if not isinstance(validatie, str) or not isinstance(blokkade, str):
        return []
    parts = set(validatie.split(VALIDATIE_SEP))
    errors: list[str] = []
    for value in dict.fromkeys(NIET_GEVALIDEERD_RE.findall(blokkade)):
        if value not in VALIDATIE_WAARDEN:
            choices = " | ".join(v for v in VALIDATIE_WAARDEN if v.startswith("NIET GEVALIDEERD"))
            errors.append(f"{where}: blokkade noemt '{value}', dat is geen waarde uit de vaste lijst van §11 "
                          f"(kies uit {choices}; toelichting in 'opmerking')")
        elif value not in parts:
            errors.append(f"{where}: blokkade noemt '{value}', maar validatie niet (zet het als lijstwaarde in "
                          "'validatie')")
    return errors


def is_contract_or_review_id(entry_id: str) -> bool:
    return entry_id.startswith(("C1.", "REVIEW-"))


def conformiteit_punten(repo: Path, rel: str) -> set[str] | None:
    """ID's uit de hoofdstukken "voor alle repos" en "jelly-leon-web" van een gekopieerde conformiteitslijst.

    1.3: tabelrijen `| C1.3-ALG-01 |`; 1.2: tabelrijen `| JW1 |` en opsommingen `- **A1**`. None = lijst ontbreekt.
    """
    path = repo / rel
    if not path.is_file():
        return None
    found: set[str] = set()
    own = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            own = bool(EIGEN_HOOFDSTUK_RE.match(line))
            continue
        if not own:
            continue
        match = re.match(r"^\| (C1\.3-[A-Z]+-\d{2}|[A-Z]+\d+) \|", line) or re.match(r"^- \*\*([A-Z]+\d+)\*\*", line)
        if match:
            found.add(match.group(1))
    return found


def check_contract_point(repo: Path, where: str, entry_id: str, cache: dict[str, set[str] | None]) -> list[str]:
    """Contractpunt of review (§11, 1.3): vaste vorm, bestaat in de gekopieerde lijst en gaat over deze repo."""
    if entry_id.startswith("REVIEW-"):
        if not REVIEW_RE.match(entry_id):
            return [(f"{where}: review-id '{entry_id}' volgt niet REVIEW-{REPO_NAME}-<onderwerp> "
                     "(kleine letters, cijfers, '-' en '.'; contract §11)")]
        return []
    if CONTRACTPUNT_13_RE.match(entry_id):
        rel, code = CONFORMITEIT_13_REL, entry_id
    elif CONTRACTPUNT_12_RE.match(entry_id):
        rel, code = CONFORMITEIT_12_REL, entry_id.removeprefix("C1.2-")
    else:
        return [f"{where}: contractpunt '{entry_id}' volgt niet C1.3-<REPO>-<nn> of C1.2-<code> (contract §11, K9)"]
    if rel not in cache:
        cache[rel] = conformiteit_punten(repo, rel)
    punten = cache[rel]
    if punten is None:
        return [f"{where}: {rel} ontbreekt; contractpunt '{entry_id}' is niet te controleren (fail-closed)"]
    if code not in punten:
        return [(f"{where}: contractpunt '{entry_id}' staat niet in {rel} onder 'voor alle repos' of "
                 "'jelly-leon-web' (bestaat het, en gaat het over deze repo?)")]
    return []


def is_calendar_date(value: object) -> bool:
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def check_commit_refs(repo: Path, where: str, bewijs: str) -> list[str]:
    """Elke in `bewijs` genoemde commit (hex, 7–40 tekens) bestaat in deze repo — geen bewijs dat niet bestaat."""
    errors: list[str] = []
    for ref in dict.fromkeys(COMMIT_REF_RE.findall(bewijs)):
        if ref.isdigit():
            continue
        if run_git(repo, "cat-file", "-e", f"{ref}^{{commit}}", check=False).returncode != 0:
            errors.append(
                f"{where}: commit {ref} uit 'bewijs' bestaat niet in deze repo (andere repo? schrijf <repo>@{ref})"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Controleer versie-, identiteits- en bewijsregels van de webfork.")
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO_ROOT)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        baseline = load_baseline(repo)
        errors = (check_baseline(repo, baseline) + check_identity(repo, baseline) + check_visible_name(repo, baseline)
                  + check_toolchain(repo, baseline) + check_evidence(repo))
    except ToolError as exc:
        print(f"FOUT: {exc}", file=sys.stderr)
        return exc.exit_code if exc.exit_code != 1 else 3
    if errors:
        print(f"FORKCONSISTENTIE NIET IN ORDE ({len(errors)} problemen):", file=sys.stderr)
        for line in errors:
            print(f"  - {line}", file=sys.stderr)
        return 1
    print(
        f"Forkconsistentie in orde: basis {baseline['upstream_tag']} ({baseline['upstream_commit'][:12]}), "
        f"forkversie {baseline['fork_version']}, technische identiteit {baseline.get('package_name', 'jellyfin-web')} "
        f"{baseline['upstream_version']}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
