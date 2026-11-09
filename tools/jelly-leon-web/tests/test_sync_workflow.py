"""Tests voor .github/workflows/upstream-sync.yml (simulator: de echte run-scripts van de workflow in bash).

Bewaakt drie dingen die actionlint niet ziet:
  * fouten in een pijplijn (tagdetectie | tee) laten de stap falen, nooit stil "geen kandidaat" (pipefail);
  * het pushtoken komt nooit in een job die upstream-code of npm uitvoert, nooit in de URL of uitvoer, en git-hooks
    lopen niet mee;
  * bundle → schone runner → push werkt, en een bestaande sync/<tag> wordt nooit overschreven (geen force-push).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import upstream_sync
import yaml
from conftest import REPO_ROOT, git

WORKFLOW = REPO_ROOT / ".github/workflows/upstream-sync.yml"
TOKEN = "ghp_dummyTokenVoorDeTest0123456789abcdef"


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def step(job: str, name_start: str) -> dict:
    for item in workflow()["jobs"][job]["steps"]:
        if str(item.get("name", "")).startswith(name_start):
            return item
    raise AssertionError(f"stap '{name_start}' niet gevonden in job {job}")


def run_step(script: str, cwd: Path, env: dict) -> subprocess.CompletedProcess[str]:
    """Zoals GitHub `shell: bash` uitvoert: bash --noprofile --norc -eo pipefail."""
    assert "${{" not in script, "run-script mag geen expressies bevatten (alleen env), ook i.v.m. injectie"
    full_env = {"PATH": os.environ["PATH"], "HOME": str(cwd), "LANG": "C.UTF-8", **env}
    return subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script], cwd=cwd,
                          env=full_env, capture_output=True, text=True, check=False)


def test_all_run_steps_use_bash_with_pipefail():
    data = workflow()
    assert data["defaults"]["run"]["shell"] == "bash"
    for job_id, job in data["jobs"].items():
        assert "shell" not in (job.get("defaults") or {}).get("run", {}), job_id
        for item in job["steps"]:
            assert item.get("shell", "bash") == "bash", (job_id, item.get("name"))


def test_push_token_only_in_job_without_third_party_code():
    jobs = workflow()["jobs"]
    holders = [job_id for job_id, job in jobs.items() if "secrets." in yaml.safe_dump(job)]
    assert holders == ["beoordeling"]
    job = jobs["beoordeling"]
    text = yaml.safe_dump(job)
    for forbidden in ("npm", "node", "playwright", "pip install", "web_smoke", "upstream_sync.py", "setup-node"):
        assert forbidden not in text, f"'{forbidden}' in de job met het pushtoken"
    push = step("beoordeling", "sync/<tag> pushen")
    assert "x-access-token:${" not in push["run"].replace("printf 'x-access-token:%s'", "")
    assert "--force" not in push["run"] and " -f " not in push["run"]
    assert jobs["beoordeling"]["steps"][0]["with"]["persist-credentials"] is False


def test_failed_tag_detection_fails_the_step(tmp_path):
    script = step("detecteer", "Kandidaten kiezen")["run"]
    repo = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "tools/jelly-leon-web", repo / "tools/jelly-leon-web",
                    ignore=shutil.ignore_patterns("__pycache__", "tests"))
    out = tmp_path / "gh_output"
    env = {"UPSTREAM_URL": str(tmp_path / "bestaat-niet.git"), "RUNNER_TEMP": str(tmp_path),
           "GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"), "INPUT_SPOOR": "beide"}
    proc = run_step(script, repo, env)
    assert proc.returncode != 0, proc.stdout + proc.stderr  # zonder pipefail zou `| tee` dit verbergen
    assert not out.exists() or "heeft_kandidaat=true" not in out.read_text(encoding="utf-8")


def test_explicit_tag_input_is_validated(tmp_path):
    script = step("detecteer", "Kandidaten kiezen")["run"]
    repo = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "tools/jelly-leon-web", repo / "tools/jelly-leon-web",
                    ignore=shutil.ignore_patterns("__pycache__", "tests"))
    out = tmp_path / "gh_output"
    base = {"RUNNER_TEMP": str(tmp_path), "GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(tmp_path / "s")}
    bad = run_step(script, repo, {**base, "INPUT_TAG": "v12.0-rc1; echo pwned"})
    assert bad.returncode != 0 and "geen stabiele upstream-tag" in bad.stderr
    good = run_step(script, repo, {**base, "INPUT_TAG": "v10.11.12"})
    assert good.returncode == 0, good.stderr
    assert 'kandidaten=["v10.11.12"]' in out.read_text(encoding="utf-8")


@pytest.fixture()
def synced(repos, tmp_path):
    """Fork + 'GitHub-remote' (bare) vóór de sync; daarna sync/v1.0.1 in de fork zoals job Sync dat doet."""
    fork: Path = repos["fork"]
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(fork), str(remote)], check=True)
    fork_sha = git(fork, "rev-parse", "HEAD")
    rc = upstream_sync.main(["--repo", str(fork), "merge", "--tag", "v1.0.1", "--bron", str(repos["upstream"]),
                             "--maak-lokale-tag"])
    assert rc == 0
    runner = tmp_path / "runner"
    runner.mkdir()
    bundle_env = {"SYNC_TAG": "v1.0.1", "RUNNER_TEMP": str(runner), "GITHUB_SHA": fork_sha}
    proc = run_step(step("sync", "Resultaat als git-bundle bewaren")["run"], fork, bundle_env)
    assert proc.returncode == 0, proc.stderr
    bundle = runner / "sync" / "sync.bundle"
    assert bundle.is_file()
    return {"remote": remote, "bundle": bundle, "fork": fork, "tmp": tmp_path}


def clean_runner_checkout(ctx: dict, name: str) -> tuple[Path, dict]:
    """Schone runner (job beoordeling): eigen checkout, geslaagd-artefact, remote-URL via insteadOf naar de bare repo."""
    tmp: Path = ctx["tmp"]
    checkout = tmp / name
    subprocess.run(["git", "clone", "-q", str(ctx["remote"]), str(checkout)], check=True)
    # Een kwaadaardige hook mag nooit meelopen (core.hooksPath=/dev/null).
    hook = checkout / ".git/hooks/pre-push"
    hook.write_text(f"#!/bin/sh\necho gelekt > {tmp / 'hook-liep'}\n", encoding="utf-8")
    hook.chmod(0o755)
    runner = tmp / f"{name}-temp"
    (runner / "geslaagd").mkdir(parents=True)
    shutil.copy(ctx["bundle"], runner / "geslaagd" / "sync.bundle")
    gitconfig = tmp / f"{name}.gitconfig"
    gitconfig.write_text(f'[url "file://{ctx["remote"]}"]\n\tinsteadOf = https://github.com/lvos04/test.git\n'
                         "[user]\n\tname = t\n\temail = t@example.invalid\n", encoding="utf-8")
    env = {"SYNC_TAG": "v1.0.1", "REPO": "lvos04/test", "RUNNER_TEMP": str(runner),
           "GITHUB_STEP_SUMMARY": str(runner / "summary"), "GIT_CONFIG_GLOBAL": str(gitconfig),
           "GIT_CONFIG_NOSYSTEM": "1"}
    return checkout, env


def test_bundle_is_pushed_from_clean_runner_without_leaking_token_or_running_hooks(synced):
    checkout, env = clean_runner_checkout(synced, "runner1")
    script = step("beoordeling", "sync/<tag> pushen")["run"]
    proc = run_step(script, checkout, {**env, "PUSH_TOKEN": TOKEN})
    assert proc.returncode == 0, proc.stderr
    remote = synced["remote"]
    assert git(remote, "rev-parse", "refs/heads/sync/v1.0.1") == git(synced["fork"], "rev-parse", "sync/v1.0.1")
    assert git(remote, "rev-parse", "refs/tags/upstream-v1.0.1^{commit}") == git(
        synced["fork"], "rev-parse", "upstream-v1.0.1^{commit}")
    assert TOKEN not in proc.stdout + proc.stderr
    assert not (synced["tmp"] / "hook-liep").exists()
    assert TOKEN not in (checkout / ".git/config").read_text(encoding="utf-8")


def test_existing_sync_branch_is_never_overwritten(synced):
    checkout, env = clean_runner_checkout(synced, "runner1")
    script = step("beoordeling", "sync/<tag> pushen")["run"]
    assert run_step(script, checkout, {**env, "PUSH_TOKEN": TOKEN}).returncode == 0
    remote = synced["remote"]
    first = git(remote, "rev-parse", "refs/heads/sync/v1.0.1")
    # Iemand werkte de review-branch bij; een volgende run mag die niet overschrijven.
    review = synced["tmp"] / "review"
    subprocess.run(["git", "clone", "-q", "-b", "sync/v1.0.1", str(remote), str(review)], check=True)
    (review / "review.txt").write_text("beoordeeld\n", encoding="utf-8")
    git(review, "add", "review.txt")
    git(review, "-c", "user.name=r", "-c", "user.email=r@example.invalid", "commit", "-q", "-m", "review")
    git(review, "push", "-q", "origin", "sync/v1.0.1")
    reviewed = git(remote, "rev-parse", "refs/heads/sync/v1.0.1")
    assert reviewed != first
    checkout2, env2 = clean_runner_checkout(synced, "runner2")
    proc = run_step(script, checkout2, {**env2, "PUSH_TOKEN": TOKEN})
    assert proc.returncode == 0, proc.stderr
    assert "bestaat al" in proc.stdout
    assert git(remote, "rev-parse", "refs/heads/sync/v1.0.1") == reviewed


def test_without_token_nothing_is_pushed(synced):
    checkout, env = clean_runner_checkout(synced, "runner1")
    proc = run_step(step("beoordeling", "sync/<tag> pushen")["run"], checkout, {**env, "PUSH_TOKEN": ""})
    assert proc.returncode == 0
    assert "Geen JLW_SYNC_PUSH_TOKEN" in proc.stdout
    branches = subprocess.run(["git", "-C", str(synced["remote"]), "branch", "--list", "sync/*"],
                              capture_output=True, text=True, check=True).stdout
    assert branches.strip() == ""
