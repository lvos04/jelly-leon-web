#!/usr/bin/env python3
"""Upgradeproef 10.11.11 → 12.x met behoud van kijkgegevens (JLT-60/JLT-61 webdeel; simulator, geen NAS).

HARDE EIS van de gebruiker (B03 §10.9): alle kijkgeschiedenis — gezien-status (met aantal en datum), hervatpunten,
favorieten, beoordelingen, onthouden taal-/ondertitelvoorkeuren, gebruikers en rechten — blijft behouden. Deze proef
toont dat voor een gevulde 10.11.11-datamap met de officiële images, en dat de Jelly Leon-webclient (fork-build)
daarna in beide layouts werkt:

  1. oude server (stock 10.11.11, digest) + eerste-startwizard, bibliotheek en vijf gebruikers: beheerder, kind (geen
     toegang), gast, tiener (leeftijdsgrens en geblokkeerde tag) en ouder; kijkgegevens via de officiële API:
     beheerder 2× gezien + favoriet + beoordeling, gast hervatpunt + voorkeuren, tiener gezien, ouder favoriet;
  2. VÓÓR-rapport per gebruiker (genormaliseerd, sha256); server stoppen; kopie van /config (= snapshot);
  3. nieuwe server (12.x, digest) met de fork-build op dezelfde /config → migraties; NA-rapport; elk verschil is
     een mislukte stap (geen stil verlies; een verklaard verschil zou akkoord van de gebruiker vragen, §10.9);
  4. browser (fork-build) in Modern en Legacy op de gemigreerde data: inloggen met hetzelfde wachtwoord, zoeken,
     detailpagina, afspelen, kinderprofiel ziet niets (stappen uit web_smoke.py), en de gast krijgt op de detailpagina
     "Hervatten" aangeboden (hervatpunt bewaard) en hervat na een klik op het juiste punt (de webclient meldt de start
     met PositionTicks = het hervatpunt, JLT-60 "clients hervatten op het juiste punt");
  5. terugzetten (JLT-61 a): oude image + de kopie van vóór de migratie → jellyfin.db byte-gelijk aan vóór, gezond,
     kijkgegevens = VÓÓR, stream 200;
  6. negatieve proef (JLT-61 b): alleen de oude image op de gemigreerde /config. De acceptatie eist "faalt zichtbaar
     en zonder stille schade". Met `--negatief-verwacht weigert` (standaard) slaagt de stap alleen als de oude image
     niet gezond wordt; met `--negatief-verwacht start` wordt het (in 10.11.11 gemeten) upstream-gedrag vastgelegd:
     de oude image start wél — dan moet er in elk geval geen stille schade zijn: kijkgegevens via de oude API = VÓÓR
     en daarna opnieuw 12.x op dezelfde map = VÓÓR. Een downgradeweigering hoort in de jelly-leon-image (ADR-0011 in
     jelly-leon §4); tot die er is, is JLT-61 (b) met stock-images Sim-mislukt.

Emby blijft hier buiten beschouwing: de overname vanuit Emby (B03-015 deel A, JLT-70…74) hoort bij lvos04/jelly-leon.
Wachtwoorden worden per run gemaakt en nooit gerapporteerd; tokens worden geredigeerd.
Exitcodes: 0 = alle stappen geslaagd, 1 = minstens één stap mislukt, 3 = omgevingsfout.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import secrets
import shutil
import sys
import tempfile
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import web_smoke  # noqa: E402
from web_smoke import Api, Report, docker  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
OLD_IMAGE = (
    "docker.io/jellyfin/jellyfin:10.11.11@sha256:aefb67e6a7ff1debdd154a78a7bbb780fd0c873d8639210a7f6a2016ad2b35db"
)
GUEST = "jl-gast"
TEEN = "jl-tiener"
PARENT = "jl-ouder"
TEEN_POLICY = {"MaxParentalRating": 13, "BlockedTags": ["horror"]}
TICKS_PER_SECOND = 10_000_000
# Kijkgegevens die de proef zet en daarna exact terug moet vinden (HARDE EIS, §10.9).
ADMIN_DATA = {"Played": True, "PlayCount": 2, "IsFavorite": True, "Rating": 8.0,
              "LastPlayedDate": "2026-11-01T20:15:00.0000000Z"}
GUEST_DATA = {"Played": False, "PlaybackPositionTicks": 1 * TICKS_PER_SECOND, "IsFavorite": False}
GUEST_PREFS = {"AudioLanguagePreference": "nld", "SubtitleLanguagePreference": "nld", "SubtitleMode": "Always",
               "RememberAudioSelections": True, "RememberSubtitleSelections": True}
USERDATA_FIELDS = ("Played", "PlayCount", "PlaybackPositionTicks", "IsFavorite", "Rating", "LastPlayedDate")
POLICY_FIELDS = ("IsAdministrator", "IsDisabled", "EnableAllFolders", "EnabledFolders", "MaxParentalRating",
                 "BlockedTags", "EnableContentDownloading", "EnableRemoteAccess")
CONFIG_FIELDS = tuple(GUEST_PREFS)


def iso_seconds(value: object) -> object:
    """Datums vergelijken op de seconde in UTC (12.x schrijft soms een andere notatie van hetzelfde moment)."""
    if not isinstance(value, str) or not value:
        return value
    text = value.rstrip("Z")
    if "." in text:
        text = text.split(".")[0]
    try:
        moment = datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
    except ValueError:
        return value
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalise_userdata(data: dict) -> dict:
    out = {}
    for key in USERDATA_FIELDS:
        value = data.get(key)
        if key == "LastPlayedDate":
            value = iso_seconds(value)
        if key == "Rating" and isinstance(value, (int, float)):
            value = float(value)
        out[key] = value
    return out


def snapshot(api: Api, token: str) -> dict:
    """Per gebruiker (op naam): beleid, voorkeuren en kijkgegevens per item (op pad), alleen via de officiële API."""
    status, users = api.json("GET", "/Users", token=token)
    if status != 200 or not isinstance(users, list):
        raise RuntimeError(f"gebruikerslijst niet leesbaar (HTTP {status})")
    status, items = api.json("GET", "/Items?" + urllib.parse.urlencode(
        {"Recursive": "true", "IncludeItemTypes": "Audio", "Fields": "Path"}), token=token)
    items = items.get("Items", []) if isinstance(items, dict) else []
    result: dict = {"gebruikers": {}, "items": sorted(i.get("Path", "") for i in items)}
    for user in sorted(users, key=lambda u: u["Name"]):
        policy = user.get("Policy") or {}
        config = user.get("Configuration") or {}
        entry = {
            "beleid": {k: policy.get(k) for k in POLICY_FIELDS},
            "voorkeuren": {k: config.get(k) for k in CONFIG_FIELDS},
            "kijkgegevens": {},
        }
        for item in items:
            s, data = api.json("GET", f"/UserItems/{item['Id']}/UserData?userId={user['Id']}", token=token)
            entry["kijkgegevens"][item.get("Path", item["Id"])] = (
                normalise_userdata(data) if s == 200 and isinstance(data, dict) else {"fout": f"HTTP {s}"}
            )
        result["gebruikers"][user["Name"]] = entry
    for entry in result["gebruikers"].values():
        if isinstance(entry["beleid"].get("EnabledFolders"), list):
            entry["beleid"]["EnabledFolders"] = sorted(entry["beleid"]["EnabledFolders"])
        if isinstance(entry["beleid"].get("BlockedTags"), list):
            entry["beleid"]["BlockedTags"] = sorted(entry["beleid"]["BlockedTags"])
    return result


def digest(data: object) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def differences(before: dict, after: dict, path: str = "") -> list[str]:
    """Alle verschillen als leesbare regels (lege lijst = identiek)."""
    if isinstance(before, dict) and isinstance(after, dict):
        found = []
        for key in sorted(set(before) | set(after)):
            where = f"{path}/{key}" if path else str(key)
            if key not in before:
                found.append(f"{where}: nieuw na de upgrade ({after[key]!r})")
            elif key not in after:
                found.append(f"{where}: VERDWENEN na de upgrade (was {before[key]!r})")
            else:
                found += differences(before[key], after[key], where)
        return found
    return [] if before == after else [f"{path}: {before!r} → {after!r}"]


def login(api: Api, user: str, password: str, report: Report) -> tuple[str | None, dict]:
    status, auth = api.json("POST", "/Users/AuthenticateByName", body={"Username": user, "Pw": password})
    token = auth.get("AccessToken") if isinstance(auth, dict) else None
    if token:
        report.secrets.append(token)
    return token, (auth if isinstance(auth, dict) else {})


def seed_viewing_data(api: Api, report: Report, creds: dict, ids: dict) -> bool:
    """Gast, tiener en ouder aanmaken en kijkgegevens zetten via de officiële API (zoals echte gebruikers)."""
    token, item = ids["token"], ids["item_id"]
    codes: list[int] = []
    created: dict[str, str | None] = {}
    for name in (GUEST, TEEN, PARENT):
        status, user = api.json("POST", "/Users/New", token=token, body={"Name": name, "Password": creds["guest_password"]})
        codes.append(status)
        created[name] = user.get("Id") if isinstance(user, dict) else None
        if name == GUEST and created[name]:
            config = dict(user.get("Configuration") or {}, **GUEST_PREFS)
            codes.append(api.request("POST", f"/Users/{created[name]}/Configuration", token=token, body=config)[0])
        if name == TEEN and created[name]:
            policy = dict(user.get("Policy") or {}, **TEEN_POLICY)
            codes.append(api.request("POST", f"/Users/{created[name]}/Policy", token=token, body=policy)[0])
    data = {GUEST: GUEST_DATA, TEEN: {"Played": True, "PlayCount": 1, "LastPlayedDate": "2026-10-30T19:00:00.0000000Z"},
            PARENT: {"IsFavorite": True}}
    for name, body in data.items():
        if created.get(name):
            codes.append(api.request("POST", f"/UserItems/{item}/UserData?userId={created[name]}", token=token, body=body)[0])
    codes.append(api.request("POST", f"/UserItems/{item}/UserData?userId={ids['admin_id']}", token=token,
                             body=ADMIN_DATA)[0])
    ids["guest_id"] = created.get(GUEST)
    return report.add("kijkgegevens gezet via de officiële API (oude server, 5 gebruikers)",
                      all(created.values()) and all(c in (200, 204) for c in codes),
                      f"HTTP {codes}: beheerder 2× gezien + favoriet + beoordeling 8; gast hervatpunt 1 s + taal-/"
                      "ondertitelvoorkeuren nld; tiener gezien + leeftijdsgrens 13 + tag 'horror' geblokkeerd; ouder favoriet")


def expected_present(snap: dict, report: Report, label: str) -> None:
    """De gezette waarden staan er echt in (anders vergelijkt de proef niets)."""
    users = snap["gebruikers"]
    admin = next(iter(users.get("jl-beheer", {}).get("kijkgegevens", {}).values()), {})
    guest = next(iter(users.get(GUEST, {}).get("kijkgegevens", {}).values()), {})
    prefs = users.get(GUEST, {}).get("voorkeuren", {})
    ok = (admin.get("Played") is True and admin.get("PlayCount") == 2 and admin.get("IsFavorite") is True
          and admin.get("Rating") == 8.0 and admin.get("LastPlayedDate") == "2026-11-01T20:15:00Z"
          and guest.get("PlaybackPositionTicks") == GUEST_DATA["PlaybackPositionTicks"]
          and all(prefs.get(k) == v for k, v in GUEST_PREFS.items())
          and users.get("jl-kind", {}).get("beleid", {}).get("EnableAllFolders") is False
          and len(users) == 5
          and users.get(TEEN, {}).get("beleid", {}).get("BlockedTags") == TEEN_POLICY["BlockedTags"]
          and users.get(TEEN, {}).get("beleid", {}).get("MaxParentalRating") is not None)
    report.add(f"{label}: gezette kijkgegevens aanwezig", ok,
               f"beheerder {admin}; gast hervatpunt {guest.get('PlaybackPositionTicks')} ticks; voorkeuren {prefs}")


def is_playback_start(method: str, url: str) -> bool:
    """POST /Sessions/Playing = reportPlaybackStart van de webclient (niet …/Progress of …/Stopped)."""
    return method == "POST" and urllib.parse.urlsplit(url).path.rstrip("/").endswith("/Sessions/Playing")


def start_position_ok(start_ticks: object, expected_ticks: int) -> bool:
    """De webclient begint op het bewaarde hervatpunt (marge 0,25 s voor afronding van currentTime), niet bij 0."""
    if isinstance(start_ticks, bool) or not isinstance(start_ticks, (int, float)):
        return False
    return abs(start_ticks - expected_ticks) <= TICKS_PER_SECOND // 4


def resume_check(base: str, args: argparse.Namespace, report: Report, creds: dict, ids: dict, layout: str) -> None:
    """De gast krijgt na de upgrade op de detailpagina "Hervatten" en de webclient hervat op het juiste punt.

    JLT-60 eist "clients hervatten op het juiste punt": na een klik op Hervatten meldt de webclient de start van het
    afspelen (POST /Sessions/Playing) met PositionTicks = het bewaarde hervatpunt (1 s), niet 0. De afspeelmeldingen
    worden onderschept en niet naar de server gestuurd (web_smoke.new_context): de proef zelf verandert zo de
    kijkgegevens niet, en de tweede layout en de negatieve proef zien nog exact de stand van VÓÓR.
    """
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    tag = f"[{layout.capitalize()}]"
    expected = GUEST_DATA["PlaybackPositionTicks"]
    starts: list[object] = []

    def on_report(request) -> None:
        if is_playback_start(request.method, request.url):
            try:
                starts.append(request.post_data_json)
            except (ValueError, TypeError):
                starts.append(None)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(**({"executable_path": args.chromium} if args.chromium else {}))
        try:
            context = web_smoke.new_context(browser, layout, viewport={"width": 1440, "height": 900},
                                            block_playback_reports=True, on_report=on_report)
            page = context.new_page()
            page.set_default_timeout(30000)
            web_smoke.ui_login(page, base, GUEST, creds["guest_password"])
            page.wait_for_selector("#indexPage:not(.hide)", timeout=60000)
            page.goto(f"{base}/web/#/details?id={ids['item_id']}&serverId={ids['server_id']}", wait_until="domcontentloaded")
            play = page.locator("button.btnPlay:not(.hide)").first
            try:
                page.locator("button.btnReplay:not(.hide)").first.wait_for(state="visible", timeout=30000)
                title = play.get_attribute("title")
                ok = title == "Hervatten"
            except PlaywrightError as exc:
                title, ok = f"fout: {str(exc).splitlines()[0][:120]}", False
            report.add(f"{tag} gast krijgt 'Hervatten' op de detailpagina (hervatpunt bewaard)", ok,
                       f"knop 'opnieuw afspelen' zichtbaar; afspeelknop-titel {title!r} (verwacht 'Hervatten')")

            start_ticks: object = None
            detail = ""
            if ok:
                try:
                    play.click()
                    deadline = time.monotonic() + 30
                    while not starts and time.monotonic() < deadline:
                        page.wait_for_timeout(250)
                    body = starts[0] if starts else None
                    start_ticks = body.get("PositionTicks") if isinstance(body, dict) else None
                    if not starts:
                        detail = "; geen afspeelstart gemeld binnen 30 s"
                except PlaywrightError as exc:
                    detail = f"; fout: {str(exc).splitlines()[0][:120]}"
            report.add(f"{tag} gast hervat op het juiste punt (webclient start op het hervatpunt)",
                       start_position_ok(start_ticks, expected),
                       f"POST /Sessions/Playing PositionTicks={start_ticks!r} (verwacht {expected} ± "
                       f"{TICKS_PER_SECOND // 4}){detail}")
            context.close()
        finally:
            browser.close()


def negative_phase(api: Api, args: argparse.Namespace, report: Report, creds: dict, dirs, container: str,
                   old: argparse.Namespace, new: argparse.Namespace, before: dict, extra: dict) -> None:
    """JLT-61 (b): alleen de oude image op de gemigreerde /config; bruikbaarheid en blijvende schade meten."""
    web_smoke.start_server(old, dirs, container, fork_web=False)
    old_healthy = web_smoke.wait_healthy(api, args.negative_timeout)
    state = docker("inspect", "-f", "{{.State.Status}} {{.State.ExitCode}}", container, check=False).stdout.strip()
    measured: dict = {"gezond": old_healthy, "container": state, "aanmelden_http": None, "leesbaar": False,
                      "verschillen_via_oude_api": []}
    if old_healthy:
        status, auth = api.json("POST", "/Users/AuthenticateByName",
                                body={"Username": creds["admin_user"], "Pw": creds["admin_password"]})
        measured["aanmelden_http"] = status
        token = auth.get("AccessToken") if isinstance(auth, dict) else None
        if token:
            report.secrets.append(token)
            try:
                seen_by_old = snapshot(api, token)
                measured["leesbaar"] = True
                measured["verschillen_via_oude_api"] = differences(before, seen_by_old)
            except RuntimeError as exc:
                measured["leesfout"] = str(exc)
    logs = docker("logs", "--tail", "40", container, check=False)
    extra["negatief_logstaart"] = report.redact((logs.stdout + logs.stderr)[-1500:])
    docker("rm", "-f", container, check=False)

    web_smoke.start_server(new, dirs, container, fork_web=True)
    new_again = web_smoke.wait_healthy(api, args.start_timeout)
    token, _ = login(api, creds["admin_user"], creds["admin_password"], report) if new_again else (None, {})
    again = snapshot(api, token) if token else {}
    persistent = differences(before, again) if again else ["12.x daarna niet leesbaar"]
    docker("rm", "-f", container, check=False)
    # Schade = blijvend verlies (12.x daarna ≠ VÓÓR) of een oude image die andere kijkgegevens toont dan VÓÓR.
    damage = [f"12.x daarna: {d}" for d in persistent] + [f"oude API: {d}" for d in measured["verschillen_via_oude_api"]]
    measured["blijvende_verschillen_12x_daarna"] = persistent
    extra["negatief"] = measured
    if not old_healthy:
        verdict = "Sim-geslaagd: de oude image wordt niet gezond op de gemigreerde data"
    elif not measured["leesbaar"]:
        verdict = (f"Sim-mislukt: de oude stock-image meldt zich gezond maar is onbruikbaar (aanmelden HTTP "
                   f"{measured['aanmelden_http']}), zonder duidelijke melding")
    else:
        verdict = "Sim-mislukt: de oude stock-image start zonder weigering en werkt op de gemigreerde data"
    verdict += "; " + ("geen blijvende schade (12.x daarna = VÓÓR)" if not damage else "MET schade aan de kijkgegevens")
    extra["jlt61b"] = verdict
    if args.negative_expected == "weigert":
        ok = not old_healthy and not damage
        label = "negatief (JLT-61 b): oude image op de gemigreerde /config faalt zichtbaar, zonder stille schade"
    else:
        ok = old_healthy and not damage
        label = ("negatief (JLT-61 b), gemeten upstream-gedrag: oude stock-image start op de gemigreerde /config; "
                 "geen stille schade (12.x daarna = VÓÓR)")
    report.add(label, ok, f"oude image gezond binnen {args.negative_timeout:.0f} s: {old_healthy}; container {state}; "
               f"aanmelden HTTP {measured['aanmelden_http']}; {len(damage)} verschillen"
               f"{': ' + '; '.join(damage[:4]) if damage else ''}; {verdict}")


def run(args: argparse.Namespace) -> tuple[Report, dict, int]:
    creds = {"admin_user": "jl-beheer", "admin_password": secrets.token_urlsafe(18), "kid_user": "jl-kind",
             "kid_password": secrets.token_urlsafe(18), "guest_password": secrets.token_urlsafe(18)}
    base = f"http://127.0.0.1:{args.port}"
    report = Report(mode="upgrade", base_url=base, image=f"{args.old_image} → {args.image}")
    report.secrets += [creds["admin_password"], creds["kid_password"], creds["guest_password"]]
    extra: dict = {}
    work = Path(tempfile.mkdtemp(prefix="jlw-upgrade-"))
    container = f"jlw-upgrade-{os.getpid()}"
    api = Api(base, timeout=30)
    exit_code = 0

    def server_args(image: str, mode: str, version: str) -> argparse.Namespace:
        ns = copy.copy(args)
        ns.image, ns.mode, ns.expected_version = image, mode, version
        return ns

    try:
        dirs = web_smoke.prepare_dirs(work)
        old = server_args(args.old_image, "stock", args.old_version)
        web_smoke.start_server(old, dirs, container, fork_web=False)
        ids = web_smoke.api_phase(api, old, report, creds)
        if not ids or not seed_viewing_data(api, report, creds, ids):
            return report, extra, 1
        before = snapshot(api, ids["token"])
        expected_present(before, report, "VÓÓR (10.11.11)")
        extra["voor"] = before
        extra["voor_sha256"] = digest(before)

        docker("stop", "-t", "30", container)
        docker("rm", "-f", container)
        snapshot_dir = work / "config-kopie"
        shutil.copytree(dirs.config, snapshot_dir, symlinks=True)
        db = dirs.config / "data" / "jellyfin.db"
        extra["jellyfin_db_sha256_voor"] = hashlib.sha256(db.read_bytes()).hexdigest() if db.is_file() else None
        report.add("kopie van /config vóór de migratie (snapshot)", db.is_file(),
                   f"jellyfin.db sha256 {str(extra['jellyfin_db_sha256_voor'])[:16]}…")

        new = server_args(args.image, "fork", args.new_version)
        web_smoke.start_server(new, dirs, container, fork_web=True)
        healthy = web_smoke.wait_healthy(api, args.start_timeout)
        status, info = api.json("GET", "/System/Info/Public")
        version = info.get("Version") if isinstance(info, dict) else None
        if not report.add("nieuwe server migreert dezelfde /config en wordt gezond", healthy and version == args.new_version,
                          f"versie {version!r} (verwacht {args.new_version}); fork-build gemount"):
            return report, extra, 1
        token, auth = login(api, creds["admin_user"], creds["admin_password"], report)
        report.add("beheerder logt na de upgrade in met hetzelfde wachtwoord", bool(token), "HTTP 200" if token else "mislukt")
        if not token:
            return report, extra, 1
        after = snapshot(api, token)
        extra["na"] = after
        extra["na_sha256"] = digest(after)
        diff = differences(before, after)
        extra["verschillen"] = diff
        report.add("NA (12.x) = VÓÓR per gebruiker: gezien, aantal, datum, hervatpunt, favoriet, beoordeling, "
                   "voorkeuren, rechten", not diff,
                   f"sha256 vóór {extra['voor_sha256'][:16]}…, na {extra['na_sha256'][:16]}…; "
                   f"{len(diff)} verschillen{': ' + '; '.join(diff[:5]) if diff else ''}")
        expected_present(after, report, "NA (12.x)")

        ui_ids = dict(ids, token=token, server_id=auth.get("ServerId", ids["server_id"]))
        for layout in args.layouts:
            try:
                # Afspeelmeldingen onderscheppen: afspelen in de browserproef mag de kijkgegevens niet veranderen,
                # anders vergelijkt de negatieve proef hierna niet meer met VÓÓR (zie web_smoke.new_context).
                web_smoke.ui_phase(base, new, report, creds, ui_ids, layout=layout, api=api,
                                   block_playback_reports=True)
            except Exception as exc:  # noqa: BLE001 - elke browserfout is een mislukte stap
                report.add(f"[{layout}] browserdeel zonder onverwachte fout", False, f"{type(exc).__name__}: {exc}"[:300])

        for layout in args.layouts:
            resume_check(base, new, report, creds, ids, layout)
        docker("stop", "-t", "30", container)
        docker("rm", "-f", container)

        kopie_db = snapshot_dir / "data" / "jellyfin.db"
        extra["jellyfin_db_sha256_kopie"] = hashlib.sha256(kopie_db.read_bytes()).hexdigest() if kopie_db.is_file() else None
        fresh_cache = work / "cache-terugzetten"  # de cache van 12.x hoort niet bij het teruggezette pad
        fresh_cache.mkdir()
        os.chmod(fresh_cache, 0o777 if os.geteuid() == 0 else 0o755)
        rollback_dirs = web_smoke.ServerDirs(config=snapshot_dir, cache=fresh_cache, media=dirs.media, user=dirs.user)
        web_smoke.start_server(old, rollback_dirs, container, fork_web=False)
        healthy = web_smoke.wait_healthy(api, args.start_timeout)
        token, _ = login(api, creds["admin_user"], creds["admin_password"], report) if healthy else (None, {})
        restored = snapshot(api, token) if token else {}
        rollback_diff = differences(before, restored) if restored else ["niet leesbaar"]
        extra["terugzetten_verschillen"] = rollback_diff
        s_status, body = (api.request("GET", f"/Audio/{ids['item_id']}/stream?static=true", token=token)
                          if token else (0, b""))
        report.add("terugzetten (JLT-61 a): oude image + kopie van vóór de migratie = VÓÓR, stream speelt",
                   healthy and not rollback_diff and s_status in (200, 206) and body[:4] == b"RIFF"
                   and extra["jellyfin_db_sha256_kopie"] == extra["jellyfin_db_sha256_voor"],
                   f"jellyfin.db van de kopie byte-gelijk aan vóór de migratie: "
                   f"{extra['jellyfin_db_sha256_kopie'] == extra['jellyfin_db_sha256_voor']}; gezond {healthy}; "
                   f"{len(rollback_diff)} verschillen; stream HTTP {s_status}")
        docker("rm", "-f", container, check=False)
        negative_phase(api, args, report, creds, dirs, container, old, new, before, extra)
    except (RuntimeError, OSError) as exc:
        report.add("upgradeproef zonder omgevingsfout", False, f"{type(exc).__name__}: {exc}"[:300])
        exit_code = 3
    finally:
        if not report.passed:
            logs = docker("logs", "--tail", "60", container, check=False)
            extra["serverlog_staart"] = report.redact((logs.stdout + logs.stderr)[-4000:])
        web_smoke.stop_server(container)
        shutil.rmtree(work, ignore_errors=True)
    return report, extra, exit_code


def build_parser() -> argparse.ArgumentParser:
    baseline = json.loads((REPO_ROOT / "tools/jelly-leon-web/baseline.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description="Upgradeproef 10.11.11 → 12.x met behoud van kijkgegevens.")
    parser.add_argument("--oude-image", dest="old_image", default=OLD_IMAGE)
    parser.add_argument("--oude-versie", dest="old_version", default="10.11.11")
    parser.add_argument("--image", default=baseline.get("toolchain", {}).get("server_image", web_smoke.DEFAULT_IMAGE))
    parser.add_argument("--nieuwe-versie", dest="new_version", default=baseline["upstream_version"])
    parser.add_argument("--dist", type=Path, default=REPO_ROOT / "dist")
    parser.add_argument("--poort", dest="port", type=int, default=38098)
    parser.add_argument("--uitvoer", dest="output", type=Path, default=None)
    parser.add_argument("--schermafbeeldingen", dest="screenshots", choices=("jpeg", "png", "geen"), default="geen")
    parser.add_argument("--chromium", default=os.environ.get("JLW_CHROMIUM") or None)
    parser.add_argument("--layouts", default="modern,legacy")
    parser.add_argument("--start-timeout", type=float, default=240.0)
    parser.add_argument("--scan-timeout", type=float, default=120.0)
    parser.add_argument("--negatief-timeout", dest="negative_timeout", type=float, default=90.0)
    parser.add_argument("--negatief-verwacht", dest="negative_expected", choices=("weigert", "start"), default="weigert",
                        help="JLT-61 b: 'weigert' = acceptatie (oude image moet falen); 'start' = gemeten gedrag van de "
                             "stock-images vastleggen (dan alleen: geen stille schade)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.layouts = web_smoke.parse_layouts(args.layouts)
    except ValueError as exc:
        print(f"FOUT: {exc}", file=sys.stderr)
        return 3
    if not (args.dist / "index.html").is_file():
        print(f"FOUT: {args.dist}/index.html ontbreekt; draai eerst npm run build:production", file=sys.stderr)
        return 3
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
    report, extra, exit_code = run(args)
    result = report.to_json()
    result["test"] = "upgradeproef 10.11.11 → 12.x met behoud van kijkgegevens (JLT-60/JLT-61 webdeel)"
    result["validatie"] = "Sim-getest (officiële images op digest + fork-build, headless Chromium; geen NAS, geen echte data)"
    result.update(extra)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        (args.output / "upgrade-proef.json").write_text(text + "\n", encoding="utf-8")
    print(f"Resultaat upgradeproef: {result['resultaat']} ({result['geslaagd']}/{result['aantal_stappen']} stappen)")
    if exit_code:
        return exit_code
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
