# Forkstrategie jelly-leon-web (B03-001, webdeel)

Versie P0 · 2026-11-09 · repo `lvos04/jelly-leon-web` · basis `jellyfin/jellyfin-web` **v10.11.11**
(`35c0793ece3adbd247eab290ae1effab851f3d37`) · licentie **GPL-2.0-or-later** (upstream `package.json`/`LICENSE`) ·
hoort bij de serverfork `lvos04/jelly-leon` (zelfde basisversie, zelfde forkregels).

Dit document is de samenvatting voor de webclient. De besluiten staan in [`docs/adr/`](../adr/README.md)
(ADR-0001…0009), de bewaking in `tools/jelly-leon-web/` en in CI (`.github/workflows/jelly-leon-web-ci.yml`).
Het serverdeel staat in `lvos04/jelly-leon` → `docs/platform-v2/FORK_STRATEGIE.md`.

## 0. In het kort

- **Stand P0: 0 core-patches.** De broncode is byte-gelijk aan upstream v10.11.11; alles wat van ons is staat in
  fork-eigen paden (`tools/jelly-leon-web/fork_paths.txt`). Gemeten: `npm ci`, eslint, stylelint, tsc, vitest
  (160/160), productiebuild en es-check slagen; de web-client-smoketest in Chromium tegen de officiële server slaagt
  21/21 voor zowel de fork-build als de stock-webclient (zie [`BOUWVERIFICATIE_P0.md`](BOUWVERIFICATIE_P0.md)).
- **Uitbreidingen eerst buiten de webcode**: serverplugin + plugin-configuratiepagina's, web-configuratie
  (`config.json`), fork-eigen modules; pas als dat niet volstaat een **kleine, geïsoleerde haak** in een
  upstream-bestand, geregistreerd in [`PATCHES.md`](PATCHES.md) en bewaakt door CI.
- **Beveiliging nooit in de webclient**: rollen, kinderprofiel-ACL en zichtbaarheid worden op de server afgedwongen;
  de webclient toont alleen wat de server teruggeeft.
- **Branding**: technische identiteit blijft "Jellyfin" (`jellyfin-web`, versie 10.11.11); alleen de zichtbare naam
  wordt later "Jelly Leon". **In P0 is niets aan branding gewijzigd** (ADR-0003).
- **Geen eigen image of Custom App**: de webclient wordt meegebouwd in `ghcr.io/lvos04/jelly-leon` (ADR-0008).

## 1. Plaats van de webclient in het platform

```text
 Hub-UI (ai-server-manager, Next.js)            jelly-leon-web (deze repo, in de browser/tv-browser)
   platformschermen: versie & clientmatrix,       kijkervaring: bibliotheek, zoeken, detail, speler,
   updatecentrum, MediaGuard-overzicht,           + kleine in-context-elementen (knop, label, scènes)
   goedkeuringen, problemen                                 │  Jellyfin-API + /media/v1/* (zelfde origin)
            │ deep-link ──────────────────────────────────► │
            ▼                                               ▼
   Hub-API /api/v1 ◄──── service-token/JWT ───── jelly-leon (server + Jelly Leon-plugin, GPL)
                                                  │  /media/v1/version|search|scenes|mediaguard/request|…
                                                  ├──► MediaGuard (eigenaar wanted/kwaliteit; via Hub-goedkeuring)
                                                  └──► zoeken-en-persoonlijke-ai (scène-index, ACL per gebruiker)
```

