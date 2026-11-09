# ADR-0011 — Webclient naar jellyfin-web 12.x (P4-0): herbasis, Node 24, guard, zichtbare naam en haakpunten

- **Status:** Aanvaard (P4-0, B03-014 webdeel, 2026-11-09). Zelfde onderwerp en nummer als ADR-0011 in
  `lvos04/jelly-leon` (server naar 12.x vóór P4, besluit 2 van de gebruiker); dit is het webdeel. Vervangt het
  Node 22-deel van ADR-0009.
- **Context:** Besluit van de gebruiker (2026-11-09): server en web gaan vóór P4 naar de nieuwste stabiele Jellyfin
  12.x; B03 wordt direct op 12.x gebouwd. BG-02: geen release meer op 10.11.11, de eerste Jelly Leon-release is op
  12.x. Bouwplan B03 2.0 §8.2 en B03-014 schrijven de werkwijze voor: `upstream_sync.py merge --tag v12.x` (herbasis),
  de twee terechte weigeringen uit de proef van P0 oplossen (`workflow_run.yml` zonder guard; Node ≥ 24 / npm ≥ 11),
  layouts legacy/modern (Modern standaard), de haken JLW-0001…0003 opnieuw lokaliseren en de zichtbare naam "Jelly Leon"
  als enige merkwijziging (contract 1.2, JW1/JW2).

## Besluit

1. **Doelversie: v12.4** — bepaald met `upstream_sync.py kies --spoor nieuwste --spoor patch` op 2026-11-09:
   `nieuwste` = v12.4 (v12.0…v12.4 nieuwer), `patch` = geen kandidaat. Web-tag v12.4 = `0a580ce8df89`, dezelfde tag als
   de server (`83d0d0e7f76e`). Nooit rc/beta.
2. **Herbasis met de sync-tooling, niets met de hand.** `upstream_sync.py merge --tag v12.4 --methode herbasis`:
   0 conflicten (0 core-patches om mee te nemen), merge-commit met twee ouders (vorige forkstand + upstream-tag),
   `baseline.json` → v12.4 / forkversie `12.4.0-jl.0`. `package.json` blijft upstream (`jellyfin-web` 12.4.0, ADR-0005).
   De twee door de tool gemaakte commits kregen alleen de verplichte attributieregel erbij (zelfde boom en ouders).
3. **Guard als geregistreerde patch JLW-0001** op `.github/workflows/workflow_run.yml` (nieuw sinds v12.0): de jobs
   `automation` en `deploy` krijgen `github.repository == 'jellyfin/jellyfin-web'` als conjunct. Daarbij is
   `workflow_check.py` strenger geworden: een guard telt alleen als conjunct op het hoogste niveau (`guard || x`
   bewaakt niets). ADR-0007 voorzag precies deze route.
4. **Toolchain Node 24.22.2 / npm 11.19.1** (LTS "Krypton", nieuwste 24.x op 2026-11-09; upstream `.nvmrc` = 24,
   `engines` node ≥ 24, npm ≥ 11, `engine-strict`). Node 26 (ook LTS) is bewust niet gekozen: upstream bouwt en test
   op 24. Eén bron: `tools/jelly-leon-web/baseline.json` → `toolchain` met `node`, `npm`, `node_image`
   (`docker.io/library/node:24.22.2-bookworm-slim@sha256:01d566e8…70e9`) en `server_image`
   (`docker.io/jellyfin/jellyfin:12.4@sha256:fea863d0…b771`), gemeten met `docker buildx imagetools inspect`.
   `check_fork_consistency.py` eist dat `node-version` in beide eigen workflows, de build-container, `JLW_SERVER_IMAGE`
   en de standaardimage van de smoketest exact deze waarden zijn en dat ze aan `engines` voldoen. De CI-job *build*
   draait in `node_image` — dezelfde image die de web-stage van `lvos04/jelly-leon` moet gebruiken (`NODE_IMAGE`).
   Een upstream-sync die een nieuwere toolchain eist, faalt daardoor met een duidelijke melding (EX48), nooit stil.
5. **Zichtbare naam "Jelly Leon" = patch JLW-0002, de enige merkwijziging.** Vijf regels, elk exact
   `Jellyfin` → `Jelly Leon`: `<title>` en `application-name` in `src/index.html`, `name`/`short_name` in
   `src/manifest.json`, de standaardtitel in `src/scripts/libraryMenu.js`. Ladder (ADR-0001/ADR-0003): server-
   `BrandingOptions` en `config.json` kennen geen naam, dus een patch. Bewust **niet** gewijzigd: technische identiteit
   (`package.json`, clientnaam "Jellyfin Web" en versie richting de server, `MediaBrowser`-header, localStorage-
   sleutels), upstream-stringbestanden ("Jellyfin Server" e.d.), het logo/woordmerk en de favicons (afbeeldingen uit
   `@jellyfin/ux-web`; een eigen logo vraagt een keuze van de gebruiker). In 12.x wordt de browsertitel en de naam in
   de Modern-werkbalk na het laden de **servernaam** (`ServerName`, per installatie instelbaar; upstream-gedrag
   UG-WEB-19); "Jelly Leon" is de titel daarvóór en de terugval. `check_fork_consistency.py` bewaakt via
   `baseline.json` → `zichtbare_naam` dat de merkbestanden regel voor regel alleen in de naam afwijken.
