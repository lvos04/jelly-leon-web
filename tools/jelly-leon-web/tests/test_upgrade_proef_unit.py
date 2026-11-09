"""Unit-tests voor e2e/upgrade_proef.py (zonder Docker): vergelijking van kijkgegevens vóór/na (HARDE EIS, §10.9)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "e2e"))

import upgrade_proef  # noqa: E402
import web_smoke  # noqa: E402

ITEM = {"Id": "i1", "Path": "/media/muziek/Jelly Leon Test/Smoketest/01 - Sinus 440 Hz.wav"}


class FakeApi:
    def __init__(self, userdata: dict, prefs: dict | None = None):
        self.userdata = userdata
        self.prefs = prefs or dict(upgrade_proef.GUEST_PREFS)

    def json(self, method, path, token=None, body=None, **_kwargs):
        assert token
        if path == "/Users":
            return 200, [
                {"Id": "u-g", "Name": upgrade_proef.GUEST, "Policy": {"EnableAllFolders": True, "BlockedTags": ["b", "a"]},
                 "Configuration": self.prefs},
                {"Id": "u-a", "Name": "jl-beheer", "Policy": {"IsAdministrator": True}, "Configuration": {}},
            ]
        if path.startswith("/Items?"):
            return 200, {"Items": [ITEM]}
        if path.startswith("/UserItems/i1/UserData?userId="):
            return 200, self.userdata[path.rsplit("=", 1)[1]]
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
