# TrueNAS Custom App — jelly-leon-web

**Er is geen eigen Custom App voor jelly-leon-web.** De webclient wordt meegebouwd in de image
`ghcr.io/lvos04/jelly-leon` en door de Jellyfin-server zelf geserveerd op `http://<NAS-adres>:<hostpoort>/web/`
(contract 1.2 §2 en §2.3: app `jelly-leon` = "server incl. web-client", containerpoort 8096; ADR-0008).

- Installeren, bijwerken en terugzetten: uitsluitend via de standaard TrueNAS Custom App **`jelly-leon`** — formulier en
  velden staan in `lvos04/jelly-leon` → `deploy/truenas/CUSTOM_APP.md`. Normaal doet het platform dat via de TrueNAS-API
  vanuit de Hub-UI; nooit via YAML, *Install via YAML*, `custom_compose_config` of docker compose.
- Er is dus ook **geen formulier, geen poort, geen opslag en geen omgevingsvariabele** voor deze repo om in te vullen.
- Web-configuratie (`config.json` in de image: koppelingen naar Hub/MediaGuard, eigen webplugin) wordt door de
  jelly-leon-image gezet met waarden uit het dienstenregister van de Hub — nooit hard-gecodeerde adressen (D03 is
  onbekend tot de onboarding-wizard het vastlegt of meet).
- Wat deze repo oplevert: de broncode (build-context voor de jelly-leon-image) en per CI-run het artefact
  `jelly-leon-web-<forkversie>-<commit>.tar.gz` met `.sha256` en `bouwinfo.json` (zie `.github/workflows/jelly-leon-web-ci.yml`).

- Sinds P4-0 (v12.4, ADR-0011) hoort de web-stage van de `jelly-leon`-image te bouwen met `NODE_IMAGE` =
  `toolchain.node_image` uit `tools/jelly-leon-web/baseline.json` (Node 24.22.2 op digest) en `.npmrc` vóór `npm ci`
  mee te kopiëren (12.x zet daar `engine-strict`, `ignore-scripts` en `min-release-age`). Dat aanpassen gebeurt in
  `lvos04/jelly-leon`, niet hier.

Status: niets hiervan is op een echte TrueNAS geïnstalleerd of getest — **NIET GEVALIDEERD (echte NAS)**.
