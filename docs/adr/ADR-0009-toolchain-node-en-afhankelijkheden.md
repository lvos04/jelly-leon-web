# ADR-0009 — Toolchain Node 22.23.4 in CI; afhankelijkheden niet zelf patchen in P0

- **Status:** Aanvaard (P0, 2026-11-09)
- **Context:** Upstream v10.11.11: `.nvmrc` = 20, `engines` node ≥ 20 en npm ≥ 9.6.4 < 11, `engine-strict=true`;
  upstream-CI draait Node 20. Node 20 is sinds 30 april 2026 end-of-life. De web-stage van de jelly-leon-image gebruikt
  `node:22.23.4-bookworm-slim` (digest-gepind). `npm audit` meldt advisories in upstream-afhankelijkheden (runtime 23,
  waarvan 2 kritiek). `classlist.js` komt als GitHub-archief binnen.

## Besluit

- CI gebruikt **Node 22.23.4** (exact, zelfde als de image) met de npm die daarbij hoort (10.9.x, binnen `engines`);
  `.nvmrc` blijft upstream (20) — wijzigen zou een core-patch zijn zonder functionele winst.
- **Geen eigen dependency-updates in P0**: `package.json`/`package-lock.json` blijven upstream. Advisories worden
  opgevolgd via upstream-syncs of, als het niet kan wachten, via een geregistreerde patch met test (followup met
  prioriteit voor runtime-afhankelijkheden: `swiper`, `dompurify`, `react-router-dom`, `pdfjs-dist`, `markdown-it`).
- Bouwomgevingen zonder toegang tot GitHub-archieven: de lokale werkwijze in `BOUWVERIFICATIE_P0.md` §2 (zelfde sha512
  als `package-lock.json`); geen wijziging in de repo.
  Contractronde 1.2 (JW3): op de eigen bouwmachine met direct internet is het archief bereikbaar en werkt `npm ci`
  zonder omweg, ook met een lege npm-cache (`BOUWVERIFICATIE_P0.md` §8). Lokaal hoort daar Node 22.23.4 met npm
  10.9.x bij: een systeem-npm < 9.6.4 valt buiten `engines` en wordt door `engine-strict=true` geweigerd.

## Gevolgen

- Upstream v12.x eist Node ≥ 24/npm ≥ 11 → bij die sync faalt `npm ci` (gemeten); dan een bewust toolchainbesluit,
  samen met de server (.NET 10) en de image.
