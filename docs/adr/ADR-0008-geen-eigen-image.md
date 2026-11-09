# ADR-0008 — Geen eigen image of Custom App: de webclient zit in `ghcr.io/lvos04/jelly-leon`

- **Status:** Aanvaard (P0, 2026-11-09)
- **Context:** De algemene kwaliteitseis vraagt per repo een alles-in-één image, `deploy/truenas/CUSTOM_APP.md`, een
  manifest en `.env.example`. Contract §2 noemt echter één app `jelly-leon` voor "jelly-leon(+web)": *server incl.
  web-client*, image `ghcr.io/lvos04/jelly-leon`, containerpoort 8096. De webclient is statische HTML/JS die Jellyfin
  zelf serveert (`/web/`, uit `/jellyfin/jellyfin-web`). De serverfork bouwt hem mee (`deploy/allinone/Dockerfile`,
  stage `web`, build-context `jelly-leon-web`).

## Besluit

- **Geen eigen image, geen eigen Custom App, geen eigen manifest** voor jelly-leon-web. Een tweede app of manifest
  voor dezelfde dienst zou het contract (één app per dienst) en de manifeststandaard (één image) breken.
- Wat deze repo levert: (1) de broncode als build-context voor de jelly-leon-image en (2) een CI-artefact
  `jelly-leon-web-<forkversie>-<commit>.tar.gz` + `.sha256` + `bouwinfo.json` (reproduceerbaar ingepakt).
- `deploy/truenas/CUSTOM_APP.md` legt alleen uit dat er geen eigen formulier is en verwijst naar het formulier van
  `jelly-leon`; `.env.example` documenteert de build-variabelen (geen runtime-variabelen, geen geheimen).
- Web-configuratie (`config.json`: `menuLinks` naar Hub/MediaGuard, eigen webplugin) zet de jelly-leon-image; die
  waarden komen uit de Hub (dienstenregister), nooit hard-gecodeerde adressen (D03 onbekend).

## Gevolgen

- Installatie blijft uitsluitend de standaard TrueNAS Custom App `jelly-leon` (contract 1.1; ongewijzigd in 1.2 §2.3);
  compose wordt hier niet gebruikt.
- Gemeld als contract-issue (generieke "image per repo"-eis ↔ §2 "jelly-leon(+web)").
- Followup voor `lvos04/jelly-leon`: de web-stage kan het CI-artefact gebruiken i.p.v. zelf `npm ci` te draaien
  (lost ook de GitHub-archief-403 in beperkte bouwomgevingen op).
- Stand contractronde 1.2: volgens `lvos04/jelly-leon` (`docs/adr/ADR-0008-alles-in-een-image.md`, "P0-afronding")
  is de volledige jelly-leon-image daar inmiddels lokaal gebouwd **mét** de echte web-build van deze repo (commit
  `2795f3365`, `npm ci` incl. het `classList.js`-archief); in hun GitHub-CI wordt de web-stage nog vervangen door de
  upstream-dist. Deze repo staat inmiddels publiek op GitHub, dus de web-stage kan daar zonder leestoken een
  `git archive` van deze repo gebruiken (followup voor `lvos04/jelly-leon`, niet in deze repo).