- **Platform- en beheerschermen horen in de Hub-UI** (contract §1: "alle schermen van alle nieuwe diensten staan in
  die ene Hub-UI"). Dus *Versie- en clientcompatibiliteitspagina* (B03-001), *Updatecentrum* (B03-013), overzicht van
  MediaGuard-aanvragen, goedkeuren (R2) — niet in deze repo (ADR-0004).
- **In de webclient** blijft alleen wat bij het kijken zelf hoort en niet zinvol in de Hub kan: een knop per titel,
  een kwaliteitslabel in de speler, scène-resultaten die op een tijdcode afspelen. Elk element praat uitsluitend met de
  eigen server (`/media/v1/*` van de Jelly Leon-plugin, zelfde origin, Jellyfin-sessietoken); de server praat met de
  Hub/MediaGuard/zoekdienst. De webclient krijgt nooit een Hub-, MediaGuard- of TrueNAS-geheim.

## 2. Uitbreidingsladder (ADR-0001)

Elke nieuwe webfunctie volgt deze volgorde; een stap verder mag pas als de vorige aantoonbaar niet volstaat
(motivatie in het patchregister: veld *Waarom geen plugin/configuratie*):

| # | Mechanisme | Waar | Telt als patch? | Voorbeelden |
|---|---|---|---|---|
| 1 | Server-/upstream-configuratie | Jellyfin-dashboard, gebruikersbeleid, `BrandingOptions` | nee | ouderlijk toezicht, mediasegmenten, login-disclaimer |
| 2 | Eigen serverplugin + **plugin-configuratiepagina** | `lvos04/jelly-leon` `plugins/` (API `/media/v1/*`, pagina via upstream-route `configurationpage?name=…`) | nee (andere repo) | instellingen Jelly Leon, MediaGuard-koppeling, kwaliteitsregels |
| 3 | **Web-configuratie** `config.json` | in de image gezet door `lvos04/jelly-leon` (`/jellyfin/jellyfin-web/config.json`) | nee (deploy-configuratie) | `menuLinks` (link "Hub", "MediaGuard"), `plugins` (eigen webplugin laden), `themes` |
| 4 | **Fork-eigen webcode** | `src/jelly-leon/**`, `src/plugins/jellyLeon/**`; teksten via `globalize.loadStrings` in eigen bestanden | nee (fork-eigen pad) | componenten, API-hooks, Nederlandse teksten |
| 5 | **Kleine, geïsoleerde haak** in een upstream-bestand | bv. één import + één aanroep | **ja → `PATCHES.md` (JLW-NNNN)** | knop op detailpagina, extra zoeksectie |

Regels voor stap 5 (gecontroleerd door `patch_register_check.py` en review):
- zo klein mogelijk: de logica staat in fork-eigen code, de haak alleen roept aan; liever een algemeen uitbreidingspunt
  dat upstream kan overnemen (veld *Upstream-PR-kans*);
- nooit `LICENSE`/`CONTRIBUTORS.md`; nooit `package.json`-`name`/`version` (technische identiteit);
- upstream-stringbestanden (`src/strings/*.json`) niet wijzigen — eigen teksten in een eigen bestand (stap 4);
- elke haak heeft een test (vitest voor de fork-eigen module + web-client-smoketest);
- de functie degradeert veilig: biedt de serverplugin de capability niet (`GET /media/v1/…` → `capability_unavailable`
  of 404/501), dan toont de webclient "niet beschikbaar"/niets — **nooit gesimuleerd succes** (contract §6).

## 3. Scheiding en bewaking

| Wat | Hoe bewaakt | Waar |
|---|---|---|
| Afwijkingen van upstream | `patch_register_check.py`: elke afwijking buiten fork-eigen paden moet in `PATCHES.md` | CI-job *Forkregels* |
| Technische identiteit | `check_fork_consistency.py`: `package.json`/`package-lock.json` = `jellyfin-web` 10.11.11; basis zit in de historie | CI-job *Forkregels* |
| Zichtbare naam (P0) | web-client-smoketest: `<title>Jellyfin</title>` en `manifest.json` `name` = "Jellyfin" | CI-job *web-e2e* |
| Upstream-geheimen | `workflow_check.py`: elk upstream-geheim achter een repository-guard, ook via herbruikbare workflows | CI-job *Forkregels* + sync |
| Eigen workflows | `workflow_check.py`: acties op commit-SHA, images op digest, exacte Node-versie, `permissions` | CI-job *Forkregels* |
| Bewijs | `check_fork_consistency.py`: `EVIDENCE.json` volgens contract §11, nooit "Gereed"/"Geslaagd" | CI-job *Forkregels* |

## 4. Waar de B03-uitbreidingen in de webclient komen (ontwerp; niets hiervan is in P0 gebouwd)

| Uitbreiding (B03) | Server (lvos04/jelly-leon e.a.) | Webclient (deze repo) | Ladder | Bestaat upstream al? |
|---|---|---|---|---|
| **MediaGuard-verzoeklink** (B03-009) — knop "Vraag aan / zoek betere versie" + leverstatus per titel | plugin: `GET /media/v1/mediaguard/status?itemId=`, `POST /media/v1/mediaguard/request` (Idempotency-Key; actie gaat als voorstel via de Hub, R2-goedkeuring; MediaGuard-noodstop en kwaliteitsregels blijven leidend) | fork-eigen `src/jelly-leon/mediaguard/` + **haak JLW-0001** in `src/controllers/itemDetails/index.js`; algemene link naar Hub/MediaGuard via `config.json` `menuLinks` (geen patch) | 3 + 4 + 5 | nee (alleen `menuLinks`-mechanisme) |
| **Scènezoeker** (B03-008) — resultaat met tijdcode, titel, reden; "afspelen vanaf hier" | plugin: `GET /media/v1/scenes?q=` → zoekdienst met **ACL per gebruiker** (Hub-JWT); zonder transcript/permissie: lege lijst, nooit gegokte resultaten | fork-eigen `src/jelly-leon/scenes/` (afspelen via upstream `playbackManager.play({ids, startPositionTicks})`) + **haak JLW-0002**: één extra sectie in `SearchResults.tsx` óf één route in `asyncRoutes/user.ts` | 4 + 5 | nee |
| **Kwaliteitsweergave** (B03-004/005) — Auto/Direct/Transcode, reden, hardware-lane, kwaliteitslabel ("origineel DV" / "fallback SDR") | upstream `PlaybackInfo`/`TranscodingInfo` + plugin `GET /media/v1/transcode/capabilities` | upstream *Playback Info* (`playerstats`) toont al afspeelmethode, codecs en transcode-redenen (geen patch); alleen label + hardware-lane via fork-eigen `src/jelly-leon/quality/` + **haak JLW-0003** in `playerstats.js` (de upstream-regel voor `HardwareAccelerationType` staat daar uitgecommentarieerd) | 1 + 4 + 5 | **deels** |
| **Kinderprofiel-ACL in zoekresultaten** (B03-010) | **volledig op de server**: Jellyfin-gebruikersbeleid (bibliotheken, leeftijdsclassificatie, tags) voor `/Items`-zoeken; scène-index filtert per gebruiker; afbeeldingen/downloads apart beoordelen (zie §6) | **geen eigen filter als beveiliging**; alleen tonen wat de server geeft. Bewaking: smoketest-stap "kinderprofiel ziet de titel niet" (UI + API) | 1 + 2 | **ja** (gebruikersbeleid; gemeten in de smoketest) |
| Instellingen van al het bovenstaande | plugin-configuratiepagina (Dashboard → Plugins → Jelly Leon), upstream-route `configurationpage?name=` | niets | 2 | ja (mechanisme) |
| Versie/clientmatrix (B03-001-scherm), updatecentrum (B03-013) | plugin `GET /media/v1/version` (bestaat in jelly-leon) | niets — scherm staat in de **Hub-UI** | — | n.v.t. |

De ID's JLW-0001…0003 zijn een planning; ze worden pas in het register opgenomen als de haak echt bestaat.

## 5. Branding (ADR-0003)

- **Technische identiteit blijft "Jellyfin"**: pakketnaam `jellyfin-web`, versie = upstream-versie, `__PACKAGE_JSON_NAME__`/
  `__PACKAGE_JSON_VERSION__` in de bundel, `MediaBrowser`/`X-Emby-*`-headers, clientnaam `appName` = "Jellyfin Web"
  (`src/components/apphost.js`) richting server, localStorage-sleutels (`jellyfin_credentials`), routes en de
  upstream-`config.json`-structuur. Clients, plugins en de server blijven de
  webclient als "Jellyfin Web" zien.
- **Alleen de zichtbare naam mag later "Jelly Leon" worden** (paginatitel, `manifest.json` `name`/`short_name`, logo,
  teksten) — eerst via serverconfiguratie (`BrandingOptions`: login-disclaimer, eigen CSS), dan via `config.json`/eigen
  thema, pas daarna via een geregistreerde patch. "Gebaseerd op Jellyfin" en de GPL-credits blijven zichtbaar.
- **In P0 is niets gewijzigd**; de smoketest controleert dat `<title>Jellyfin</title>` en `manifest.json` `name`
  "Jellyfin" nog gelden, zodat een stille brandingwijziging opvalt.

## 6. Bekende upstream-gedragingen die de webclient niet kan oplossen

- Gemeten tegen de officiële server 10.11.11 zonder token (2026-11-09): `GET /Items/{id}` → 401 en
  `GET /Items/{id}/Download` → 401, maar `GET /Items/{id}/Images/Primary` → **404** (geen 401: de afbeeldingsroute
  controleert geen aanmelding; 404 omdat het testnummer geen afbeelding heeft). Wie een item-ID kent, kan dus
  afbeeldingen ophalen zonder profielcontrole; zie ook de streamwaarneming in ADR-0009 van `lvos04/jelly-leon`. Voor de
  B03-010-acceptatie ("geen adult media via thumbnail cache of download-API") is dat een **serverkwestie**; de webclient
  voegt er niets aan toe of af. Opgenomen als followup voor de server.
- De webclient bewaart de inlog (`jellyfin_credentials`) in de browser; bij gedeelde apparaten (kinderprofiel) moet
  "Mij onthouden" bewust uit — gebruikersinstructie, geen patch.

## 7. Upstream-sync en upgradepad (ADR-0006, B03-013)

- `upstream-sync.yml` (wekelijks + handmatig) → nieuwste stabiele `jellyfin-web`-tag per spoor (`patch` 10.11.x,
  `nieuwste` nu **v12.4**) → branch `sync/<tag>` (merge binnen de reeks, anders **herbasis**: upstream-tag + fork-eigen
  paden + geregistreerde patches) → forkregels, eslint, stylelint, tsc, vitest, build, es-check en smoketest tegen de
  officiële server **van dezelfde versie**. Elke fout = workflow faalt (EX48); **nooit automatisch naar productie**.
- Server en web horen samen naar dezelfde upstream-tag; de image van `lvos04/jelly-leon` bouwt de web-client mee.
- **Echte syncproef v12.4 (2026-11-09, lokaal, niets gepusht)**: gewone merge 30 conflicten (upstream-backports),
  herbasis 0 conflicten, maar de sync faalt terecht op (1) `workflow_run.yml` in v12.4 dat upstream-geheimen zonder
  repository-guard doorgeeft en (2) de eis Node ≥ 24 / npm ≥ 11. Zie
  `test-evidence/p0-upstream-syncproef-v12.4.json`.

## 8. Bouwen, testen en CI (zie BOUWVERIFICATIE_P0.md)

| Wat | Waar | Stand P0 (lokaal gemeten, 2026-11-09) |
|---|---|---|
| `npm ci` (Node 22.23.4, npm 10.9.9) | CI-jobs *kwaliteit*/*build* | 1724 pakketten; lokaal alleen met integriteitsgecontroleerde cache voor `classlist.js` (GitHub-archief geblokkeerd in deze bouwomgeving) |
| eslint / stylelint / tsc | job *kwaliteit* | 0 fouten (eslint 103 upstream-waarschuwingen) / 0 / 0 |
| vitest | job *kwaliteit* | 12 bestanden, 160/160 |
| productiebuild + es-check | job *build* | geslaagd (2 upstream-groottewaarschuwingen), 2317 bestanden, ES5 in orde |
| forkregels + 31 tool-tests | job *forkregels* | geslaagd |
| web-client-smoketest | job *web-e2e* | fork 21/21, stock 21/21 (Sim-getest) |
| echte GitHub-runs | — | **NIET GEVALIDEERD** (nog niet op GitHub uitgevoerd) |

## 9. Licentie (GPL)

`LICENSE` en `CONTRIBUTORS.md` blijven byte-gelijk aan upstream (CI). Elke verspreide build is te herleiden tot een
commit in deze repo (artefact `bouwinfo.json`, OCI-labels in de jelly-leon-image). De zichtbaarheid van de repo's
(publiek/privé) vóór de eerste image-release is een open gebruikersbesluit (zie ADR-0004 in `lvos04/jelly-leon`).
