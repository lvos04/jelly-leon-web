# ADR-0006 — Upstream-sync via `sync/<tag>`, nooit automatisch naar productie (EX48)

- **Status:** Aanvaard (P0, 2026-11-09)
- **Context:** B03-013, I06 stap 7 ("upstream tracking branch en CI compat smoke"), I24 stap 1, testmatrix **EX48**
  ("nieuwe Jellyfin-upstreamcode met incompatibiliteit → test faalt, geen productiedeploy"). Upstream jellyfin-web heeft
  naast `v10.11.11` al `v12.0`…`v12.4` (gemeten 2026-11-09). Serverfork: zelfde aanpak (`lvos04/jelly-leon` ADR-0006).

## Besluit

1. **Werktuig** `tools/jelly-leon-web/upstream_sync.py` (standaardbibliotheek; unit-getest met een nep-upstream):
   `kies` (sporen `patch` = zelfde major.minor, `nieuwste` = hoogste stabiele tag; rc/beta nooit; numerieke volgorde)
   en `merge` naar branch `sync/<tag>` met methode `merge` (zelfde reeks) of `herbasis` (andere reeks: upstream-tag +
   fork-eigen paden + geregistreerde patches, merge-commit met beide ouders, geen force-push). Conflict = exit 2,
   alles teruggedraaid. Werkt `baseline.json` bij; meldt als `package.json` een andere versie heeft dan de tag.
2. **Workflow** `.github/workflows/upstream-sync.yml` (maandag 04:37 UTC + handmatig): sync → forkregels
   (consistentie, patchregister, `workflow_check.py`, tool-tests) → `npm ci` (Node 22.23.4, engine-strict) → eslint,
   stylelint, tsc, vitest → build + es-check → web-client-smoketest tegen de **officiële server van dezelfde versie**
   (`docker.io/jellyfin/jellyfin:<versie>`, vóór gebruik op digest vastgezet en in het rapport vermeld; bestaat die
   image niet, dan faalt de sync: niet verifieerbaar = niet overnemen). Elke fout = workflow faalt.
3. **Nooit naar productie:** geen image, geen release, standaardbranch ongemoeid. Resultaat als git-bundle; alleen met
   geheim `JLW_SYNC_PUSH_TOKEN` (contents + workflows) wordt `sync/<tag>` gepusht ter beoordeling. Overnemen en
   release (samen met de server) zijn handmatige R2-stappen.

## Echte meting (2026-11-09, tijdelijke kloon, niets gepusht)

- `kies`: spoor `patch` geen kandidaat; spoor `nieuwste` **v12.4**.
- `merge`: **30 conflicten**, alle in bestanden die de fork nooit wijzigde (upstream-backports op de releasebranch).
- `herbasis`: 0 conflicten (0 core-patches), daarna faalt de sync terecht: `workflow_check.py` (nieuw
  `workflow_run.yml` met onbewaakte `JF_BOT_TOKEN`/`CLOUDFLARE_*`) en `npm ci` (`EBADENGINE`: node ≥ 24, npm ≥ 11).
  Rapport: `docs/platform-v2/test-evidence/p0-upstream-syncproef-v12.4.json`.

## Gevolgen

- EX48 is met echte upstream-code aangetoond (Sim-geslaagd); een echte GitHub-run is NIET GEVALIDEERD (scheduled
  workflows draaien alleen vanaf de standaardbranch).
- Overstap naar 12.x vraagt: guard-patch op `workflow_run.yml`, toolchainbesluit Node 24 (samen met .NET 10 voor de
  server), clientmatrix opnieuw, terugzetpad server+web+database samen.
