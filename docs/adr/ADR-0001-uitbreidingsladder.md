# ADR-0001 — Uitbreidingen via server, plugin-configuratie en web-configuratie; webpatch alleen als kleine haak

- **Status:** Aanvaard (P0, 2026-11-09)
- **Context:** B03 §5 ("Begin met een Jellyfin plugin/adapter … Maak fork pas wanneer onderbouwd nodig"), I06 stap 6–7,
  I24 stap 3 ("Sidecar/extension eerst"), B03-013 ("Patch stack minimal"). De B03-uitbreidingen die de webclient raken
  zijn: MediaGuard-verzoeklink (B03-009), scènezoeker (B03-008), kwaliteitsweergave (B03-004/005) en
  kinderprofiel-ACL in zoekresultaten (B03-010). Upstream jellyfin-web biedt zelf al uitbreidingsmechanismen:
  plugin-configuratiepagina's van serverplugins (route `configurationpage?name=…`), `config.json` (`menuLinks`,
  `plugins`, `themes`), webplugins via `pluginManager` en extra vertalingen via `globalize.loadStrings`.

## Besluit

Volgorde per functie; een stap verder alleen als de vorige aantoonbaar niet volstaat:

1. server-/upstream-configuratie (gebruikersbeleid, ouderlijk toezicht, `BrandingOptions`, mediasegmenten);
2. eigen serverplugin in `lvos04/jelly-leon` met API `/media/v1/*` en een **plugin-configuratiepagina**;
3. web-configuratie `config.json` (door de jelly-leon-image gezet — deploy-configuratie, geen bronwijziging);
4. fork-eigen webcode in `src/jelly-leon/**` en `src/plugins/jellyLeon/**` (eigen teksten via `globalize.loadStrings`);
5. **kleine, geïsoleerde haak** in een upstream-bestand (één import + één aanroep), geregistreerd als `JLW-NNNN` in
   `docs/platform-v2/PATCHES.md`, met test en beoordeelde upstream-PR-kans.

Altijd: beveiliging (rollen, kinderprofiel, zichtbaarheid) wordt op de server afgedwongen, nooit alleen in de webclient;
ontbreekt een capability op de server, dan toont de webclient "niet beschikbaar" — nooit gesimuleerd succes.
Plaatsing van de vier B03-uitbreidingen: `FORK_STRATEGIE.md` §4.

## Gevolgen

- P0: 0 core-patches (gemeten, `patch_register_check.py`).
- Verwachte haken in latere fasen: detailpagina (MediaGuard-knop), zoekresultaten/route (scènes), `playerstats`
  (kwaliteitslabel) — elk één regel, logica in fork-eigen code.
- Elke haak kan bij een upstream-sync conflicteren; dan faalt de sync zichtbaar (ADR-0006).

## Overwogen alternatieven

- *JavaScript-injectie in `index.html` door een serverplugin* (zoals community-"JS injector"-plugins) — verworpen: niet
  versiebeheerd in deze repo, omzeilt het patchregister, breekt stil bij upstream-wijzigingen en is een XSS-vector.
- *Webplugin die de DOM van upstream-pagina's manipuleert zonder haak* — alleen voor experimenten; fragiel bij elke
  upstream-wijziging, slecht testbaar. Een geregistreerde haak van één regel is eerlijker en beter bewaakt.
- *Alle B03-schermen in de webclient bouwen* — verworpen, zie ADR-0004.
