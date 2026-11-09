"""Unit-tests voor de rapport- en controlelogica van e2e/web_smoke.py (zonder Docker of browser).

Doel: de smoketest kan nooit "geslaagd" melden zonder echte, geslaagde stappen (contract: geen gesimuleerd succes),
redigeert wachtwoorden/tokens en herkent dataverlies of een verkeerde webclient na herstart/terugzetten.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "e2e"))

import web_smoke  # noqa: E402

IDS = {"server_id": "srv-1", "item_id": "item-1", "admin_id": "adm-1", "kid_id": "kid-1", "token": "t"}
CREDS = {"admin_user": "jl-beheer", "admin_password": "geheim-a", "kid_user": "jl-kind", "kid_password": "geheim-k"}


class FakeApi:
    """Speelt de Jellyfin-API na; elke afwijking is per test in te stellen."""

    def __init__(self, server_id="srv-1", item_status=200, stream=b"RIFF" + b"\0" * 2000, kid_count=0,
                 index_html=b"<html><title>Jellyfin</title></html>"):
        self.server_id = server_id
        self.item_status = item_status
        self.stream = stream
        self.kid_count = kid_count
        self.index_html = index_html

    def json(self, method, path, token=None, body=None, device_id=None):
        if path == "/System/Info/Public":
            return 200, {"Id": self.server_id, "ProductName": "Jellyfin Server"}
        if path == "/Users/AuthenticateByName":
            return 200, {"AccessToken": f"tok-{body['Username']}", "ServerId": self.server_id}
        if path.startswith("/Items/item-1"):
            return self.item_status, ({"Id": "item-1"} if self.item_status == 200 else None)
        if path.startswith("/Items?"):
            return 200, {"TotalRecordCount": self.kid_count}
        raise AssertionError(f"onverwachte call {method} {path}")

    def request(self, method, path, token=None, body=None, device_id=None):
        assert path.startswith("/Audio/item-1/stream") and token
        return (200 if self.stream else 404), self.stream

    def raw_get(self, path):
        assert path == "/web/index.html"
        return 200, self.index_html


def report() -> web_smoke.Report:
    return web_smoke.Report(mode="fork", base_url="http://127.0.0.1:1", image="test")


def test_report_without_steps_never_passes():
    rep = report()
    assert rep.passed is False
    assert rep.to_json()["resultaat"] == "mislukt"


def test_report_redacts_secrets_and_one_failure_fails_all():
    rep = report()
    rep.secrets += ["geheim-a", "tok-123"]
    rep.add("stap 1", True, "wachtwoord geheim-a en token tok-123")
    assert rep.passed
    rep.add("stap 2", False, "mislukt")
    data = rep.to_json()
    assert data["resultaat"] == "mislukt" and data["geslaagd"] == 1 and data["aantal_stappen"] == 2
    assert "geheim-a" not in json.dumps(data) and "tok-123" not in json.dumps(data)


def test_verify_data_accepts_intact_server():
    rep = report()
    web_smoke.verify_data(FakeApi(), rep, "herstart", CREDS, IDS)
    assert rep.passed and len(rep.steps) == 2
    assert "tok-jl-beheer" not in json.dumps(rep.to_json())  # nieuw token meteen geredigeerd


@pytest.mark.parametrize(
    "api, failing_step",
    [
        (FakeApi(server_id="srv-NIEUW"), "gegevens behouden"),          # nieuwe lege /config = dataverlies
        (FakeApi(item_status=404), "gegevens behouden"),                # bibliotheek kwijt
        (FakeApi(stream=b""), "stream en server-ACL werken"),           # stream breekt
        (FakeApi(stream=b"<html>fout</html>" * 100), "stream en server-ACL werken"),  # geen audio
        (FakeApi(kid_count=1), "stream en server-ACL werken"),          # kinderprofiel ziet de titel
    ],
)
def test_verify_data_detects_data_loss_broken_stream_and_acl_leak(api, failing_step):
    rep = report()
    web_smoke.verify_data(api, rep, "terugzetten", CREDS, IDS)
    assert not rep.passed
    failed = [s["stap"] for s in rep.steps if not s["geslaagd"]]
    assert failed == [f"terugzetten: {failing_step}"]


def test_served_web_distinguishes_fork_and_stock(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    fork_html = b"<html><title>Jellyfin</title><!-- fork --></html>"
    (dist / "index.html").write_bytes(fork_html)
    args = web_smoke.build_parser().parse_args(["--modus", "fork", "--dist", str(dist)])
    assert web_smoke.served_web(FakeApi(index_html=fork_html), args, fork_web=True)[0] is True
    assert web_smoke.served_web(FakeApi(index_html=fork_html), args, fork_web=False)[0] is False
    stock = b"<html><title>Jellyfin</title><!-- stock --></html>"
    assert web_smoke.served_web(FakeApi(index_html=stock), args, fork_web=False)[0] is True
    assert web_smoke.served_web(FakeApi(index_html=stock), args, fork_web=True)[0] is False
    renamed = b"<html><title>Iets anders</title></html>"  # zichtbare naam mag in P0 niet wijzigen
    assert web_smoke.served_web(FakeApi(index_html=renamed), args, fork_web=False)[0] is False


def test_unreachable_server_gives_failed_report_not_success(tmp_path, capsys):
    out = tmp_path / "uit"
    rc = web_smoke.main(["--modus", "stock", "--url", "http://127.0.0.1:9", "--start-timeout", "0.5",
                         "--uitvoer", str(out), "--schermafbeeldingen", "geen"])
    assert rc == 1
    data = json.loads((out / "web-smoke-stock.json").read_text(encoding="utf-8"))
    assert data["resultaat"] == "mislukt"
    assert data["stappen"][0]["stap"] == "server gezond" and data["stappen"][0]["geslaagd"] is False


def test_missing_playwright_is_environment_error_and_never_success(tmp_path, monkeypatch):
    def fake_api_phase(api, args, rep, creds):
        rep.add("API-deel", True, "nagespeeld")
        return dict(IDS)

    def no_playwright(*_args, **_kwargs):
        raise ImportError("No module named 'playwright'")

    monkeypatch.setattr(web_smoke, "api_phase", fake_api_phase)
    monkeypatch.setattr(web_smoke, "ui_phase", no_playwright)
    out = tmp_path / "uit"
    rc = web_smoke.main(["--modus", "stock", "--url", "http://127.0.0.1:9", "--uitvoer", str(out)])
    assert rc == 3
    data = json.loads((out / "web-smoke-stock.json").read_text(encoding="utf-8"))
    assert data["resultaat"] == "mislukt"
    assert {"stap": "browserdeel uitgevoerd", "geslaagd": False} == {
        k: data["stappen"][-1][k] for k in ("stap", "geslaagd")
    }


def test_fork_mode_without_build_is_environment_error(tmp_path, capsys):
    rc = web_smoke.main(["--modus", "fork", "--dist", str(tmp_path / "leeg")])
    assert rc == 3
    assert "index.html ontbreekt" in capsys.readouterr().err
