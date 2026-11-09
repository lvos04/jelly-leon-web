"""Tests voor workflow_check.py: repository-guards op upstream-geheimen en pinning van eigen workflows (ADR-0007)."""

from __future__ import annotations

from pathlib import Path

import pytest

import workflow_check
from conftest import REPO_ROOT, write

SHA = "8e8c483db84b4bee98b60c0593521ed34d9990e8"
FORK_PATHS = "tools/jelly-leon-web/\n.github/workflows/eigen.yml\n"


def make_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    write(repo, "tools/jelly-leon-web/fork_paths.txt", FORK_PATHS)
    for name, text in files.items():
        write(repo, f".github/workflows/{name}", text)
    return repo


REUSABLE_WITH_SECRET = """
name: bot
on:
  workflow_call:
jobs:
  label:
    runs-on: ubuntu-latest
    steps:
      - uses: some/action@v1
        with:
          repoToken: ${{ secrets.JF_BOT_TOKEN }}
"""


def test_real_repository_workflows_are_guarded():
    """De echte upstream-workflows (v12.4 + guard-patch JLW-0001 op workflow_run.yml) zijn in orde."""
    assert workflow_check.main(["--repo", str(REPO_ROOT)]) == 0


# Ingekort uit upstream jellyfin-web v12.4 (.github/workflows/workflow_run.yml): de reden voor patch JLW-0001.
WORKFLOW_RUN_V124 = """
on:
  workflow_run:
    workflows: [Pull Request]
    types: [completed]
jobs:
  automation:
    name: Automation
    {guard_automation}
    uses: ./.github/workflows/bot.yml
    secrets:
      JF_BOT_TOKEN: ${{{{ secrets.JF_BOT_TOKEN }}}}
  deploy:
    name: Deploy
    if: ${{{{ {guard_deploy}github.event.workflow_run.conclusion == 'success' }}}}
    uses: ./.github/workflows/bot.yml
    secrets:
      CLOUDFLARE_API_TOKEN: ${{{{ secrets.CLOUDFLARE_API_TOKEN }}}}
"""


def test_upstream_workflow_run_v124_without_guard_fails_and_jlw_0001_fixes_it(tmp_path):
    unguarded = WORKFLOW_RUN_V124.format(guard_automation="", guard_deploy="")
    repo = make_repo(tmp_path / "zonder", {"workflow_run.yml": unguarded, "bot.yml": REUSABLE_WITH_SECRET})
    errors = workflow_check.check_upstream(repo, workflow_check.load_workflows(repo), [])
    assert any("automation" in e for e in errors) and any("CLOUDFLARE_API_TOKEN" in e for e in errors)
    guarded = WORKFLOW_RUN_V124.format(
        guard_automation="if: ${{ github.repository == 'jellyfin/jellyfin-web' }}",
        guard_deploy="github.repository == 'jellyfin/jellyfin-web' && ",
    )
    repo = make_repo(tmp_path / "met", {"workflow_run.yml": guarded, "bot.yml": REUSABLE_WITH_SECRET})
    assert workflow_check.check_upstream(repo, workflow_check.load_workflows(repo), []) == []


@pytest.mark.parametrize(
    "condition, guarded",
    [
        ("${{ github.repository == 'jellyfin/jellyfin-web' }}", True),
        ("${{ github.repository == 'jellyfin/jellyfin-web' && github.event.workflow_run.conclusion == 'success' }}", True),
        ("github.event_name == 'push' && contains(github.repository, 'jellyfin/')", True),
        ("(github.repository_owner == 'jellyfin')", True),
        ("github.repository == 'jellyfin/jellyfin-web' && (a || b)", True),
        # een guard in een of-tak bewaakt niets: de job kan in de fork alsnog draaien
        ("github.repository == 'jellyfin/jellyfin-web' || always()", False),
        ("${{ always() || github.repository == 'jellyfin/jellyfin-web' }}", False),
        ("(github.repository == 'jellyfin/jellyfin-web' || true) && github.event_name == 'push'", False),
        ("github.repository != 'jellyfin/jellyfin-web'", False),
        ("github.event.pull_request.head.repo.full_name == 'jellyfin/jellyfin-web'", False),
        ("${{ contains(github.event.head_commit.message, 'jellyfin/') }}", False),
        (None, False),
    ],
)
def test_guard_must_be_top_level_conjunct(condition, guarded):
    assert workflow_check._guarded(condition) is guarded


