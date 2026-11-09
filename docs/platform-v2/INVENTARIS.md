# Inventaris jelly-leon-web (P0, B03-001 webdeel)

Peildatum 2026-11-09 · branch `ccr-c133d7a0-kuz1cv` · basis `jellyfin/jellyfin-web` v10.11.11
(`35c0793ece3adbd247eab290ae1effab851f3d37`, lokale tag `upstream-v10.11.11`). Alles hieronder is **gemeten in deze
repository** (commando's in [`BOUWVERIFICATIE_P0.md`](BOUWVERIFICATIE_P0.md)), niet op een NAS. Over wat er op de NAS
draait (huidige Jellyfin-versie, clients, D07/D15) zegt dit document niets.

## 1. Repository en herkomst

| Onderdeel | Stand |
|---|---|
| Upstream | `jellyfin/jellyfin-web` (remote `upstream`), volledige historie samengevoegd in commit `6fde14bf6` |
| Fork-eigen | `README.jelly-leon.md`, `docs/platform-v2/`, `docs/adr/`, `deploy/`, `tools/jelly-leon-web/`, `.env.example`, `.github/workflows/jelly-leon-web-ci.yml`, `.github/workflows/upstream-sync.yml` (`tools/jelly-leon-web/fork_paths.txt`) |
| Core-patches | **0** (`docs/platform-v2/PATCHES.md`; CI-gecontroleerd) |
| Upstream-README | `README.md` ongewijzigd; onze README is `README.jelly-leon.md` |
| Licentie | GPL-2.0-or-later (`package.json`), `LICENSE` = GPL-2.0-tekst, `CONTRIBUTORS.md` ongewijzigd |
| Broncode | `src/`: 1084 bestanden, waarvan 525 `.ts/.tsx` en 248 `.js/.jsx` |
| Nieuwere upstream-tags | spoor 10.11.x: geen; nieuwste: `v12.0`…`v12.4` (v12.4 eist Node ≥ 24/npm ≥ 11, zie §7) |

## 2. Bouwsysteem en toolchain

| Onderdeel | Stand | Opmerking |
|---|---|---|
| Bundler | **webpack 5.99.9** (`webpack.common.js`/`.prod.js`/`.dev.js`), babel 7, ts-loader, sass/postcss, `fork-ts-checker` | Vite alleen als vitest-config (`vite.config.ts`) |
| Scripts | `build:production`, `build:development`, `build:check` (`tsc --noEmit`), `build:es-check`, `escheck`, `lint`, `stylelint`, `test`, `serve` | zie `package.json` |
| Node | `.nvmrc` = **20**, `engines` node ≥ 20, npm ≥ 9.6.4 < 11, `engine-strict=true` (`.npmrc`) | Node 20 is sinds 2026-04-30 end-of-life → CI gebruikt **22.23.4** (zelfde als de web-stage van de jelly-leon-image), ADR-0009 |
| npm | lokaal 10.9.9 (binnen `engines`) | npm 11 zou door `engine-strict` geweigerd worden |
| Afhankelijkheden | 1724 pakketten na `npm ci`; `package-lock.json` v3 | één afhankelijkheid van een GitHub-archief: `classlist.js` (`github.com/eligrey/classList.js/archive/1.2.20180112.tar.gz`) |
| Build-variabelen | `JELLYFIN_VERSION` (bouwlabel), `USE_SYSTEM_FONTS`, `WEBPACK_SERVE`, `NODE_ENV`; commit via `git describe` | gedocumenteerd in `.env.example` (geen geheimen) |
| Uitvoer | `dist/`: 2317 bestanden, ~60 MB, `index.html`, `config.json`, `manifest.json`, `serviceworker.js` | ES5-controle (`es-check`) slaagt |
| Browsers | `browserslist` incl. oude tv-browsers (Chrome 27/38/47/53/56/63, Edge 18, iOS > 10) | belangrijk voor tv-browsers (B03-003); niet wijzigen |

## 3. Tests, lint en kwaliteit (upstream)

| Controle | Werktuig | Gemeten (lokaal, Node 22.23.4) |
|---|---|---|
| Unit-tests | vitest 3.2.4 (jsdom) | **12 bestanden, 160/160 geslaagd** (`space`, `itemText`, `mediaSegments`, `cardBuilderUtils`, `browser`, `card`, `dateFnsLocale`, `events`, `file`, `image`, `string`, `url`) |
| Lint JS/TS | eslint 9.30.1 flat config (typescript-eslint, react, react-hooks, jsx-a11y, sonarjs, compat, import, @stylistic) | **0 fouten**, 103 waarschuwingen (upstream) |
| Lint CSS | stylelint 16.21.0 | 0 problemen |
| Types | `tsc --noEmit` (TypeScript 5.8.3, target ES5) | 0 fouten |
| ES5-bundel | es-check 9.1.4 | in orde |
| E2E | **geen upstream-E2E** | eigen web-client-smoketest (`tools/jelly-leon-web/e2e/web_smoke.py`): fork 21/21, stock 21/21 |
| Afhankelijkhedenaudit | `npm audit` (informatief) | runtime: 23 meldingen (2 kritiek: `swiper`, `tar` via `pdfjs-dist`; 17 hoog o.a. `dompurify` 2.5.8, `react-router-dom` 6.30.1, `pdfjs-dist` 3.11.174, `markdown-it`, `lodash-es`); totaal incl. dev 95. **In P0 niet gepatcht** (zou een core-patch op `package.json`/lock zijn); oplossen via upstream-sync of bewuste, geregistreerde patch — followup |

Upstream-CI (`.github/workflows/__quality_checks.yml`) draait dezelfde vijf controles (`build:es-check`, `lint`,
`stylelint`, `build:check`, `test`) op Node 20 plus dependency-review en CodeQL.

## 4. i18n (Nederlands)

| Onderdeel | Stand |
|---|---|
| Mechanisme | `src/lib/globalize` met JSON-bestanden in `src/strings/` (99 talen); taal = gebruikersinstelling, anders `navigator.language` |
| `nl.json` | **100 %** van de 1871 `en-us`-sleutels aanwezig (2072 sleutels, 201 verouderde extra); 82 waarden gelijk aan Engels (vakwoorden als "Album", "AirPlay", "Anime") |
| Gemeten in de browser | met `locale nl-NL` toont de aanmeldpagina "Meld je aan", "Gebruiker", "Wachtwoord", "Aanmelden"; foutmelding "Ongeldige gebruikersnaam of wachtwoord…"; zoeken zonder resultaat "Sorry! Geen resultaten gevonden voor …" |
| Eigen teksten (later) | via `globalize.loadStrings`/`register` in fork-eigen bestanden; upstream-`src/strings/*.json` blijven ongewijzigd (FORK_STRATEGIE §2) |

## 5. Routes en schermen relevant voor B03

App-indeling: `src/apps/stable` (standaard-UI), `src/apps/experimental` (nieuwe React-UI, opt-in),
`src/apps/dashboard` (beheer), `src/apps/wizard` (eerste start). Routes in `routes/asyncRoutes/*.ts` (React) en
`routes/legacyRoutes/*.ts` (oude controllers + HTML).

| B03-scherm/-functie | Upstream-route / -onderdeel | Wat er al is | Uitbreidingspunt (FORK_STRATEGIE §2/§4) |
|---|---|---|---|
| Discover / Bibliotheek / Film / Serie / Muziek | `#/home` (`controllers/home`), `#/movies`, `#/tv`, `#/music`, `#/list` | volledige bibliotheek-UI | geen patch nodig (B03-002 is serverwerk) |
| Anime | geen eigen route (anime = bibliotheek/collectie) | — | server (metadata-overlay), geen webpatch in P0 |
| Detail (titel) | `#/details` (`controllers/itemDetails/index.js` + `.html`) | knoppen afspelen, trailer, gezien, favoriet, menu | **haak JLW-0001** voor MediaGuard-knop (B03-009) |
| Zoeken | `#/search` (`apps/stable/routes/search.tsx`, `features/search/*`) | items, personen, artiesten, live-tv; serverzoeken via `/Items` | **haak JLW-0002** of eigen route voor scènes (B03-008) |
| Speler / kwaliteitsweergave | `#/video` (`controllers/playback/video`), `components/playerstats/playerstats.js` | *Playback Info*: afspeelmethode, codecs, bitrate, **transcode-redenen**; hardware-acceleratieregel staat uitgecommentarieerd | **haak JLW-0003** voor label/hardware-lane (B03-004/005) |
| Intro/recap/credits overslaan | `components/playback/skipsegment.ts`, `apps/stable/features/playback/utils/mediaSegment*` | upstream ondersteunt mediasegmenten + overslaan (getest in `mediaSegments.test.ts`) | geen patch; segmentbron is serverwerk (B03-007) |
| Live-tv / DVR | `#/livetv`, dashboard `livetv`, `livetv/recordings`, `livetv/guide`, `livetv/tuner` | gids, opnames, tuners | conflict-UI (B03-012) later; eerst server |
| Profielen / kinderprofiel | dashboard `users`, `users/access`, `users/parentalcontrol`, `users/profile`; `#/userprofile`, `#/mypreferences*` | bibliotheektoegang, leeftijdsclassificatie, tags, schema's | **geen webpatch**; afdwingen op de server (B03-010) — gemeten in de smoketest |
| Apparaten | dashboard `devices` | apparatenlijst | — |
| Downloads | contextmenu "Downloaden" (gebruikersbeleid `EnableContentDownloading`) | browserdownload van het origineel | offline-downloads (B03-011) horen bij de mobiele clients (`jelly-leon-clients`) |
| Plugin-instellingen | dashboard `plugins`, `plugins/:pluginId`, route `configurationpage?name=…` | upstream laadt HTML/JS-configuratiepagina's van serverplugins | **zonder webpatch** bruikbaar door de Jelly Leon-plugin |
| Web-configuratie | `config.json` (`menuLinks`, `plugins`, `themes`, `servers`, `multiserver`) via `scripts/settings/webSettings.js` | menukoppelingen en webplugins zonder broncodewijziging | `menuLinks` → Hub/MediaGuard; `plugins` → `src/plugins/jellyLeon` |
| Webplugins | `components/pluginManager.js` (via `config.json` of `window`) | 14 ingebouwde plugins (spelers, screensavers, SyncPlay, Chromecast, …) | eigen webplugin in `src/plugins/jellyLeon/` (fork-eigen pad) |
| Versie/clientmatrix, updatecentrum | — | — | **Hub-UI** (niet in deze repo, ADR-0004) |

## 6. Upstream-workflows (zie ADR-0007)

Gemeten met `tools/jelly-leon-web/workflow_check.py --overzicht`:

| Workflow | Triggers | Upstream-geheimen | Onbewaakt bereikbaar in de fork |
|---|---|---|---|
| `__automation.yml` | workflow_call | JF_BOT_TOKEN | via aanroeper (die is bewaakt) |
| `__codeql.yml` | workflow_call | — | — |
| `__deploy.yml` | workflow_call | CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN | via aanroeper (bewaakt) |
| `__job_messages.yml` | workflow_call | JF_BOT_TOKEN | via aanroeper (bewaakt) |
| `__package.yml` | workflow_call | — | — |
| `__quality_checks.yml` | workflow_call, workflow_dispatch | — | 0 |
| `pull_request.yml` | pull_request (`master`, `release*`), merge_group | — | 0 |
| `push.yml` | push (`master`, `release*`) | — | 0 |
| `schedule.yml` | schedule, workflow_dispatch | JF_BOT_TOKEN | 0 (`contains(github.repository, 'jellyfin/')`) |

Gevolg: in v10.11.11 is **geen guard-patch nodig**. De fork-branches (`main`, `ccr-**`, `sync/**`, `release/**`)
starten `push.yml`/`pull_request.yml` niet (die luisteren naar `master` en `release*`; `release/…` valt daar niet
onder). Overige upstream-config: `.github/renovate.json` (alleen actief met de Renovate-app), `.github/CODEOWNERS`
(upstream-team; zonder effect in de fork) — ongewijzigd.

## 7. Delta-matrix B03 ↔ webclient (bestaand / onvolledig / ontbrekend)

| B03-taak | Webaandeel | Stand | Toelichting |
|---|---|---|---|
| B03-001 Forkstrategie en licentie | fork, CI, GPL, sync, compat | **onvolledig → in P0 aangevuld** | fork + forkregels + CI + sync + smoketest gebouwd; echte clients/GitHub-runs ontbreken |
| B03-002 Universele bibliotheek | bibliotheek-UI | bestaand (upstream) | geen webwerk tot de server-overlay er is |
| B03-003 Clients | webclient/tv-browser, PWA | bestaand (upstream, oude browsers ondersteund) | echte tv's/telefoons NIET GEVALIDEERD (D15) |
| B03-004 Transcoding planner | hardware-lane tonen | onvolledig | `playerstats` toont transcode-redenen, niet de lane |
| B03-005 Beste kwaliteit per apparaat | kwaliteitslabel, why-transcode | onvolledig | redenen bestaan; label ontbreekt |
| B03-006 Metadata/anime | — | n.v.t. web (server) | — |
| B03-007 Intro/recap/credits | overslaan-knop | **bestaand** (mediasegmenten) | segmentprovider is serverwerk |
| B03-008 Scènezoeker | resultaten + afspelen op tijdcode | ontbrekend | ontwerp FORK_STRATEGIE §4 (JLW-0002) |
| B03-009 MediaGuard | knop + leverstatus | ontbrekend | ontwerp FORK_STRATEGIE §4 (JLW-0001) + `menuLinks` |
| B03-010 Accounts/parental | zoeken/thumbnail/download respecteren ACL | bestaand voor zoeken (server); thumbnails/download = serverkwestie | smoketest: kinderprofiel vindt titel niet (UI + API) |
| B03-011 Offline downloaden | — | n.v.t. web (mobiele clients) | browserdownload bestaat upstream |
| B03-012 Live-tv/DVR | conflict-UI | onvolledig | upstream gids/opnames bestaan |
| B03-013 Beheer en terugkeer upstream | sync, patch stack, compat | **onvolledig → in P0 aangevuld** | `upstream-sync.yml` + `upstream_sync.py`; syncproef v12.4 faalt terecht |

## 8. Risico's en open punten

- **GitHub-archiefafhankelijkheid** (`classlist.js`): bouwomgevingen zonder toegang tot `github.com`-archieven kunnen
  `npm ci` niet uitvoeren (in deze omgeving: HTTP 403; de serverfork liep hier ook op vast). GitHub Actions heeft die
  toegang wel. Lokaal opgelost zonder repowijziging (BOUWVERIFICATIE §2).
- **Node 20 EOL** upstream; v12.x eist Node 24 → toolchainbesluit samen met de server (.NET 10).
- **Afhankelijkheden met advisories** (§3) — niet zelf patchen in P0; beoordelen bij sync of als geregistreerde patch.
- **v12.4 `workflow_run.yml`** geeft upstream-geheimen zonder guard door → bij overname eerst een guard-patch.
- **Afbeeldingen zonder token** (upstream-server) raken B03-010 (thumbnail-lek) — serverfollowup, geen webfix.
