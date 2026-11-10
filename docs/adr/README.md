# Architectuurbesluiten (ADR) — jelly-leon-web

Elke keuze in deze fork die afwijkt van "upstream jellyfin-web ongewijzigd laten" of die het platformcontract
(`docs/platform-v2/PLATFORM_CONTRACTEN.md`, versie 1.3 — byte-gelijke kopie, zie ADR-0012) interpreteert, staat hier als ADR. De serverfork
`lvos04/jelly-leon` heeft een eigen reeks (zelfde nummering waar het onderwerp overeenkomt).
Status: `Voorgesteld` → `Aanvaard` → (`Vervangen door ADR-xxxx`).

| ADR | Titel | Status |
|---|---|---|
| [ADR-0001](ADR-0001-uitbreidingsladder.md) | Uitbreidingen via server, plugin-configuratie en web-configuratie; webpatch alleen als kleine haak | Aanvaard |
| [ADR-0002](ADR-0002-fork-eigen-paden-en-patchregister.md) | Fork-eigen paden en patchregister met CI-controle | Aanvaard |
| [ADR-0003](ADR-0003-branding-zichtbare-naam.md) | Branding: alleen zichtbare naam "Jelly Leon"; technische identiteit `jellyfin-web` | Aanvaard |
| [ADR-0004](ADR-0004-schermen-hub-versus-webclient.md) | Platformschermen in de Hub-UI; in de webclient alleen in-context-elementen; beveiliging op de server | Aanvaard |
| [ADR-0005](ADR-0005-versieschema-en-basis.md) | Versieschema: `package.json` blijft upstream, forkversie in `baseline.json` | Aanvaard |
| [ADR-0006](ADR-0006-upstream-sync.md) | Upstream-sync via `sync/<tag>`, nooit automatisch naar productie (EX48) | Aanvaard |
| [ADR-0007](ADR-0007-upstream-workflows-in-fork.md) | Upstream-workflows ongewijzigd; guards bewaakt door `workflow_check.py` | Aanvaard |
| [ADR-0008](ADR-0008-geen-eigen-image.md) | Geen eigen image of Custom App: de webclient zit in `ghcr.io/lvos04/jelly-leon` | Aanvaard |
| [ADR-0009](ADR-0009-toolchain-node-en-afhankelijkheden.md) | Toolchain Node 22.23.4 in CI; afhankelijkheden niet zelf patchen in P0 | Node-deel vervangen door ADR-0011 |
| [ADR-0010](ADR-0010-contract-1-2.md) | Platformcontract 1.2: byte-gelijke kopie met drifttest, strenge bewijsregels (§11), JW1–JW3 | Aanvaard |
| [ADR-0011](ADR-0011-upgrade-12x-webclient.md) | Webclient naar jellyfin-web 12.x (P4-0): herbasis v12.4, Node 24, guard JLW-0001, zichtbare naam JLW-0002, layouts, haakpunten (UG-WEB) | Aanvaard |
| [ADR-0012](ADR-0012-contract-1-3.md) | Platformcontract 1.3: kopie + drifttest-pin (C1.3-JLW-01), bewijsregels §11 van 1.3 (C1.3-JLW-02), wat niet van toepassing is | Aanvaard |