def test_direct_unguarded_secret_fails(tmp_path):
    repo = make_repo(tmp_path, {"stale.yml": """
on:
  schedule:
    - cron: '0 1 * * *'
jobs:
  stale:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/stale@v9
        with:
          repo-token: ${{ secrets.JF_BOT_TOKEN }}
"""})
    errors = workflow_check.check_upstream(repo, workflow_check.load_workflows(repo), ["tools/jelly-leon-web/"])
    assert len(errors) == 1 and "secrets.JF_BOT_TOKEN" in errors[0] and "schedule" in errors[0]


def test_job_and_step_guards_are_accepted(tmp_path):
    repo = make_repo(tmp_path, {"ok.yml": """
on: [push]
jobs:
  a:
    if: ${{ github.repository == 'jellyfin/jellyfin-web' }}
    runs-on: ubuntu-latest
    steps:
      - run: echo ${{ secrets.CLOUDFLARE_API_TOKEN }}
  b:
    runs-on: ubuntu-latest
    steps:
      - if: contains(github.repository, 'jellyfin/')
        run: echo ${{ secrets.JF_BOT_TOKEN }}
      - run: echo ${{ secrets.GITHUB_TOKEN }}
"""})
    assert workflow_check.check_upstream(repo, workflow_check.load_workflows(repo), []) == []


def test_reusable_secret_via_inherit_needs_guard_at_caller(tmp_path):
    caller = """
on:
  pull_request:
jobs:
  automation:
    {guard}
    uses: ./.github/workflows/__bot.yml
    secrets: inherit
"""
    repo = make_repo(tmp_path, {"__bot.yml": REUSABLE_WITH_SECRET, "pr.yml": caller.format(guard="")})
    errors = workflow_check.check_upstream(repo, workflow_check.load_workflows(repo), [])
    assert len(errors) == 1 and "pr.yml › automation → .github/workflows/__bot.yml › label" in errors[0]
    guarded = caller.format(guard="if: ${{ github.repository == 'jellyfin/jellyfin-web' }}")
    repo2 = make_repo(tmp_path / "b", {"__bot.yml": REUSABLE_WITH_SECRET, "pr.yml": guarded})
    assert workflow_check.check_upstream(repo2, workflow_check.load_workflows(repo2), []) == []


def test_reusable_without_inherit_does_not_leak(tmp_path):
    repo = make_repo(tmp_path, {"__bot.yml": REUSABLE_WITH_SECRET, "pr.yml": """
on: [pull_request]
jobs:
  automation:
    uses: ./.github/workflows/__bot.yml
"""})
    assert workflow_check.check_upstream(repo, workflow_check.load_workflows(repo), []) == []


def test_own_workflow_pinning_rules(tmp_path):
    repo = make_repo(tmp_path, {"eigen.yml": f"""
name: eigen
on: [push]
jobs:
  a:
    runs-on: ubuntu-24.04
    container: node:22
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@{SHA}
        with:
          node-version: '22'
      - uses: docker://alpine:latest
"""})
    errors = workflow_check.check_own(repo, workflow_check.load_workflows(repo), ["tools/jelly-leon-web/", ".github/workflows/eigen.yml"])
    joined = "\n".join(errors)
    assert "geen expliciete top-level 'permissions'" in joined
    assert "container-image 'node:22' zonder @sha256-digest" in joined
    assert "'actions/checkout@v4' niet op een volledige commit-SHA" in joined
    assert "node-version '22' is niet exact" in joined
    assert "'docker://alpine:latest' zonder @sha256-digest" in joined
    assert "':latest'-tag" in joined


def test_own_workflow_fully_pinned_is_ok(tmp_path):
    repo = make_repo(tmp_path, {"eigen.yml": f"""
name: eigen
on: [push]
permissions:
  contents: read
jobs:
  a:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@{SHA} # v6.0.1
      - uses: actions/setup-node@{SHA}
        with:
          node-version: 22.23.4
"""})
    assert workflow_check.check_own(repo, workflow_check.load_workflows(repo), [".github/workflows/eigen.yml"]) == []


def test_overview_lists_upstream_workflows():
    workflows = workflow_check.load_workflows(REPO_ROOT)
    lines = workflow_check.overview(workflows, workflow_check.load_fork_paths(REPO_ROOT))
    assert lines[0].startswith("| Workflow |")
    assert any("`schedule.yml`" in line and "JF_BOT_TOKEN" in line for line in lines)
