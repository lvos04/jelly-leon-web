# jelly-leon-web

Webclient van **Jelly Leon** (TrueNAS Home Platform V2, project B03 "Universele mediaserver") — een fork van
[`jellyfin/jellyfin-web`](https://github.com/jellyfin/jellyfin-web) **v10.11.11**, met volledige upstream-historie.
De upstream-README staat ongewijzigd in [`README.md`](README.md). Licentie: GPL-2.0-or-later (zie [`LICENSE`](LICENSE));
gebaseerd op Jellyfin, met dank aan alle [upstream-bijdragers](CONTRIBUTORS.md).

> Technische identiteit blijft **Jellyfin** (`jellyfin-web` 10.11.11, clientnaam "Jellyfin Web"); alleen de zichtbare
> naam wordt later "Jelly Leon". In fase P0 is er **niets** aan de webcode of branding gewijzigd.

## Stand (P0, 2026-11-09)

- 0 core-patches: de broncode is identiek aan upstream v10.11.11 ([`PATCHES.md`](docs/platform-v2/PATCHES.md)).
- Forkregels, upstream-sync en CI: [`tools/jelly-leon-web/`](tools/jelly-leon-web), [`.github/workflows/jelly-leon-web-ci.yml`](.github/workflows/jelly-leon-web-ci.yml),
  [`.github/workflows/upstream-sync.yml`](.github/workflows/upstream-sync.yml).
- Lokaal gemeten: `npm ci`, eslint, stylelint, tsc, vitest (160/160), productiebuild, es-check en de
  web-client-smoketest (21/21, Chromium tegen de officiële server) — zie [`BOUWVERIFICATIE_P0.md`](docs/platform-v2/BOUWVERIFICATIE_P0.md).
- Niet gevalideerd: echte tv's/telefoons (D15), echte NAS, echte GitHub-runs.

## Documenten

| Document | Inhoud |
|---|---|
| [`docs/platform-v2/FORK_STRATEGIE.md`](docs/platform-v2/FORK_STRATEGIE.md) | hoe B03-uitbreidingen in de webclient komen (plugin/configuratie eerst, kleine haken) |
| [`docs/platform-v2/INVENTARIS.md`](docs/platform-v2/INVENTARIS.md) | bouwsysteem, Node, tests, lint, i18n, routes, delta-matrix |
| [`docs/platform-v2/PATCHES.md`](docs/platform-v2/PATCHES.md) | patchregister (CI-gecontroleerd) |
| [`docs/adr/`](docs/adr/README.md) | architectuurbesluiten ADR-0001…0009 |
| [`docs/platform-v2/EVIDENCE.json`](docs/platform-v2/EVIDENCE.json) | bewijs per Excel-ID (contract §11) |
| [`deploy/truenas/CUSTOM_APP.md`](deploy/truenas/CUSTOM_APP.md) | waarom er geen eigen Custom App is (zit in `jelly-leon`) |

## Ontwikkelen

```sh
npm ci                      # Node 22.23.4 (CI); upstream .nvmrc zegt 20 (EOL), zie ADR-0009
npm test                    # vitest
npm run lint && npm run stylelint && npm run build:check
npm run build:production    # → dist/
python3.12 -m venv .venv && .venv/bin/pip install -r tools/jelly-leon-web/requirements-dev.txt
.venv/bin/python tools/jelly-leon-web/patch_register_check.py
.venv/bin/python tools/jelly-leon-web/check_fork_consistency.py
.venv/bin/python tools/jelly-leon-web/workflow_check.py --overzicht
.venv/bin/python -m pytest -q -c tools/jelly-leon-web/pytest.ini tools/jelly-leon-web/tests
.venv/bin/python tools/jelly-leon-web/e2e/web_smoke.py --modus fork --uitvoer /tmp/web-smoke   # vraagt Docker + Chromium
```

Installatie gebeurt nooit vanuit deze repo: de webclient zit in de standaard TrueNAS Custom App `jelly-leon`
(`ghcr.io/lvos04/jelly-leon`), die het platform via de TrueNAS-API installeert.
