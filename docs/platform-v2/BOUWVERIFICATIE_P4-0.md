# Bouwverificatie P4-0 — jelly-leon-web op jellyfin-web v12.4 (B03-014 webdeel, JW1)

Datum 2026-11-09 · branch `ccr-c133d7a0-kuz1cv` · besluit: [`ADR-0011`](../adr/ADR-0011-upgrade-12x-webclient.md).
Alles hieronder is **echt uitgevoerd** op de eigen bouwmachine van de gebruiker (Ubuntu 26.04.1 LTS, kernel
7.0.0-42, 22 CPU's, 14 GiB RAM gedeeld met andere bouwers, Docker Engine 29.1.3, direct internet zonder proxy).
Zware stappen één voor één met `nice -n 10`, de productiebuild op 4 CPU's (`taskset -c 0-3`, anders liep de machine
vol: een eerste poging zonder begrenzing werd door de kernel gestopt, exit 137), stacks onder
`<WERKMAP>/.lokaal/stack.lock`. Validatie: **Sim-getest** (officiële images + headless Chromium);
geen NAS, geen echte apparaten.

## 1. Upgrade met de sync-tooling

| Stap | Commando | Uitkomst |
|---|---|---|
| Doelversie | `upstream_sync.py kies --spoor nieuwste --spoor patch` | `nieuwste`: **v12.4** (nieuwer: v12.0…v12.4); `patch`: geen kandidaat. `git ls-remote --tags` (server en web): v12.4 is de nieuwste stabiele tag, web `0a580ce8df89`, server `83d0d0e7f76e` |
| Herbasis | `upstream_sync.py merge --tag v12.4 --methode herbasis --maak-lokale-tag` | **0 conflicten**; merge-commit `2d96f377e` (ouders: forkstand `536aa7e1e` + upstream `0a580ce8d`), baseline-commit `77872d3e9` (forkversie `12.4.0-jl.0`); `package.json` = `jellyfin-web` 12.4.0 |
| Forkregels direct na de herbasis | `check_fork_consistency.py`, `patch_register_check.py`, `workflow_check.py` | consistentie en patchregister in orde; **`workflow_check.py` exit 1: 10 onbewaakte geheimgebruiken** via `workflow_run.yml` (terechte weigering 1) |
| Node 22 tegen v12.4 | `npm ci` met Node 22.23.4 / npm 10.9.9 | **exit 1, `EBADENGINE`** (vereist node ≥ 24.0.0, npm ≥ 11.0.0; terechte weigering 2) |
| Oplossing 1 | guard-patch **JLW-0001** (2 regels) | `workflow_check.py`: 10 upstream (bewaakt), 2 eigen (vastgezet) |
| Oplossing 2 | toolchain **Node 24.22.2 / npm 11.19.1** (nodejs.org-tarball, sha256 tegen `SHASUMS256.txt`) | `npm ci` slaagt (§2) |

De herbasis is twee keer uitgevoerd: eerst op `3e717e26b`; omdat de remote branch intussen vijf documentcommits van
een andere bouwstap had gekregen, daarna opnieuw op `536aa7e1e` (zelfde tool, zelfde uitkomst, 0 conflicten) en zijn de
eigen commits daarop gezet. Er is niets geforceerd gepusht.

## 2. Kwaliteit en build (Node 24.22.2, code = commit `0e3352ca9`)

