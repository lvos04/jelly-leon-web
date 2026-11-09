"""Unit-tests voor e2e/upgrade_proef.py (zonder Docker): vergelijking van kijkgegevens vóór/na (HARDE EIS, §10.9)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "e2e"))

import upgrade_proef  # noqa: E402
import web_smoke  # noqa: E402

ITEM = {"Id": "i1", "Path": "/media/muziek/Jelly Leon Test/Smoketest/01 - Sinus 440 Hz.wav"}


FILM_PATH = f"/media/films/{upgrade_proef.FILM_RELATIVE.as_posix()}"
FILM = {"Id": "f1", "Path": FILM_PATH, "Type": "Movie"}


class FakeApi:
    def __init__(self, userdata: dict, prefs: dict | None = None, tracks: dict | None = None):
        self.userdata = userdata
        self.prefs = prefs or dict(upgrade_proef.GUEST_PREFS)
        self.tracks = tracks  # per gebruiker-ID de spoorkeuze uit PlaybackInfo; None = geen testfilm

    def json(self, method, path, token=None, body=None, **_kwargs):
        assert token
        if path == "/Users":
            return 200, [
                {"Id": "u-g", "Name": upgrade_proef.GUEST, "Policy": {"EnableAllFolders": True, "BlockedTags": ["b", "a"]},
                 "Configuration": self.prefs},
                {"Id": "u-a", "Name": "jl-beheer", "Policy": {"IsAdministrator": True}, "Configuration": {}},
            ]
        if path.startswith("/Items?"):
            assert "Audio%2CMovie" in path  # films (spoorkeuzes) horen in de vergelijking
            return 200, {"Items": [ITEM] + ([FILM] if self.tracks is not None else [])}
        if path.startswith("/UserItems/i1/UserData?userId="):
            return 200, self.userdata[path.rsplit("=", 1)[1]]
        if path.startswith("/UserItems/f1/UserData?userId="):
            return 200, {"Played": False, "PlayCount": 1}
        if path.startswith("/Items/f1/PlaybackInfo?userId="):
            assert method == "POST"
            user_id = path.rsplit("=", 1)[1]
            if user_id not in self.tracks:
                return 404, None
            return 200, {"MediaSources": [dict(self.tracks[user_id], Id="bron", MediaStreams=[])]}
        raise AssertionError(path)


ADMIN = {"Played": True, "PlayCount": 2, "IsFavorite": True, "Rating": 8, "PlaybackPositionTicks": 0,
         "LastPlayedDate": "2026-11-01T20:15:00.0000000Z", "Key": "negeren"}
GUEST = {"Played": False, "PlayCount": 0, "IsFavorite": False, "PlaybackPositionTicks": 10_000_000}


def test_snapshot_normalises_and_ignores_irrelevant_fields():
    snap = upgrade_proef.snapshot(FakeApi({"u-a": ADMIN, "u-g": GUEST}), "tok")
    admin = snap["gebruikers"]["jl-beheer"]["kijkgegevens"][ITEM["Path"]]
    assert admin["LastPlayedDate"] == "2026-11-01T20:15:00Z" and admin["Rating"] == 8.0 and "Key" not in admin
    assert snap["gebruikers"][upgrade_proef.GUEST]["beleid"]["BlockedTags"] == ["a", "b"]
    assert list(snap["gebruikers"]) == sorted(snap["gebruikers"])


def test_identical_after_upgrade_has_no_differences_even_with_other_date_notation():
    before = upgrade_proef.snapshot(FakeApi({"u-a": ADMIN, "u-g": GUEST}), "t")
    after = upgrade_proef.snapshot(FakeApi({"u-a": dict(ADMIN, LastPlayedDate="2026-11-01T20:15:00Z"), "u-g": GUEST}), "t")
    assert upgrade_proef.differences(before, after) == []
    assert upgrade_proef.digest(before) == upgrade_proef.digest(after)


@pytest.mark.parametrize(
    "admin, guest, prefs, fragment",
    [
        (dict(ADMIN, Played=False), GUEST, None, "Played: True → False"),                   # gezien kwijt
        (dict(ADMIN, PlayCount=1), GUEST, None, "PlayCount: 2 → 1"),
        (dict(ADMIN, IsFavorite=False), GUEST, None, "IsFavorite"),
        (dict(ADMIN, Rating=None), GUEST, None, "Rating"),
        (dict(ADMIN, LastPlayedDate="2026-11-02T20:15:00Z"), GUEST, None, "LastPlayedDate"),
        (ADMIN, dict(GUEST, PlaybackPositionTicks=0), None, "PlaybackPositionTicks"),        # hervatpunt kwijt
        (ADMIN, GUEST, dict(upgrade_proef.GUEST_PREFS, SubtitleMode="Default"), "SubtitleMode"),  # voorkeur kwijt
    ],
)
def test_every_lost_or_changed_viewing_datum_is_reported(admin, guest, prefs, fragment):
    before = upgrade_proef.snapshot(FakeApi({"u-a": ADMIN, "u-g": GUEST}), "t")
    after = upgrade_proef.snapshot(FakeApi({"u-a": admin, "u-g": guest}, prefs), "t")
    diff = upgrade_proef.differences(before, after)
    assert len(diff) == 1 and fragment in diff[0]


def test_missing_user_or_item_is_reported_as_lost():
    before = {"gebruikers": {"a": {"x": 1}, "b": {"x": 1}}}
    assert upgrade_proef.differences(before, {"gebruikers": {"a": {"x": 1}}}) == [
        "gebruikers/b: VERDWENEN na de upgrade (was {'x': 1})"
    ]


def test_expected_present_detects_seed_not_applied():
    snap = upgrade_proef.snapshot(FakeApi({"u-a": dict(ADMIN, PlayCount=0), "u-g": GUEST}), "t")
    rep = web_smoke.Report(mode="upgrade", base_url="x", image="x")
    upgrade_proef.expected_present(snap, rep, "VÓÓR")
    assert not rep.passed


@pytest.mark.parametrize("value, expected", [
    ("2026-11-01T20:15:00.0000000Z", "2026-11-01T20:15:00Z"),
    ("2026-11-01T20:15:00Z", "2026-11-01T20:15:00Z"),
    ("2026-11-01T20:15:00", "2026-11-01T20:15:00Z"),
    (None, None),
    ("geen datum", "geen datum"),
])
def test_iso_seconds(value, expected):
    assert upgrade_proef.iso_seconds(value) == expected


def test_ci_uses_the_same_old_and_new_images():
    """De CI-job upgrade-e2e gebruikt dezelfde oude image als de standaard en de nieuwe uit baseline.json."""
    import json

    root = Path(__file__).resolve().parents[3]
    ci = (root / ".github/workflows/jelly-leon-web-ci.yml").read_text(encoding="utf-8")
    assert f"JLW_OUDE_SERVER_IMAGE: {upgrade_proef.OLD_IMAGE}" in ci
    baseline = json.loads((root / "tools/jelly-leon-web/baseline.json").read_text(encoding="utf-8"))
    assert upgrade_proef.build_parser().parse_args([]).image == baseline["toolchain"]["server_image"]
    assert "@sha256:" in upgrade_proef.OLD_IMAGE and ":10.11.11@" in upgrade_proef.OLD_IMAGE


@pytest.mark.parametrize(
    "verwacht, oud_gezond, oud_aanmelden, schade, geslaagd, oordeel",
    [
        ("weigert", False, None, False, True, "Sim-geslaagd"),   # acceptatie JLT-61 b: oude image weigert
        ("weigert", True, 200, False, False, "Sim-mislukt"),     # oude image start: acceptatie niet gehaald
        ("start", True, 500, False, True, "Sim-mislukt"),        # gemeten: gezond maar onbruikbaar, geen schade
        ("start", True, 200, False, True, "Sim-mislukt"),        # gemeten: start en werkt, toont VÓÓR
        ("start", True, 200, True, False, "Sim-mislukt"),        # schade is altijd een fout
        ("start", False, None, False, False, "Sim-geslaagd"),    # gedrag veranderd t.o.v. de meting: opnieuw beoordelen
    ],
)
def test_negative_phase_modes(monkeypatch, verwacht, oud_gezond, oud_aanmelden, schade, geslaagd, oordeel):
    calls = {"health": 0}

    def wait_healthy(api, timeout):
        calls["health"] += 1
        return oud_gezond if calls["health"] == 1 else True

    monkeypatch.setattr(upgrade_proef.web_smoke, "start_server", lambda *a, **k: None)
    monkeypatch.setattr(upgrade_proef.web_smoke, "wait_healthy", wait_healthy)

    class Proc:
        stdout, stderr = "running 0", ""

    class OldApi:
        def json(self, method, path, **kwargs):
            assert path == "/Users/AuthenticateByName"
            return oud_aanmelden, ({"AccessToken": "oud"} if oud_aanmelden == 200 else None)

    monkeypatch.setattr(upgrade_proef, "docker", lambda *a, **k: Proc())
    monkeypatch.setattr(upgrade_proef, "login", lambda *a, **k: ("tok", {}))
    voor = {"gebruikers": {"jl-beheer": {"kijkgegevens": {"x": {"Played": True}}}}}
    na = {"gebruikers": {"jl-beheer": {"kijkgegevens": {"x": {"Played": not schade}}}}}
    monkeypatch.setattr(upgrade_proef, "snapshot", lambda api, token: na)
    args = upgrade_proef.build_parser().parse_args(["--negatief-verwacht", verwacht])
    rep, extra = web_smoke.Report(mode="upgrade", base_url="x", image="x"), {}
    upgrade_proef.negative_phase(OldApi(), args, rep, {"admin_user": "a", "admin_password": "p"}, None, "c",
                                 args, args, voor, extra)
    assert rep.passed is geslaagd
    assert extra["jlt61b"].startswith(oordeel)
    assert ("MET schade" in extra["jlt61b"]) is schade


@pytest.mark.parametrize(
    "method, url, expected",
    [
        ("POST", "http://127.0.0.1:1/Sessions/Playing", True),
        ("POST", "http://127.0.0.1:1/Sessions/Playing?x=1", True),
        ("POST", "http://127.0.0.1:1/Sessions/Playing/Progress", False),   # voortgang is geen start
        ("POST", "http://127.0.0.1:1/Sessions/Playing/Stopped", False),
        ("GET", "http://127.0.0.1:1/Sessions/Playing", False),
    ],
)
def test_is_playback_start(method, url, expected):
    assert upgrade_proef.is_playback_start(method, url) is expected


@pytest.mark.parametrize(
    "ticks, expected",
    [
        (10_000_000, True),          # precies het hervatpunt (1 s)
        (10_002_000, True),          # afronding van currentTime
        (0, False),                  # begint vooraan: hervatpunt genegeerd (JLT-60 negatief)
        (None, False),               # geen melding
        (True, False),               # geen getal
        (40_000_000, False),         # verkeerd punt
    ],
)
def test_start_position_ok(ticks, expected):
    assert upgrade_proef.start_position_ok(ticks, upgrade_proef.GUEST_DATA["PlaybackPositionTicks"]) is expected


def test_playback_reports_can_be_intercepted_without_reaching_the_server():
    """De upgradeproef verandert de kijkgegevens niet zelf: afspeelmeldingen krijgen 204 en gaan niet naar de server."""

    class Route:
        def __init__(self, request):
            self.request, self.fulfilled = request, None

        def fulfill(self, **kwargs):
            self.fulfilled = kwargs

        def continue_(self):  # pragma: no cover - mag nooit gebeuren
            raise AssertionError("melding doorgestuurd naar de server")

    class Context:
        def __init__(self):
            self.routes, self.scripts = [], []

        def add_init_script(self, script):
            self.scripts.append(script)

        def route(self, pattern, handler):
            self.routes.append((pattern, handler))

    class Browser:
        def new_context(self, **kwargs):
            assert kwargs["locale"] == "nl-NL"
            return Context()

    seen = []
    plain = web_smoke.new_context(Browser(), "modern")
    assert plain.routes == []                                   # standaard (smoketest): niets onderschept
    ctx = web_smoke.new_context(Browser(), "legacy", block_playback_reports=True, on_report=seen.append)
    assert ctx.scripts and "desktop-legacy" in ctx.scripts[0]
    [(pattern, handler)] = ctx.routes
    assert pattern == web_smoke.PLAYBACK_REPORTS_GLOB
    route = Route(request="POST /Sessions/Playing")
    handler(route)
    assert seen == ["POST /Sessions/Playing"] and route.fulfilled == {"status": 204, "body": ""}


GUEST_TRACKS = dict(upgrade_proef.GUEST_TRACKS)
ADMIN_TRACKS = {"DefaultAudioStreamIndex": 1, "DefaultSubtitleStreamIndex": -1}


def test_snapshot_records_remembered_track_choice_per_film():
    snap = upgrade_proef.snapshot(FakeApi({"u-a": ADMIN, "u-g": GUEST}, tracks={"u-g": GUEST_TRACKS, "u-a": ADMIN_TRACKS}), "t")
    assert snap["items"] == sorted([ITEM["Path"], FILM_PATH])
    guest = snap["gebruikers"][upgrade_proef.GUEST]
    assert guest["spoorkeuzes"] == {FILM_PATH: GUEST_TRACKS}               # alleen films, niet het muziekbestand
    assert set(guest["kijkgegevens"]) == {ITEM["Path"], FILM_PATH}


@pytest.mark.parametrize(
    "after_tracks, fragment",
    [
        ({"u-g": {"DefaultAudioStreamIndex": 1, "DefaultSubtitleStreamIndex": 4}, "u-a": ADMIN_TRACKS},
         "DefaultAudioStreamIndex: 2 → 1"),              # onthouden audiokeuze kwijt (terug naar voorkeur nld)
        ({"u-g": {"DefaultAudioStreamIndex": 2, "DefaultSubtitleStreamIndex": 3}, "u-a": ADMIN_TRACKS},
         "DefaultSubtitleStreamIndex: 4 → 3"),           # onthouden ondertitelkeuze kwijt
        ({"u-a": ADMIN_TRACKS}, "fout"),                 # film voor de gast niet meer afspeelbaar
    ],
)
def test_lost_track_choice_is_reported(after_tracks, fragment):
    before = upgrade_proef.snapshot(FakeApi({"u-a": ADMIN, "u-g": GUEST}, tracks={"u-g": GUEST_TRACKS, "u-a": ADMIN_TRACKS}), "t")
    after = upgrade_proef.snapshot(FakeApi({"u-a": ADMIN, "u-g": GUEST}, tracks=after_tracks), "t")
    diff = upgrade_proef.differences(before, after)
    assert diff and any(fragment in line and "spoorkeuzes" in line for line in diff), diff


def _complete_snapshot(guest_tracks: dict) -> dict:
    wav = upgrade_proef.WAV_PATH
    user = {"beleid": {}, "voorkeuren": {}, "kijkgegevens": {}, "spoorkeuzes": {}}
    users = {name: {k: dict(v) for k, v in user.items()} for name in
             ("jl-beheer", "jl-kind", upgrade_proef.GUEST, upgrade_proef.TEEN, upgrade_proef.PARENT)}
    users["jl-beheer"]["kijkgegevens"][wav] = upgrade_proef.normalise_userdata(upgrade_proef.ADMIN_DATA)
    users[upgrade_proef.GUEST]["kijkgegevens"][wav] = upgrade_proef.normalise_userdata(upgrade_proef.GUEST_DATA)
    users[upgrade_proef.GUEST]["voorkeuren"] = dict(upgrade_proef.GUEST_PREFS)
    users[upgrade_proef.GUEST]["spoorkeuzes"][FILM_PATH] = guest_tracks
    users["jl-kind"]["beleid"]["EnableAllFolders"] = False
    users[upgrade_proef.TEEN]["beleid"].update(upgrade_proef.TEEN_POLICY)
    return {"gebruikers": users}


def test_expected_present_requires_the_remembered_track_choice():
    ok = web_smoke.Report(mode="upgrade", base_url="x", image="x")
    upgrade_proef.expected_present(_complete_snapshot(GUEST_TRACKS), ok, "VÓÓR")
    assert ok.passed, ok.steps
    # Alleen de taalvoorkeur (nld = 1/3), niet de onthouden keuze: dan vergelijkt de proef niets → mislukt.
    missing = web_smoke.Report(mode="upgrade", base_url="x", image="x")
    upgrade_proef.expected_present(_complete_snapshot({"DefaultAudioStreamIndex": 1, "DefaultSubtitleStreamIndex": 3}),
                                   missing, "VÓÓR")
    assert not missing.passed


def test_server_dirs_mount_the_film_library_read_only(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(web_smoke, "docker", lambda *a, **k: calls.append(a))
    args = web_smoke.build_parser().parse_args(["--modus", "stock"])
    dirs = web_smoke.ServerDirs(config=tmp_path / "c", cache=tmp_path / "k", media=tmp_path / "m", user="1:1",
                                films=tmp_path / "f")
    web_smoke.start_server(args, dirs, "naam")
    assert f"{tmp_path / 'f'}:{web_smoke.FILMS_PATH}:ro" in calls[0]
    web_smoke.start_server(args, web_smoke.ServerDirs(config=tmp_path / "c", cache=tmp_path / "k",
                                                      media=tmp_path / "m", user="1:1"), "naam")
    assert not any(web_smoke.FILMS_PATH in part for part in calls[1])
