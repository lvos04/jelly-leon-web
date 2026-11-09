#!/usr/bin/env python3
"""Controleert de GitHub-workflows van de webfork (ADR-0007).

1. **Upstream-workflows** (alles in .github/workflows buiten de fork-eigen paden): elk gebruik van een geheim van
   upstream (`JF_BOT_TOKEN`, `CLOUDFLARE_*`, … — alles behalve `GITHUB_TOKEN`) moet achter een repository-guard
   zitten (`github.repository == 'jellyfin/jellyfin-web'`, `contains(github.repository, 'jellyfin/')` of
   `github.repository_owner == 'jellyfin'`), op job- of stapniveau, ook via herbruikbare workflows
   (`uses: ./.github/workflows/…` + `secrets: inherit`). Zo falen of handelen upstream-bots en -deploys nooit in de
   fork, zonder dat iemand de workflows stilletjes uitzet. Een upstream-sync die een onbewaakt geheim binnenhaalt
   laat deze controle falen → dan een guard als geregistreerde patch toevoegen (PATCHES.md).
2. **Eigen workflows** (fork-eigen paden): acties op een volledige commit-SHA, container-images met `@sha256:`,
   geen `latest`, exacte Node-versie, expliciete `permissions`.

`--overzicht` drukt per upstream-workflow triggers, geheimen en guard-status af (bron voor ADR-0007).
Exitcodes: 0 = in orde, 1 = overtreding, 3 = gebruiks-/omgevingsfout.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jlw_common import DEFAULT_REPO_ROOT, ToolError, is_fork_path, load_fork_paths  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover - in CI via requirements-dev.txt
    yaml = None

WORKFLOW_DIR = ".github/workflows"
GUARD_RE = re.compile(
    r"github\.repository\s*==\s*'jellyfin/[^']+'"
    r"|contains\(\s*github\.repository\s*,\s*'jellyfin/'\s*\)"
    r"|github\.repository_owner\s*==\s*'jellyfin'"
)
SECRET_RE = re.compile(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)")
ALLOWED_SECRETS = {"GITHUB_TOKEN"}
LOCAL_REUSABLE_RE = re.compile(r"^\./\.github/workflows/([^@\s]+)$")
SHA_PIN_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
EXACT_NODE_RE = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass
class WorkflowInfo:
    path: str
    triggers: list[str]
    data: dict
    secrets: set[str] = field(default_factory=set)


def _load_yaml(text: str, where: str) -> dict:
    if yaml is None:
        raise ToolError("PyYAML ontbreekt; installeer tools/jelly-leon-web/requirements-dev.txt", exit_code=3)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ToolError(f"{where}: ongeldige YAML: {exc}", exit_code=1) from exc
    if not isinstance(data, dict):
        raise ToolError(f"{where}: verwacht een YAML-object", exit_code=1)
    return data


def _triggers(data: dict) -> list[str]:
    # PyYAML (YAML 1.1) leest de sleutel `on` als boolean True.
    raw = data.get("on", data.get(True))
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, dict):
        return [str(key) for key in raw]
    return []


def _text(value: object) -> str:
    if yaml is None:  # pragma: no cover
        return str(value)
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=True) if value is not None else ""


def _top_level_terms(expr: str) -> tuple[list[str], bool]:
    """Splits een expressie op `&&` op het hoogste niveau (buiten haakjes en strings).

    Geeft (conjuncten, heeft_top_level_or). Haakjes en strings ('…') blijven binnen hun term.
    """
    terms: list[str] = []
    depth = 0
    in_string = False
    has_or = False
    current: list[str] = []
    index = 0
    while index < len(expr):
        char = expr[index]
        pair = expr[index:index + 2]
        if in_string:
            current.append(char)
            if char == "'":
                in_string = False
        elif char == "'":
            in_string = True
            current.append(char)
        elif char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth -= 1
            current.append(char)
        elif depth == 0 and pair == "&&":
            terms.append("".join(current))
            current = []
            index += 1
        elif depth == 0 and pair == "||":
            has_or = True
            current.append(pair)
            index += 1
        else:
            current.append(char)
        index += 1
    terms.append("".join(current))
    return [t.strip() for t in terms], has_or


def _strip_outer_parens(term: str) -> str:
    while term.startswith("(") and term.endswith(")"):
        inner = term[1:-1].strip()
        _, has_or = _top_level_terms(inner)
        if has_or or len(_top_level_terms(inner)[0]) != 1:
            break
        term = inner
    return term


def _guarded(condition: object) -> bool:
    """Waar alleen als de repository-guard een conjunct op het hoogste niveau is.

    `github.repository == 'jellyfin/jellyfin-web' && x` telt als bewaakt; `guard || x` en `(guard || x) && y` niet,
    want dan kan de job in de fork alsnog draaien (aanvulling P4-0: de guard op workflow_run.yml gebruikt `&&`).
    """
    if not isinstance(condition, str):
        return False
    expr = condition.strip()
    if expr.startswith("${{") and expr.endswith("}}"):
        expr = expr[3:-2].strip()
    terms, has_or = _top_level_terms(expr)
    if has_or:
        return False
    return any(GUARD_RE.fullmatch(_strip_outer_parens(term)) for term in terms)


def _upstream_secrets(value: object) -> set[str]:
    return {name for name in SECRET_RE.findall(_text(value)) if name not in ALLOWED_SECRETS}


def load_workflows(repo: Path) -> dict[str, WorkflowInfo]:
    directory = repo / WORKFLOW_DIR
    if not directory.is_dir():
        raise ToolError(f"{WORKFLOW_DIR} ontbreekt", exit_code=3)
    result: dict[str, WorkflowInfo] = {}
    for path in sorted(list(directory.glob("*.yml")) + list(directory.glob("*.yaml"))):
        rel = f"{WORKFLOW_DIR}/{path.name}"
        data = _load_yaml(path.read_text(encoding="utf-8"), rel)
        info = WorkflowInfo(path=rel, triggers=_triggers(data), data=data)
        info.secrets = _upstream_secrets(data.get("jobs"))
        result[path.name] = info
    return result


def unguarded_secret_uses(name: str, workflows: dict[str, WorkflowInfo], stack: tuple[str, ...] = ()) -> list[str]:
    """Upstream-geheimen die vanuit deze workflow bereikbaar zijn zonder een repository-guard te passeren."""
    if name in stack:
        return []
    info = workflows.get(name)
    if info is None:
        return []
    found: list[str] = []
    jobs = info.data.get("jobs") or {}
    for job_id, job in jobs.items():
        if not isinstance(job, dict) or _guarded(job.get("if")):
            continue
        prefix = f"{info.path} › {job_id}"
        reusable = job.get("uses")
        if isinstance(reusable, str):
            local = LOCAL_REUSABLE_RE.match(reusable)
            passes_secrets = job.get("secrets") == "inherit" or _upstream_secrets(job.get("secrets"))
            if local and passes_secrets:
                for item in unguarded_secret_uses(local.group(1), workflows, stack + (name,)):
                    found.append(f"{prefix} → {item}")
            for secret in sorted(_upstream_secrets(job.get("secrets"))):
                found.append(f"{prefix}: geeft secrets.{secret} door")
            continue
        for secret in sorted(_upstream_secrets({k: v for k, v in job.items() if k != "steps"})):
            found.append(f"{prefix}: secrets.{secret} op jobniveau")
        for index, step in enumerate(job.get("steps") or []):
            if not isinstance(step, dict) or _guarded(step.get("if")):
                continue
            label = step.get("name") or step.get("uses") or f"stap {index + 1}"
            for secret in sorted(_upstream_secrets(step)):
                found.append(f"{prefix} › {label}: secrets.{secret}")
    return found


def check_upstream(repo: Path, workflows: dict[str, WorkflowInfo], fork_paths: list[str]) -> list[str]:
    errors: list[str] = []
    for name, info in workflows.items():
        if is_fork_path(info.path, fork_paths):
            continue
        entry_triggers = [t for t in info.triggers if t != "workflow_call"]
        if not entry_triggers:
            continue  # herbruikbaar: wordt via de aanroepers gecontroleerd
        for item in unguarded_secret_uses(name, workflows):
            errors.append(
                f"{item} — upstream-geheim zonder repository-guard (trigger: {', '.join(entry_triggers)}); "
                "voeg een guard toe als geregistreerde patch (ADR-0007)"
            )
    return errors


def check_own(repo: Path, workflows: dict[str, WorkflowInfo], fork_paths: list[str]) -> list[str]:
    errors: list[str] = []
    for info in workflows.values():
        if not is_fork_path(info.path, fork_paths):
            continue
        if "permissions" not in info.data:
            errors.append(f"{info.path}: geen expliciete top-level 'permissions' (minimale rechten verplicht)")
        for job_id, job in (info.data.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            where = f"{info.path} › {job_id}"
            if isinstance(job.get("uses"), str) and not job["uses"].startswith("./"):
                if not SHA_PIN_RE.match(job["uses"]):
                    errors.append(f"{where}: herbruikbare workflow '{job['uses']}' niet op commit-SHA vastgezet")
            container = job.get("container")
            image = container.get("image") if isinstance(container, dict) else container
            if isinstance(image, str) and "@sha256:" not in image:
                errors.append(f"{where}: container-image '{image}' zonder @sha256-digest")
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                uses = step.get("uses")
                if isinstance(uses, str) and not uses.startswith("./"):
                    if uses.startswith("docker://"):
                        if "@sha256:" not in uses:
                            errors.append(f"{where}: '{uses}' zonder @sha256-digest")
                    elif not SHA_PIN_RE.match(uses):
                        errors.append(f"{where}: actie '{uses}' niet op een volledige commit-SHA vastgezet")
                node = (step.get("with") or {}).get("node-version") if isinstance(step.get("with"), dict) else None
                if node is not None and not EXACT_NODE_RE.match(str(node)):
                    errors.append(f"{where}: node-version '{node}' is niet exact (x.y.z)")
        if re.search(r":latest\b", _text(info.data)):
            errors.append(f"{info.path}: verwijzing naar een ':latest'-tag")
    return errors


def overview(workflows: dict[str, WorkflowInfo], fork_paths: list[str]) -> list[str]:
    lines = ["| Workflow | Triggers | Upstream-geheimen | Onbewaakt bereikbaar |", "|---|---|---|---|"]
    for name, info in workflows.items():
        if is_fork_path(info.path, fork_paths):
            continue
        open_uses = unguarded_secret_uses(name, workflows)
        lines.append(
            f"| `{name}` | {', '.join(info.triggers) or '—'} | {', '.join(sorted(info.secrets)) or '—'} | "
            f"{len(open_uses) if [t for t in info.triggers if t != 'workflow_call'] else 'via aanroeper'} |"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Controleer upstream-guards en pinning van de workflows.")
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--overzicht", action="store_true", help="druk een tabel van de upstream-workflows af")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        fork_paths = load_fork_paths(repo)
        workflows = load_workflows(repo)
        errors = check_upstream(repo, workflows, fork_paths) + check_own(repo, workflows, fork_paths)
    except ToolError as exc:
        print(f"FOUT: {exc}", file=sys.stderr)
        return exc.exit_code
    if args.overzicht:
        print("\n".join(overview(workflows, fork_paths)))
    if errors:
        print(f"WORKFLOWS NIET IN ORDE ({len(errors)} problemen):", file=sys.stderr)
        for line in errors:
            print(f"  - {line}", file=sys.stderr)
        return 1
    own = sum(1 for i in workflows.values() if is_fork_path(i.path, fork_paths))
    print(f"Workflows in orde: {len(workflows) - own} upstream (geheimen bewaakt), {own} eigen (vastgezet).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