| Commando | Exit | Duur | Uitkomst |
|---|---|---|---|
| `npm ci --no-audit --no-fund --cache <lege map> --loglevel=http` | 0 | 15 s | 1771 pakketten, alles echt opgehaald (lege cache); `classlist.js` rechtstreeks van `codeload.github.com` (HTTP 200) |
| `npm run lint` | 0 | 54 s | eslint 9.39.5: **0 fouten**, 98 waarschuwingen (allemaal upstream) |
| `npm run stylelint` | 0 | 2 s | 0 problemen |
| `npm run build:check` | 0 | 8 s | `tsc --noEmit` (TypeScript 5.9.3): 0 fouten |
| `npm test` | 0 | 2 s | vitest 3.2.7: **12 bestanden, 164/164 geslaagd** |
| `JELLYFIN_VERSION=<commit> taskset -c 0-3 npm run build:production` | 0 | 95 s | webpack 5.109.0, 2 upstream-groottewaarschuwingen; `dist/` 2348 bestanden, 61 MB; `<title>Jelly Leon</title>` |
| `npm run escheck` | 0 | — | es-check 9.6.4: 982 bestanden ES5 in orde |
| Build in de Node-image op digest: `docker run --cpuset-cpus 0-3 --memory 6g --user <uid> node:24.22.2-bookworm-slim@sha256:01d566e8…70e9` met `npm ci && npm run build:production && npm run escheck` | 0 | 100 s | Node v24.22.2, npm 11.19.1; 2348 bestanden; `<title>Jelly Leon</title>` — dezelfde image als de CI-job *build* en de aanbevolen `NODE_IMAGE` van jelly-leon |

## 3. Forkregels en tool-tests

| Commando | Uitkomst |
|---|---|
| `check_fork_consistency.py` | in orde: basis v12.4 (`0a580ce8df89`), forkversie 12.4.0-jl.0, identiteit `jellyfin-web` 12.4.0; zichtbare naam alleen "Jellyfin" → "Jelly Leon" in de drie merkbestanden; toolchain overal gelijk en binnen `engines` |
| `patch_register_check.py` | in orde: 2 patches (JLW-0001, JLW-0002), 4 bestanden |
| `contract_drift.py --online` | contractkopieën byte-gelijk aan `ai-server-manager@8b54f3940` |
| `workflow_check.py --overzicht` | 10 upstream-workflows (geheimen bewaakt, nu ook `workflow_run.yml`), 2 eigen (vastgezet) |
| `upstream_gedrag_check.py --overzicht` | 19/19 ankers gevonden (UG-WEB-1…19). Tegenproef op de 10.11.11-boom: 11 van de 19 ankers falen (verhuisde bestanden en ander gedrag) |
| `pytest -q -c tools/jelly-leon-web/pytest.ini tools/jelly-leon-web/tests` | **130 geslaagd** op de verificatiecommit `0e3352ca9`; met de unit-tests van de upgradeproef erbij **153 geslaagd** (lokaal, `cb8341c12`) |
| `actionlint` (met shellcheck 0.11.0) op beide eigen workflows | 0 meldingen |

## 4. Web-client-smoketest tegen `jellyfin/jellyfin:12.4@sha256:fea863d0…b771` (Chromium 153.0.8010.12, Playwright 1.63.0)

| Modus | Uitkomst | Inhoud |
|---|---|---|
| `web_smoke.py --modus fork --dist dist --layouts modern,legacy` | **45/45**, 52 s | API: identiteit "Jellyfin Server" 12.4.0, fork-build geserveerd, zichtbare naam "Jelly Leon" (titel, application-name, manifest), wizard, bibliotheek, kinderprofiel, server-ACL, zonder token 401, **legacy-authenticatie uit** (`X-Emby-Token`/`api_key=`/`X-Emby-Authorization` 401, `Authorization` 200). Per layout (Modern = standaard, Legacy = `desktop-legacy`): aanmelden in het Nederlands, fout wachtwoord geweigerd, inloggen, juiste layout actief, webclient meldt zich als **"Jellyfin Web" 12.4.0** (`/Sessions`) met `jellyfin_credentials`, zoeken, detailpagina + afspelen (HTTP 200), kinderprofiel ziet niets, 360/390/768/1440 px zonder overloop. Daarna herstart, terugzetten naar de stock-webclient ("Jellyfin") en weer vooruit ("Jelly Leon") op dezelfde `/config`: telkens gegevens, stream en ACL behouden |
| `web_smoke.py --modus stock --layouts modern,legacy` | **39/39**, 41 s | dezelfde reis met de webclient uit de officiële image ("Jellyfin"), incl. herstart |

