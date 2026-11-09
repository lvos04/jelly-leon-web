#!/usr/bin/env python3
"""Web-client-smoketest voor jelly-leon-web (B03-001 webdeel; simulator, géén echte apparaten).

Start de officiële Jellyfin-serverimage (vast op digest) en stuurt een echte Chromium-browser (Playwright) door de
gebruikersreizen van een stock-client:

  --modus fork   onze productiebuild (dist/) alleen-lezen gemount op /jellyfin/jellyfin-web
  --modus stock  de web-client die in de officiële image zit (referentie: "geen regressie" = zelfde uitkomst)

Stappen (elk met eigen resultaat in het rapport):
  API     gezond → technische identiteit ("Jellyfin Server", upstream-versie) → juiste webbron geserveerd →
          eerste-startwizard → bibliotheek met zelfgegenereerde WAV → kinderprofiel zonder bibliotheektoegang →
          zoekresultaten per gebruiker (server-ACL) → zonder token geweigerd
  Browser (nl-NL) Nederlandse aanmeldpagina met titel "Jellyfin" → fout wachtwoord geweigerd (negatieve test) →
          inloggen → startscherm met bibliotheek → zoeken → detailpagina → afspelen (stream 200/206) →
          kinderprofiel vindt de titel niet → 360/390/768/1440 px zonder horizontale overloop (+ schermafbeelding)
  Opslag  (alleen als dit script de server zelf start; uit te zetten met --zonder-herstart)
          herstart van de container → zelfde server-ID, beheerder logt in, testnummer met hetzelfde ID, stream 200,
          kinderprofiel ziet nog steeds niets; in modus fork daarna "terugzetten": dezelfde /config met de
          stock-webclient van de image (vorige binary, B03-013) en weer "vooruit" naar de fork-build — telkens
          dezelfde controles. Zo blijft na herstart en terugzetten alles werken zonder dataverlies.

Wachtwoorden worden per run willekeurig gemaakt en nooit in het rapport gezet; tokens worden geredigeerd.
Dit bewijst alleen protocol- en UI-gedrag in een browser — echte tv's/telefoons blijven NIET GEVALIDEERD (D15).
Exitcodes: 0 = alle stappen geslaagd, 1 = minstens één stap mislukt, 3 = omgevingsfout (docker/playwright/dist).
Een omgevingsfout geeft nooit een rapport met resultaat "geslaagd": de ontbrekende stap staat er als mislukt in.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import make_test_media  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_IMAGE = (
    "docker.io/jellyfin/jellyfin:10.11.11@sha256:aefb67e6a7ff1debdd154a78a7bbb780fd0c873d8639210a7f6a2016ad2b35db"
)
WEB_DIR_IN_IMAGE = "/jellyfin/jellyfin-web"
LIBRARY_PATH = "/media/muziek"
TRACK_NAME = "Sinus 440 Hz"
VIEWPORTS = ((360, 780), (390, 844), (768, 1024), (1440, 900))
CLIENT = {"Client": "Jelly Leon Web Smoketest", "Device": "CI", "DeviceId": "jlw-web-smoke", "Version": "0.1.0"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def auth_value(token: str | None = None, device_id: str = CLIENT["DeviceId"]) -> str:
    client = dict(CLIENT, DeviceId=device_id)
    parts = [f'{key}="{value}"' for key, value in client.items()]
    if token:
        parts.append(f'Token="{token}"')
    return "MediaBrowser " + ", ".join(parts)


@dataclass
class Report:
    mode: str
    base_url: str
    image: str
    started_at: str = field(default_factory=utc_now)
    steps: list[dict] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    facts: dict = field(default_factory=dict)

    def redact(self, text: str) -> str:
        for value in self.secrets:
            if value:
                text = text.replace(value, "***")
        return text

    def add(self, name: str, ok: bool, detail: str) -> bool:
        self.steps.append({"stap": name, "geslaagd": bool(ok), "detail": self.redact(detail), "tijd_utc": utc_now()})
        mark = "OK  " if ok else "FOUT"
        print(f"[{mark}] {name}: {self.redact(detail)}", flush=True)
        return bool(ok)

    @property
    def passed(self) -> bool:
        return bool(self.steps) and all(step["geslaagd"] for step in self.steps)

    def to_json(self) -> dict:
        return {
            "test": "web-client-smoketest",
            "modus": self.mode,
            "server_image": self.image,
            "basis_url": self.base_url,
            "gestart_utc": self.started_at,
            "beeindigd_utc": utc_now(),
            "resultaat": "geslaagd" if self.passed else "mislukt",
            "aantal_stappen": len(self.steps),
            "geslaagd": sum(1 for s in self.steps if s["geslaagd"]),
            "validatie": "Sim-getest (headless Chromium + officiële serverimage; geen echte apparaten, D15)",
            "feiten": self.facts,
            "stappen": self.steps,
        }


class Api:
    def __init__(self, base_url: str, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Altijd direct naar de lokale testserver, nooit via een proxy.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, method: str, path: str, token: str | None = None, body: object | None = None,
                device_id: str = CLIENT["DeviceId"]) -> tuple[int, bytes]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        req.add_header("Authorization", auth_value(token, device_id))
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except (urllib.error.URLError, OSError):
            return 0, b""

    def json(self, method: str, path: str, **kwargs) -> tuple[int, object]:
        status, raw = self.request(method, path, **kwargs)
        try:
            return status, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return status, None

    def raw_get(self, path: str) -> tuple[int, bytes]:
        try:
            with self.opener.open(self.base_url + path, timeout=self.timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except (urllib.error.URLError, OSError):
            return 0, b""


# --------------------------------------------------------------------------------------------- server (docker)

def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(["docker", *args], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        proc = subprocess.CompletedProcess(["docker", *args], 127, "", "docker niet gevonden")
    if check and proc.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args[:2])} mislukte: {proc.stderr.strip()}")
    return proc


@dataclass(frozen=True)
class ServerDirs:
    config: Path
    cache: Path
    media: Path
    user: str


def prepare_dirs(work: Path) -> ServerDirs:
    """config/cache (schrijfbaar voor de containergebruiker) en media (alleen-lezen) in een eigen werkmap."""
    config, cache, media = work / "config", work / "cache", work / "media"
    for path in (config, cache, media):
        path.mkdir(parents=True, exist_ok=True)
    make_test_media.make(media)
    for root, dirs, files in os.walk(media):
        os.chmod(root, 0o755)
        for name in files:
            os.chmod(Path(root) / name, 0o644)
    if os.geteuid() == 0:
        # Lokaal als root: draai de server als 568:568 (zoals de TrueNAS-app), nooit als root.
        for path in (config, cache):
            os.chown(path, 568, 568)
        user = "568:568"
    else:
        user = f"{os.getuid()}:{os.getgid()}"
    os.chmod(work, 0o755)
    return ServerDirs(config=config, cache=cache, media=media, user=user)


def start_server(args: argparse.Namespace, dirs: ServerDirs, name: str, fork_web: bool | None = None) -> None:
    """Start de officiële image als 568 (of de huidige gebruiker), zonder capabilities, alleen op 127.0.0.1.

    fork_web=True mount de fork-build over de ingebouwde webclient; False laat de stock-webclient van de image staan.
    """
    if fork_web is None:
        fork_web = args.mode == "fork"
    cmd = [
        "run", "-d", "--name", name, "--user", dirs.user, "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "-p", f"127.0.0.1:{args.port}:8096",
        "-v", f"{dirs.config}:/config", "-v", f"{dirs.cache}:/cache", "-v", f"{dirs.media}:{LIBRARY_PATH}:ro",
    ]
    if fork_web:
        cmd += ["-v", f"{args.dist.resolve()}:{WEB_DIR_IN_IMAGE}:ro"]
    cmd.append(args.image)
    docker(*cmd)


def stop_server(name: str) -> None:
    docker("rm", "-f", name, check=False)


def wait_healthy(api: Api, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        status, body = api.raw_get("/health")
        if status == 200 and body.strip() == b"Healthy":
            return True
        time.sleep(2)
    return False


# --------------------------------------------------------------------------------------------- API-deel

def api_phase(api: Api, args: argparse.Namespace, report: Report, creds: dict) -> dict | None:
    if not report.add("server gezond", wait_healthy(api, args.start_timeout), "GET /health → Healthy"):
        return None
    status, info = api.json("GET", "/System/Info/Public")
    info = info if isinstance(info, dict) else {}
    report.facts["server_productnaam"] = info.get("ProductName")
    report.facts["server_versie"] = info.get("Version")
    report.add(
        "technische identiteit ongewijzigd",
        status == 200 and info.get("ProductName") == "Jellyfin Server" and info.get("Version") == args.expected_version,
        f"ProductName={info.get('ProductName')!r}, Version={info.get('Version')!r} (verwacht {args.expected_version})",
    )
    status, index_html = api.raw_get("/web/index.html")
    if args.mode == "fork":
        expected = (args.dist / "index.html").read_bytes()
        same = status == 200 and index_html == expected
        report.add("fork-build wordt geserveerd", same, f"HTTP {status}; /web/index.html {'=' if same else '≠'} dist/index.html")
    else:
        report.add("stock-webclient wordt geserveerd", status == 200 and b"<html" in index_html.lower(), f"HTTP {status}")
    report.facts["web_index_sha256"] = hashlib.sha256(index_html).hexdigest()
    m_status, manifest = api.json("GET", "/web/manifest.json")
    manifest_name = manifest.get("name") if isinstance(manifest, dict) else None
    title_ok = b"<title>Jellyfin</title>" in index_html
    report.add("zichtbare naam in P0 ongewijzigd ('Jellyfin', ADR-0003)", title_ok and manifest_name == "Jellyfin",
               f"index.html <title>Jellyfin</title> {'aanwezig' if title_ok else 'ontbreekt'}; "
               f"manifest.json name={manifest_name!r} (HTTP {m_status})")

    wizard = [
        ("POST", "/Startup/Configuration", {"UICulture": "nl", "MetadataCountryCode": "NL", "PreferredMetadataLanguage": "nl"}),
        ("GET", "/Startup/User", None),
        ("POST", "/Startup/User", {"Name": creds["admin_user"], "Password": creds["admin_password"]}),
        ("POST", "/Startup/RemoteAccess", {"EnableRemoteAccess": False, "EnableAutomaticPortMapping": False}),
        ("POST", "/Startup/Complete", None),
    ]
    codes = [api.request(method, path, body=body)[0] for method, path, body in wizard]
    if not report.add("eerste-startwizard (API)", all(c in (200, 204) for c in codes), f"HTTP {codes}"):
        return None

    status, auth = api.json("POST", "/Users/AuthenticateByName",
                            body={"Username": creds["admin_user"], "Pw": creds["admin_password"]})
    token = auth.get("AccessToken") if isinstance(auth, dict) else None
    if token:
        report.secrets.append(token)
    if not report.add("beheerder logt in via API", status == 200 and bool(token), f"HTTP {status}"):
        return None
    admin_id = auth["User"]["Id"]
    server_id = auth.get("ServerId", "")

    query = urllib.parse.urlencode({"name": "Muziek", "collectionType": "music", "paths": LIBRARY_PATH, "refreshLibrary": "true"})
    status, _ = api.request("POST", f"/Library/VirtualFolders?{query}", token=token, body={"LibraryOptions": {}})
    report.add("bibliotheek 'Muziek' aanmaken", status in (200, 204), f"HTTP {status}")
    item_id = ""
    deadline = time.monotonic() + args.scan_timeout
    while time.monotonic() < deadline and not item_id:
        items_query = urllib.parse.urlencode({"Recursive": "true", "IncludeItemTypes": "Audio", "userId": admin_id})
        status, body = api.json("GET", f"/Items?{items_query}", token=token)
        if status == 200 and isinstance(body, dict) and body.get("Items"):
            item_id = body["Items"][0]["Id"]
            report.facts["testitem_naam"] = body["Items"][0].get("Name")
            break
        api.request("POST", "/Library/Refresh", token=token)
        time.sleep(3)
    if not report.add("bibliotheekscan vindt het testnummer", bool(item_id), f"item {item_id or 'niet gevonden'}"):
        return None

    status, kid = api.json("POST", "/Users/New", token=token, body={"Name": creds["kid_user"], "Password": creds["kid_password"]})
    kid_id = kid.get("Id") if isinstance(kid, dict) else None
    policy = dict(kid.get("Policy") or {}) if isinstance(kid, dict) else {}
    policy.update({"EnableAllFolders": False, "EnabledFolders": [], "IsAdministrator": False})
    pstatus = api.request("POST", f"/Users/{kid_id}/Policy", token=token, body=policy)[0] if kid_id else 0
    report.add("kinderprofiel zonder bibliotheektoegang", status == 200 and pstatus in (200, 204),
               f"aanmaken HTTP {status}, beleid HTTP {pstatus} (EnableAllFolders=false)")

    status, kid_auth = api.json("POST", "/Users/AuthenticateByName", device_id="jlw-web-smoke-kind",
                                body={"Username": creds["kid_user"], "Pw": creds["kid_password"]})
    kid_token = kid_auth.get("AccessToken") if isinstance(kid_auth, dict) else None
    if kid_token:
        report.secrets.append(kid_token)
    search = urllib.parse.urlencode({"searchTerm": "Sinus", "Recursive": "true", "IncludeItemTypes": "Audio"})
    a_status, a_body = api.json("GET", f"/Items?{search}&userId={admin_id}", token=token)
    k_status, k_body = api.json("GET", f"/Items?{search}&userId={kid_id}", token=kid_token, device_id="jlw-web-smoke-kind")
    a_count = a_body.get("TotalRecordCount") if isinstance(a_body, dict) else None
    k_count = k_body.get("TotalRecordCount") if isinstance(k_body, dict) else None
    report.add("zoeken respecteert server-ACL (API)", a_status == 200 and a_count == 1 and k_status == 200 and k_count == 0,
               f"beheerder {a_count} resultaat, kinderprofiel {k_count} (verwacht 1 / 0)")
    status, _ = api.request("GET", f"/Users/{admin_id}", token=None)
    report.add("zonder token geweigerd", status == 401, f"GET /Users/<id> zonder token → HTTP {status} (verwacht 401)")
    return {"token": token, "admin_id": admin_id, "server_id": server_id, "item_id": item_id, "kid_id": kid_id}


# --------------------------------------------------------------------------------------------- opslag: herstart/terugzetten

def verify_data(api: Api, report: Report, label: str, creds: dict, ids: dict) -> None:
    """Na herstart of terugzetten: zelfde server, zelfde gebruikers/bibliotheek, stream en server-ACL werken nog."""
    status, info = api.json("GET", "/System/Info/Public")
    server_id = info.get("Id") if isinstance(info, dict) else None
    status_a, auth = api.json("POST", "/Users/AuthenticateByName",
                              body={"Username": creds["admin_user"], "Pw": creds["admin_password"]})
    token = auth.get("AccessToken") if isinstance(auth, dict) else None
    if token:
        report.secrets.append(token)
    item_status, item = (api.json("GET", f"/Items/{ids['item_id']}?userId={ids['admin_id']}", token=token)
                         if token else (0, None))
    same_item = item_status == 200 and isinstance(item, dict) and item.get("Id") == ids["item_id"]
    report.add(
        f"{label}: gegevens behouden",
        status == 200 and server_id == ids["server_id"] and status_a == 200 and bool(token) and same_item,
        f"server-ID {'gelijk' if server_id == ids['server_id'] else 'ANDERS'}; beheerder logt in met hetzelfde "
        f"wachtwoord: HTTP {status_a}; testnummer met hetzelfde ID: HTTP {item_status}",
    )
    s_status, body = (api.request("GET", f"/Audio/{ids['item_id']}/stream?static=true", token=token)
                      if token else (0, b""))
    stream_ok = s_status in (200, 206) and body[:4] == b"RIFF" and len(body) > 1000
    kid_status, kid_auth = api.json("POST", "/Users/AuthenticateByName", device_id="jlw-web-smoke-kind",
                                    body={"Username": creds["kid_user"], "Pw": creds["kid_password"]})
    kid_token = kid_auth.get("AccessToken") if isinstance(kid_auth, dict) else None
    if kid_token:
        report.secrets.append(kid_token)
    search = urllib.parse.urlencode({"searchTerm": "Sinus", "Recursive": "true", "IncludeItemTypes": "Audio"})
    k_status, k_body = (api.json("GET", f"/Items?{search}&userId={ids['kid_id']}", token=kid_token,
                                 device_id="jlw-web-smoke-kind") if kid_token else (0, None))
    k_count = k_body.get("TotalRecordCount") if isinstance(k_body, dict) else None
    report.add(
        f"{label}: stream en server-ACL werken",
        stream_ok and kid_status == 200 and k_status == 200 and k_count == 0,
        f"GET /Audio/<id>/stream → HTTP {s_status}, {len(body)} bytes; kinderprofiel logt in (HTTP {kid_status}) "
        f"en vindt {k_count} resultaten (verwacht 0)",
    )


def served_web(api: Api, args: argparse.Namespace, fork_web: bool) -> tuple[bool, str]:
    status, index_html = api.raw_get("/web/index.html")
    title_ok = b"<title>Jellyfin</title>" in index_html
    if fork_web:
        same = status == 200 and index_html == (args.dist / "index.html").read_bytes()
        return same and title_ok, f"HTTP {status}; fork-build {'geserveerd' if same else 'NIET geserveerd'}"
    is_fork = args.mode == "fork" and index_html == (args.dist / "index.html").read_bytes()
    ok = status == 200 and title_ok and not is_fork
    return ok, f"HTTP {status}; stock-webclient van de image {'geserveerd' if ok else 'NIET geserveerd'}"


def persistence_phase(api: Api, args: argparse.Namespace, report: Report, creds: dict, ids: dict,
                      dirs: ServerDirs, container: str) -> None:
    stages: list[tuple[str, bool | None]] = [("herstart", None)]
    if args.mode == "fork":
        stages += [("terugzetten naar stock-webclient (zelfde /config)", False),
                   ("weer vooruit naar de fork-build (zelfde /config)", True)]
    for label, fork_web in stages:
        if fork_web is None:
            docker("restart", "-t", "20", container)
            fork_web_now = args.mode == "fork"
        else:
            docker("rm", "-f", container)
            start_server(args, dirs, container, fork_web=fork_web)
            fork_web_now = fork_web
        healthy = wait_healthy(api, args.start_timeout)
        served_ok, detail = served_web(api, args, fork_web_now) if healthy else (False, "server niet gezond")
        if not report.add(f"{label}: server gezond, juiste webclient", healthy and served_ok, detail):
            return
        verify_data(api, report, label, creds, ids)


# --------------------------------------------------------------------------------------------- browserdeel

def wait_for_login_form(page, timeout_s: float = 60.0) -> None:
    """Wacht tot het handmatige aanmeldformulier stabiel zichtbaar is.

    Met verborgen gebruikers toont upstream direct het handmatige formulier, anders eerst gebruikerskaarten met de
    knop 'Handmatig aanmelden'. Tijdens het laden van de pagina wisselt de zichtbaarheid kort; daarom pas verder als
    het veld drie keer achter elkaar (1,5 s) zichtbaar is.
    """
    from playwright.sync_api import Error as PlaywrightError

    deadline = time.monotonic() + timeout_s
    stable = 0
    while time.monotonic() < deadline:
        if page.locator("#txtManualName").is_visible():
            stable += 1
            if stable >= 3:
                return
        else:
            stable = 0
            button = page.locator(".btnManual:visible")
            if button.count() > 0:
                try:
                    button.first.click(timeout=2000)
                except PlaywrightError:
                    pass
        time.sleep(0.5)
    raise RuntimeError("het aanmeldformulier verschijnt niet binnen de tijd")


def ui_login(page, base: str, user: str, password: str) -> None:
    page.goto(f"{base}/web/", wait_until="domcontentloaded")
    wait_for_login_form(page)
    page.locator("#txtManualName").fill(user)
    page.locator("#txtManualPassword").fill(password)
    page.locator(".manualLoginForm .button-submit").click()


def has_no_horizontal_overflow(page) -> tuple[bool, str]:
    width = page.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
    return width[0] <= width[1] + 1, f"scrollWidth {width[0]} px, venster {width[1]} px"


def shot(page, out: Path | None, name: str, kind: str) -> str:
    if out is None or kind == "geen":
        return ""
    path = out / f"{name}.{'jpg' if kind == 'jpeg' else 'png'}"
    if kind == "jpeg":
        page.screenshot(path=str(path), type="jpeg", quality=60, full_page=False)
    else:
        page.screenshot(path=str(path), full_page=False)
    return path.name


def ui_phase(base: str, args: argparse.Namespace, report: Report, creds: dict, ids: dict) -> None:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    out = args.output
    with sync_playwright() as pw:
        launch = {"executable_path": args.chromium} if args.chromium else {}
        browser = pw.chromium.launch(**launch)
        report.facts["browser"] = f"Chromium {browser.version} (headless)"
        try:
            context = browser.new_context(locale="nl-NL", viewport={"width": 1440, "height": 900})
            page = context.new_page()
            page.set_default_timeout(30000)

            page.goto(f"{base}/web/", wait_until="domcontentloaded")
            wait_for_login_form(page)
            dutch = [text for text in ("Meld je aan", "Aanmelden", "Gebruiker", "Wachtwoord")
                     if page.get_by_text(text, exact=True).count() > 0]
            report.add("aanmeldpagina in het Nederlands (browser nl-NL)", len(dutch) >= 3,
                       f"gevonden: {', '.join(dutch) or 'geen'}")
            shot(page, out, f"{args.mode}-1440-aanmelden", args.screenshots)

            ui_login(page, base, creds["admin_user"], creds["admin_password"] + "-fout")
            toast = page.get_by_text("Ongeldige gebruikersnaam of wachtwoord", exact=False)
            try:
                toast.first.wait_for(state="visible", timeout=15000)
                rejected = "#/home" not in page.url
            except PlaywrightError:
                rejected = False
            report.add("fout wachtwoord geweigerd (negatieve test)", rejected, f"melding zichtbaar, url {page.url.split('#')[-1]}")

            ui_login(page, base, creds["admin_user"], creds["admin_password"])
            page.wait_for_selector("#indexPage:not(.hide)", timeout=60000)
            library = page.locator("#indexPage").get_by_text("Muziek", exact=True)
            try:
                library.first.wait_for(state="visible", timeout=30000)
                home_ok = True
            except PlaywrightError:
                home_ok = False
            report.add("inloggen → startscherm met bibliotheek", home_ok, f"url {page.url.split('#')[-1]}")
            shot(page, out, f"{args.mode}-1440-startscherm", args.screenshots)
            state = context.storage_state()

            page.goto(f"{base}/web/#/search?query=Sinus", wait_until="domcontentloaded")
            try:
                page.locator(".searchResults").get_by_text(TRACK_NAME).first.wait_for(state="visible", timeout=30000)
                found = True
            except PlaywrightError:
                found = False
            report.add("zoeken vindt het testnummer (UI)", found, f"zoekterm 'Sinus' → {TRACK_NAME!r}")
            shot(page, out, f"{args.mode}-1440-zoeken", args.screenshots)

            item_id = ids["item_id"]
            page.goto(f"{base}/web/#/details?id={item_id}&serverId={ids['server_id']}", wait_until="domcontentloaded")
            play = page.locator("button.btnPlay:not(.hide)").first
            stream_status = 0
            try:
                play.wait_for(state="visible", timeout=30000)
                with page.expect_response(lambda r: f"/Audio/{item_id}/" in r.url, timeout=30000) as resp_info:
                    play.click()
                stream_status = resp_info.value.status
            except PlaywrightError as exc:
                report.facts["afspelen_fout"] = str(exc).splitlines()[0][:200]
            report.add("afspelen start een stream", stream_status in (200, 206),
                       f"GET /Audio/<id>/… → HTTP {stream_status} (verwacht 200/206)")
            context.close()

            kid_context = browser.new_context(locale="nl-NL", viewport={"width": 1440, "height": 900})
            kid_page = kid_context.new_page()
            kid_page.set_default_timeout(30000)
            ui_login(kid_page, base, creds["kid_user"], creds["kid_password"])
            kid_page.wait_for_selector("#indexPage:not(.hide)", timeout=60000)
            kid_page.goto(f"{base}/web/#/search?query=Sinus", wait_until="domcontentloaded")
            try:
                kid_page.get_by_text("Geen resultaten gevonden", exact=False).first.wait_for(state="visible", timeout=30000)
                hidden = kid_page.locator(".searchResults").get_by_text(TRACK_NAME).count() == 0
            except PlaywrightError:
                hidden = False
            report.add("kinderprofiel ziet de titel niet in zoekresultaten (UI)", hidden,
                       "melding 'Geen resultaten gevonden', geen testnummer zichtbaar")
            shot(kid_page, out, f"{args.mode}-1440-kind-zoeken", args.screenshots)
            kid_context.close()

            for width, height in VIEWPORTS:
                mobile = width < 768
                ctx = browser.new_context(locale="nl-NL", viewport={"width": width, "height": height},
                                          is_mobile=mobile, has_touch=mobile, storage_state=state)
                vpage = ctx.new_page()
                vpage.set_default_timeout(30000)
                vpage.goto(f"{base}/web/#/home", wait_until="domcontentloaded")
                try:
                    vpage.locator("#indexPage:not(.hide)").get_by_text("Muziek", exact=True).first.wait_for(
                        state="visible", timeout=45000
                    )
                    rendered = True
                except PlaywrightError:
                    rendered = False
                no_overflow, detail = has_no_horizontal_overflow(vpage)
                name = shot(vpage, out, f"{args.mode}-{width}-startscherm", args.screenshots)
                report.add(f"startscherm {width}px zonder horizontale overloop", rendered and no_overflow,
                           f"{detail}{'; ' + name if name else ''}")
                ctx.close()
        finally:
            browser.close()


# --------------------------------------------------------------------------------------------- hoofdprogramma

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Web-client-smoketest (headless Chromium, officiële serverimage).")
    parser.add_argument("--modus", dest="mode", choices=("fork", "stock"), default="fork")
    parser.add_argument("--dist", type=Path, default=REPO_ROOT / "dist", help="productiebuild (modus fork)")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--poort", dest="port", type=int, default=38097)
    parser.add_argument("--url", help="server draait al op deze URL (geen docker starten)")
    parser.add_argument("--verwachte-versie", dest="expected_version", default=None,
                        help="standaard: upstream_version uit tools/jelly-leon-web/baseline.json")
    parser.add_argument("--uitvoer", dest="output", type=Path, default=None, help="map voor rapport en schermafbeeldingen")
    parser.add_argument("--schermafbeeldingen", dest="screenshots", choices=("jpeg", "png", "geen"), default="jpeg")
    parser.add_argument("--chromium", default=os.environ.get("JLW_CHROMIUM") or None, help="pad naar Chromium (optioneel)")
    parser.add_argument("--start-timeout", type=float, default=180.0)
    parser.add_argument("--scan-timeout", type=float, default=120.0)
    parser.add_argument("--houd-server", dest="keep", action="store_true", help="container na afloop laten staan")
    parser.add_argument("--zonder-herstart", dest="skip_restart", action="store_true",
                        help="herstart-/terugzetcontroles overslaan (sneller; niet in CI)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.expected_version is None:
        baseline = json.loads((REPO_ROOT / "tools/jelly-leon-web/baseline.json").read_text(encoding="utf-8"))
        args.expected_version = baseline["upstream_version"]
    if args.mode == "fork" and not args.url and not (args.dist / "index.html").is_file():
        print(f"FOUT: {args.dist}/index.html ontbreekt; draai eerst npm run build:production", file=sys.stderr)
        return 3
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
    creds = {
        "admin_user": "jl-beheer",
        "admin_password": secrets.token_urlsafe(18),
        "kid_user": "jl-kind",
        "kid_password": secrets.token_urlsafe(18),
    }
    base = args.url or f"http://127.0.0.1:{args.port}"
    report = Report(mode=args.mode, base_url=base, image=args.image if not args.url else "extern")
    report.secrets += [creds["admin_password"], creds["kid_password"]]
    if args.mode == "fork" and (args.dist / "index.html").is_file():
        report.facts["dist_index_sha256"] = hashlib.sha256((args.dist / "index.html").read_bytes()).hexdigest()
        report.facts["dist_bestanden"] = sum(1 for p in args.dist.rglob("*") if p.is_file())

    container = f"jlw-web-smoke-{args.mode}-{os.getpid()}"
    work = Path(tempfile.mkdtemp(prefix="jlw-web-smoke-"))
    exit_code = 0
    dirs: ServerDirs | None = None
    try:
        if not args.url:
            try:
                dirs = prepare_dirs(work)
                start_server(args, dirs, container)
            except (RuntimeError, FileNotFoundError) as exc:
                print(f"FOUT: server starten mislukt: {exc}", file=sys.stderr)
                report.add("server starten", False, f"{type(exc).__name__}: {exc}")
                exit_code = 3
        api = Api(base)
        ids = api_phase(api, args, report, creds) if not exit_code else None
        if ids:
            try:
                ui_phase(base, args, report, creds, ids)
            except ImportError:
                print("FOUT: playwright ontbreekt (pip install -r tools/jelly-leon-web/requirements-dev.txt)", file=sys.stderr)
                report.add("browserdeel uitgevoerd", False, "playwright ontbreekt: browserstappen niet uitgevoerd")
                exit_code = 3
            except Exception as exc:  # noqa: BLE001 - elke browserfout is een mislukte stap, nooit een stille pass
                report.add("browserdeel zonder onverwachte fout", False, f"{type(exc).__name__}: {str(exc).splitlines()[0][:300]}")
        if ids and dirs is not None and not args.skip_restart:
            try:
                persistence_phase(api, args, report, creds, ids, dirs, container)
            except RuntimeError as exc:
                report.add("herstart/terugzetten zonder onverwachte fout", False, str(exc)[:300])
        if not report.passed and not args.url:
            logs = docker("logs", "--tail", "60", container, check=False)
            report.facts["serverlog_staart"] = report.redact((logs.stdout + logs.stderr)[-4000:])
    finally:
        if not args.url and not args.keep:
            stop_server(container)
        shutil.rmtree(work, ignore_errors=True)
    result = report.to_json()
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        (args.output / f"web-smoke-{args.mode}.json").write_text(text + "\n", encoding="utf-8")
    print(f"Resultaat {args.mode}: {result['resultaat']} ({result['geslaagd']}/{result['aantal_stappen']} stappen)")
    if exit_code:
        return exit_code
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
