# ADR-0003 — Branding: alleen zichtbare naam "Jelly Leon"; technische identiteit `jellyfin-web`

- **Status:** Aanvaard (P0, 2026-11-09); uitgevoerd in P4-0 als patch JLW-0002 (ADR-0011)
- **Context:** Vaste keuze gebruiker en contract §1: "technische identiteit/API blijft 'Jellyfin' (clientcompatibiliteit);
  alleen de zichtbare naam is 'Jelly Leon'". Serverkant: `lvos04/jelly-leon` ADR-0003. De webclient meldt zich bij de
  server als client "Jellyfin Web" (`appName` in `src/components/apphost.js`) met pakketnaam/versie uit `package.json`
  (`__PACKAGE_JSON_NAME__`/`__PACKAGE_JSON_VERSION__`), gebruikt `MediaBrowser`/`X-Emby-*`-headers en de
  localStorage-sleutel `jellyfin_credentials`.

## Besluit

- **Blijft ongewijzigd:** `package.json` `name` = `jellyfin-web` en `version` = upstream-versie, clientnaam "Jellyfin Web",
  headers, localStorage-sleutels, routes, `config.json`-structuur, serviceworker-scope.
- **Mag later "Jelly Leon" heten (niet in P0):** paginatitel, `manifest.json` `name`/`short_name`, logo, teksten — eerst
  via serverconfiguratie (`BrandingOptions`), dan via `config.json`/eigen thema, pas daarna via een geregistreerde patch.
  "Gebaseerd op Jellyfin" en GPL-credits blijven zichtbaar; geen upstream-logo als eigen merk.
- **P0: niets aan branding gewijzigd.** Bewaking: `check_fork_consistency.py` (pakketnaam/-versie) en de
  web-client-smoketest (`<title>Jellyfin</title>`, `manifest.json` name "Jellyfin").

## Gevolgen

- Stock clients, serverplugins en de server zien de webclient ongewijzigd (B03-001-acceptatie).
- Bij de latere brandingstap moet de smoketest-stap bewust worden aangepast (zichtbaar in de diff), nooit stil.

## Aanvulling P4-0 (2026-11-09, ADR-0011)

De brandingstap is uitgevoerd als geregistreerde patch **JLW-0002** op de 12.4-basis: alleen `<title>`,
`application-name`, `manifest.json` `name`/`short_name` en de standaardtitel in `libraryMenu.js` heten "Jelly Leon".
De smoketest is bewust aangepast (fork verwacht "Jelly Leon", stock "Jellyfin") en controleert daarnaast dat de
webclient zich bij de server nog steeds als "Jellyfin Web" met de upstream-versie meldt. Logo en favicons blijven
voorlopig die van Jellyfin (geen eigen logo beschikbaar).