Rapporten en vijf schermafbeeldingen: [`test-evidence/p40-web-smoke/`](test-evidence/p40-web-smoke/).

## 5. Upgradeproef 10.11.11 → 12.4 met behoud van kijkgegevens (JLT-60/JLT-61 webdeel)

`tools/jelly-leon-web/e2e/upgrade_proef.py` (HARDE EIS: kijkgeschiedenis blijft behouden). Opzet: stock 10.11.11
(digest `aefb67e6…35db`) met wizard, bibliotheek en **vijf gebruikers** (beheerder, kind zonder toegang, gast, tiener met
leeftijdsgrens 13 en geblokkeerde tag, ouder); kijkgegevens via de officiële API (beheerder 2× gezien met datum,
favoriet, beoordeling 8; gast hervatpunt 1 s en taal-/ondertitelvoorkeuren `nld`; tiener gezien; ouder favoriet);
VÓÓR-rapport per gebruiker (beleid, voorkeuren, kijkgegevens per item; sha256); kopie van `/config`; dan 12.4 met de
fork-build op dezelfde `/config` (migraties), NA-rapport, browserreis in beide layouts en de hervatknop voor de gast;
terugzetten (oude image + kopie) en de negatieve proef (alleen de oude image op de gemigreerde data).

### 5.1 Uitkomst (GitHub-runner, run 42681489156, commit `cb8341c12`): **46/46**

| Onderdeel | Uitkomst |
|---|---|
| Migratie 10.11.11 → 12.4 | zonder handwerk; server 12.4.0 gezond; beheerder logt in met hetzelfde wachtwoord |
| VÓÓR = NA per gebruiker | **0 verschillen**, sha256 VÓÓR = NA (`68a660997cd57b2c…`): gezien, aantal, datum, hervatpunt (10 000 000 ticks), favorieten, beoordeling, taal-/ondertitelvoorkeuren, rechten (o.a. `MaxParentalRating` 13 en `BlockedTags` van de tiener, kind zonder bibliotheektoegang) |
| Browser na de upgrade (fork-build) | Modern en Legacy: aanmelden, zoeken, detailpagina, afspelen (HTTP 200), kinderprofiel ziet niets, 360…1440 px; webclient = "Jellyfin Web" 12.4.0 |
| Hervatten | de gast krijgt in beide layouts "Hervatten" op de detailpagina (hervatpunt bewaard) |
| Terugzetten (JLT-61 a) | oude image + kopie van vóór de migratie: `jellyfin.db` van de kopie byte-gelijk aan die van vóór (`0a0432a93ff4cb89…`), gezond, 0 verschillen met VÓÓR, stream HTTP 200 |
| Negatieve proef (JLT-61 b) | **gemeten:** de oude stock-image 10.11.11 meldt zich op de gemigreerde `/config` *gezond* (`/health`), maar aanmelden geeft **HTTP 500** (uitzondering in de serverlog) — geen weigering met een duidelijke melding. **Geen blijvende schade**: 12.4 daarna opnieuw op dezelfde map = VÓÓR. JLT-61 (b) is daarmee met stock-images **Sim-mislukt**; de weigering hoort in de jelly-leon-image (downgradecontrole, ADR-0011 in jelly-leon §4). In CI legt `--negatief-verwacht start` dit gemeten gedrag vast; stille schade blijft daar een fout. |

Rapport: [`test-evidence/p40-upgrade/upgrade-proef-ci-42681489156.json`](test-evidence/p40-upgrade/upgrade-proef-ci-42681489156.json).
De proef is **niet lokaal** gedraaid: `stack.lock` was meer dan 30 minuten bezet door een andere bouwer; de run op de
GitHub-runner is de uitvoering. De twee eerdere CI-runs (42678478921: 43/44, 42680117590: 45/46) faalden alleen op de
negatieve proef; zie §6.

## 6. GitHub-CI

