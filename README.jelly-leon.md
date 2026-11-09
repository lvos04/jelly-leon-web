# jelly-leon-web

Webclient van **Jelly Leon** (TrueNAS Home Platform V2, project B03 "Universele mediaserver") — een fork van
[`jellyfin/jellyfin-web`](https://github.com/jellyfin/jellyfin-web) **v10.11.11**, met volledige upstream-historie.
De upstream-README staat ongewijzigd in [`README.md`](README.md). Licentie: GPL-2.0-or-later (zie [`LICENSE`](LICENSE));
gebaseerd op Jellyfin, met dank aan alle [upstream-bijdragers](CONTRIBUTORS.md).

> Technische identiteit blijft **Jellyfin** (`jellyfin-web` 10.11.11, clientnaam "Jellyfin Web"); alleen de zichtbare
> naam wordt later "Jelly Leon". In fase P0 is er **niets** aan de webcode of branding gewijzigd.

## Stand (P0 + contractronde 1.2, 2026-11-09)

- 0 core-patches: de broncode is identiek aan upstream v10.11.11 ([`PATCHES.md`](docs/platform-v2/PATCHES.md)).
- Forkregels, upstream-sync en CI: [`tools/jelly-leon-web/`](tools/jelly-leon-web), [`.github/workflows/jelly-leon-web-ci.yml`](.github/workflows/jelly-leon-web-ci.yml),
  [`.github/workflows/upstream-sync.yml`](.github/workflows/upstream-sync.yml).
- Lokaal gemeten: `npm ci`, eslint, stylelint, tsc, vitest (160/160), productiebuild, es-check, 50 tool-tests en de
  web-client-smoketest (fork 30/30 incl. herstart en terugzetten, Chromium tegen de officiële server) — zie
  [`BOUWVERIFICATIE_P0.md`](docs/platform-v2/BOUWVERIFICATIE_P0.md) §7 (review).
- Jelly Leon Web-CI op GitHub geslaagd (runs 42601333719 en 42610233474, 7/7 jobs, smoketest 30/30 op een GitHub-runner).
- Contract 1.2 (2026-11-09): [`PLATFORM_CONTRACTEN.md`](docs/platform-v2/PLATFORM_CONTRACTEN.md) en
  [`CONTRACT_1.2_CONFORMITEIT.md`](docs/platform-v2/CONTRACT_1.2_CONFORMITEIT.md) byte-gelijk overgenomen met drifttest
  (`tools/jelly-leon-web/contract_drift.py`, CI), strengere bewijsregels voor `EVIDENCE.json` (§11) — ADR-0010.
  JW3: op de eigen bouwmachine werkt `npm ci` (ook het `classList.js`-archief van GitHub) zonder omweg; volledige
  build, 68 tool-tests en smoketest fork 30/30 / stock 24/24 opnieuw lokaal geslaagd
  ([`BOUWVERIFICATIE_P0.md`](docs/platform-v2/BOUWVERIFICATIE_P0.md) §8). JW1 (12.x) volgt in een eigen fase vóór P4.
- Onafhankelijke review contract 1.2: alles opnieuw zoals de CI (75 tool-tests, vitest 160/160, build, smoketest
  fork 30/30 / stock 24/24); bewijscontrole fail-closed gemaakt ([`BOUWVERIFICATIE_P0.md`](docs/platform-v2/BOUWVERIFICATIE_P0.md) §9).
- Niet gevalideerd: echte tv's/telefoons (D15), echte NAS, een echte run van `upstream-sync.yml`.

## Documenten

| Document | Inhoud |
|---|---|
| [`docs/platform-v2/FORK_STRATEGIE.md`](docs/platform-v2/FORK_STRATEGIE.md) | hoe B03-uitbreidingen in de webclient komen (plugin/configuratie eerst, kleine haken) |
| [`docs/platform-v2/INVENTARIS.md`](docs/platform-v2/INVENTARIS.md) | bouwsysteem, Node, tests, lint, i18n, routes, delta-matrix |
| [`docs/platform-v2/PATCHES.md`](docs/platform-v2/PATCHES.md) | patchregister (CI-gecontroleerd) |
| [`docs/adr/`](docs/adr/README.md) | architectuurbesluiten ADR-0001…0010 |
| [`docs/platform-v2/PLATFORM_CONTRACTEN.md`](docs/platform-v2/PLATFORM_CONTRACTEN.md) | platformcontract 1.2 (kopie, bron: `lvos04/ai-server-manager`) |
| [`docs/platform-v2/EVIDENCE.json`](docs/platform-v2/EVIDENCE.json) | bewijs per Excel-ID (contract §11) |
| [`deploy/truenas/CUSTOM_APP.md`](deploy/truenas/CUSTOM_APP.md) | waarom er geen eigen Custom App is (zit in `jelly-leon`) |

## Ontwikkelen

```sh
npm ci                      # Node 22.23.4 (CI); upstream .nvmrc zegt 20 (EOL), zie ADR-0009
npm test                    # vitest
npm run lint && npm run stylelint && npm run build:check
npm run build:production    # → dist/
# venv buiten de repo: upstream-eslint lint "./" en negeert geen .venv in de werkmap
python3.12 -m venv ~/.venvs/jelly-leon-web && ~/.venvs/jelly-leon-web/bin/pip install -r tools/jelly-leon-web/requirements-dev.txt
PY=~/.venvs/jelly-leon-web/bin/python
$PY tools/jelly-leon-web/patch_register_check.py
$PY tools/jelly-leon-web/check_fork_consistency.py
$PY tools/jelly-leon-web/workflow_check.py --overzicht
$PY tools/jelly-leon-web/contract_drift.py            # --online (GitHub) of --bron-map ../ai-server-manager
$PY -m pytest -q -c tools/jelly-leon-web/pytest.ini tools/jelly-leon-web/tests
$PY tools/jelly-leon-web/e2e/web_smoke.py --modus fork --uitvoer /tmp/web-smoke   # vraagt Docker + Chromium
```

Installatie gebeurt nooit vanuit deze repo: de webclient zit in de standaard TrueNAS Custom App `jelly-leon`
(`ghcr.io/lvos04/jelly-leon`), die het platform via de TrueNAS-API installeert.