6. **Layouts.** In 12.x heet `apps/stable` nu `apps/legacy` en `apps/experimental` nu `apps/modern`;
   `apphost.getDefaultLayout()` geeft Modern; Legacy kiest de gebruiker met de instelling `layout` = `desktop-legacy`
   (of `mobile-legacy`, `tv`). De web-client-smoketest doorloopt elke gebruikersreis in **beide** layouts en controleert
   welke actief is (Modern: MUI-AppBar; Legacy: geen). Webhaken moeten in beide layouts werken of hun beperking
   vastleggen (bijv. H-SYNCPLAY-MENU alleen Modern tenzij BG-14).
7. **Haken opnieuw beoordeeld, nog niet gebouwd.** De P0-planning "JLW-0001…0003" is vervallen: nummers worden pas bij
   een echte patch toegekend (bouwplan §10.11), dus JLW-0001/0002 zijn nu de guard en de naam. De haken heten met hun
   werknaam (H-ITEMDETAILS, H-ROUTE, H-PLAYBACKINFO, H-HOME, H-SYNCPLAY-MENU, H-DEVICEPROFILE, H-SKIPTEXT,
   H-SEGACTION, H-SYNCPLAY-SKIP); hun plek op v12.4 staat in `PATCHES.md`. Gemeten verschillen met P0: de detailpagina
   zit in `src/apps/legacy/controllers/itemDetails/index.js` en dient beide layouts (één haak volstaat); routes bestaan
   per layout (`apps/{modern,legacy}/routes/asyncRoutes/user.ts`); de uitgecommentarieerde `HardwareAccelerationType`-
   regel in `playerstats.js` bestaat niet meer.
8. **Register van upstream-gedrag, webdeel** (`docs/platform-v2/UPSTREAM_GEDRAG.md`, B03-019 a): eigen reeks
   **UG-WEB-<n>** zodat nummers niet botsen met het serverregister (UG-F1…F6-<n> in jelly-leon). Elke regel heeft een
   anker (regex) in het upstream-bestand; `upstream_gedrag_check.py` laat CI en de sync falen als een anker verdwijnt
   of een `UG-WEB`-verwijzing geen regel heeft. Op v12.4 vindt hij alle 19 ankers; tegen de oude 10.11.11-boom falen
   er 11 — precies de verhuizingen waarvoor deze ADR bestaat.
9. **Legacy-authenticatie** staat in de 12.4-server standaard uit (BG-01: blijft uit). De smoketest meet het:
   `X-Emby-Token`, `api_key=` en `X-Emby-Authorization` → 401, `Authorization: MediaBrowser … Token=…` → 200. De
   webclient gebruikt alleen de laatste; afspelen werkt in beide layouts.

## Gevolgen

- Deze repo staat op v12.4. `lvos04/jelly-leon` moet voor zijn image dezelfde stand overnemen (andere repo, andere
  bouwer; followups): `web_upstream_tag`/`web_upstream_commit`/`web_fork_commit` in zijn `baseline.json`, `NODE_IMAGE`
  = `toolchain.node_image` hiervandaan, en in de web-stage `.npmrc` mee kopiëren vóór `npm ci` (in 12.x staan daar
  `engine-strict`, `ignore-scripts=true` en `min-release-age=7`; nu kopieert de stage alleen `package.json` en
  `package-lock.json`). Wie op de jelly-leon-image `<title>Jellyfin</title>` controleert, moet "Jelly Leon" verwachten.
- **Upgradeproef (JLT-60/61 webdeel, `upgrade_proef.py`, CI-job `upgrade-e2e`):** een gevulde 10.11.11-datamap
  migreert naar 12.4 zonder verlies van kijkgegevens (5 gebruikers, 0 verschillen) en de webclient werkt erop in beide
  layouts; terugzetten met de oude image + een kopie werkt. **Bevinding:** alleen de oude stock-image op de gemigreerde
  data meldt zich gezond maar aanmelden geeft HTTP 500 (geen blijvende schade). JLT-61 (b) vraagt "faalt zichtbaar met
  een duidelijke melding": dat moet de jelly-leon-image doen (downgradecontrole bij het starten); tot dan Sim-mislukt.
- `upstream-sync.yml` draait voortaan op Node 24.22.2 en controleert ook de ankers; de volgende stap is 12.4 → 12.y
  (JLT-67) zodra upstream een nieuwere tag publiceert. Methode dan `herbasis` (andere major.minor).
- Node 22-toolchain (ADR-0009) is voor deze repo vervallen; de afhankelijkheden blijven upstream (geen eigen updates;
  `npm audit` informatief in `INVENTARIS.md`).
- Overnemen in de standaardbranch en een release blijven handmatige R2-stappen (ADR-0006). Echte apparaten en de NAS:
  NIET GEVALIDEERD.

## Gemelde contractpunten (veiligste lezing gekozen)

1. Het bouwplan noemt de geplande webhaken "JLW-0001…0003" en later "opvolger van JLW-0001" (B03-048, B03-057), maar
   §10.11 zegt dat nummers pas bij de echte patch in volgorde worden toegekend. Gekozen: §10.11 volgen; JLW-0001/0002
   zijn de guard en de naam, de haken heten met hun werknaam. Verzoek aan de eigenaar van het bouwplan: "opvolger van
   JLW-0001" vervangen door "H-ITEMDETAILS".
2. B03-019 nummert upstream-gedrag als `UG-<functie>-<n>`; voor het webdeel is gekozen voor `UG-WEB-<n>` met de functie
   in een kolom, om botsingen met het serverregister van jelly-leon te voorkomen.
3. "Bouwimages op digest bijwerken": deze repo heeft geen eigen image (ADR-0008). Gekozen: de Node-image op digest
   vastleggen in `baseline.json` → `toolchain.node_image`, de CI-build daarin draaien en lokaal bewijzen dat `npm ci` +
   productiebuild daarin slagen; `NODE_IMAGE` in jelly-leon zelf aanpassen is werk van die repo.