| Run | Commit | Uitkomst |
|---|---|---|
| [42674062638](https://github.com/lvos04/jelly-leon-web/actions/runs/42674062638) | `0e3352ca9` | poging 1 en 2: mislukt zonder dat de jobs startten, tijdens de GitHub-storing "Incident with Actions and Checks API" (githubstatus.com, 2026-11-09 vanaf 18:12Z); poging 3: **geslaagd, 7/7 jobs** (build in de Node-image, smoketest 45/45) |
| [42678478921](https://github.com/lvos04/jelly-leon-web/actions/runs/42678478921) | `8803546e9` | mislukt: upgradeproef 43/44 (negatieve proef eiste een weigering; de stock-image start wel) |
| [42680117590](https://github.com/lvos04/jelly-leon-web/actions/runs/42680117590) | `60a695444` | mislukt: upgradeproef 45/46 ("niet leesbaar via de oude API" telde als schade) |
| [42681489156](https://github.com/lvos04/jelly-leon-web/actions/runs/42681489156) | `cb8341c12` | **geslaagd, 8/8 jobs**: forkregels (pytest 152 + 1 overgeslagen), eslint/stylelint/tsc/vitest 164/164 op Node 24.22.2, build in `node:24.22.2-bookworm-slim@sha256:01d566e8…` (2348 bestanden), smoketest 45/45, upgradeproef 46/46 |

Samenvatting in [`test-evidence/p40-github-ci-run-42681489156.json`](test-evidence/p40-github-ci-run-42681489156.json);
lokale metingen in [`test-evidence/p40-lokale-bouw.json`](test-evidence/p40-lokale-bouw.json).

## 7. Wat niet gevalideerd is

- Echte NAS en de echte (Emby-)kijkgeschiedenis: **NIET GEVALIDEERD (echte NAS)** — de upgradeproef gebruikt
  synthetische gebruikers en één zelfgemaakt testnummer. De overname vanuit Emby (B03-015, JLT-70…74) hoort bij
  `lvos04/jelly-leon`.
- Echte tv's, telefoons, tablets en tv-browsers (D15): **NIET GEVALIDEERD (hardware)**; Safari/Swiftfin:
  **NIET GEVALIDEERD (Mac/Xcode)**.
- De jelly-leon-image met deze webstand: nog niet (andere repo; zie ADR-0011 "Gevolgen").
- Een echte run van `upstream-sync.yml` op GitHub (alleen vanaf de standaardbranch) en de sync 12.4 → 12.y (JLT-67):
  er is nog geen nieuwere 12.x-tag dan v12.4.

## 8. Onafhankelijke review P4-0 (2026-11-09, na commit `b693399a9`)

Alles opnieuw zoals de CI het draait, lokaal op de bouwmachine (Node 24.22.2 / npm 11.19.1, Python 3.12.16, Chromium
153 headless). `stack.lock` was de hele review bezet door de langlopende MSO-reviewstack (tot 4 uur); de E2E-proeven
zijn daarom zonder `stack.lock` gedraaid, op hun eigen poorten 38097/38098 (vooraf vrij gecontroleerd). Het zijn geen
tijdmetingen. Samenvatting: [`test-evidence/p40-review/p40-review-qa.json`](test-evidence/p40-review/p40-review-qa.json).

| Controle | Uitkomst |
|---|---|
| Alleen upstream + geregistreerde patches | `git diff upstream-v12.4 HEAD` buiten de fork-eigen paden: alleen de 4 bestanden van JLW-0001/0002; 0 verwijderde of hernoemde upstream-bestanden; lokale tag `upstream-v12.4` = `git ls-remote` v12.4 (`0a580ce8df89`); v12.4 is nog steeds de nieuwste stabiele tag |
| Forkregels | `check_fork_consistency.py`, `patch_register_check.py`, `contract_drift.py` (online en tegen `../ai-server-manager`), `workflow_check.py`, `upstream_gedrag_check.py` (19/19): alle exit 0; B03-plankopieën sha256-gelijk aan de bron |
| Tool-tests | 153 geslaagd op `b693399a9`; **171** na de reparaties |
| actionlint (shellcheck 0.11.0) | 0 meldingen |
| `npm ci`, lint, stylelint, tsc, vitest | exit 0; eslint 0 fouten (98 upstream-waarschuwingen), vitest 164/164 |
| Productiebuild + es-check (4 CPU's) | 2348 bestanden, 61 MB, `<title>Jelly Leon</title>`; 982 bestanden ES5 |
| Smoketest fork / stock (12.4 op digest, Modern + Legacy) | **45/45** en **39/39**, twee keer (op `1ee24c507` en `d67edaacf`) |
| Upgradeproef 10.11.11 → 12.4 | nu ook **lokaal**: 48/48 (met hervatpuntcontrole), daarna **50/50** (met onthouden spoorkeuzes) |
| GitHub-CI run [42686982044](https://github.com/lvos04/jelly-leon-web/actions/runs/42686982044) (`1ee24c507`) | **8/8 jobs**: smoketest fork 45/45 én stock 39/39 (stock nieuw in CI), upgradeproef 48/48 |
| GitHub-CI run [42688123496](https://github.com/lvos04/jelly-leon-web/actions/runs/42688123496) (`d67edaacf`) | **8/8 jobs**: tool-tests 170 + 1 overgeslagen, smoketest fork 45/45 en stock 39/39, upgradeproef **50/50** (spoorkeuze gast 2/4 vóór en na; hervatten op PositionTicks 10 058 100 in Modern en 10 000 000 in Legacy, binnen de marge van 0,25 s) |

### 8.1 Gevonden en gerepareerd

1. **Hervatten op het juiste punt (JLT-60) was niet echt gemeten** — alleen dat de knop "Hervatten" zichtbaar is. Nu
   klikt de gast in beide layouts op Hervatten en moet de webclient de afspeelstart (`POST /Sessions/Playing`) melden
   met `PositionTicks` = het hervatpunt: gemeten **10 000 000** (1 s) in Modern en Legacy (`218a0c5d5`).
2. **De proef kon de kijkgegevens zelf veranderen.** Een gemelde afspeelstart verhoogt `PlayCount` en zet
   `LastPlayedDate`; dan meldt de negatieve proef vals "schade" en ziet de tweede layout geen hervatpunt meer. Dat het
   tot nu toe goed ging, hing af van timing (de browser sloot direct na het streamverzoek), niet van de proef. In de
   upgradeproef worden de afspeelmeldingen nu onderschept (204, niet naar de server); de smoketest blijft ongewijzigd
   (`218a0c5d5`).
3. **HARDE EIS "onthouden spoorkeuzes" was niet gedekt** (één spoor in het testbestand; alleen de taalvoorkeur
   vergeleken). Nu: testfilm van 3 s met 2 audio- en 2 ondertitelsporen (nld/eng), gemaakt met de ffmpeg uit de oude
   image op digest (`--network none`, bitexact, sha256 `14401ef7…`), niet gecommit. Op 10.11.11 kiest de gast via
   afspeelmeldingen de Engelse sporen 2/4 tegen haar voorkeur nld (1/3) in; vóór én na de upgrade biedt PlaybackInfo de
   gast 2/4 aan, de anderen 1/3, het kind HTTP 404 (geen toegang) — **0 verschillen** (`d67edaacf`).
4. **CI draaide alleen de fork-smoketest**; B03-014 ("stock-client-smoketest") en JW1 ("smoketest fork/stock") vragen
   ook stock. Nu beide in de job `web-e2e`; stock draait ook als fork faalt (`428473d3c`).
5. **`check_fork_consistency.py` accepteerde een testrij die tegelijk Sim-geslaagd en Sim-mislukt is**; nu een fout
   (`1ee24c507`).
6. `EVIDENCE.json` (JLT-60) verwees naar een niet-bestaand rapportbestand; rechtgezet.

Niet gewijzigd: geen upstream-bestand, geen patch, geen toolchain. JLT-61 (b) blijft **Sim-mislukt** (de oude
stock-image weigert de gemigreerde data niet zichtbaar; de weigering hoort in `lvos04/jelly-leon`). Rapporten:
[`test-evidence/p40-review/`](test-evidence/p40-review/).
